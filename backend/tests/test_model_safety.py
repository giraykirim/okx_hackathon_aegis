import json

import httpx
import pytest
from test_policy import inputs

from aegis.integrations import Models
from aegis.settings import Settings


def configured(**kwargs):
    return Settings(
        _env_file=None,
        evren_base_url="https://evren.invalid/v1",
        evren_api_key="canary-key",
        evren_model="account-model",
        **kwargs,
    )


def discovery(request):
    if request.url.path.endswith("terms/status"):
        return httpx.Response(200, json={"current_version": 1, "accepted": True})
    if request.url.path.endswith("models"):
        return httpx.Response(200, json={"data": [{"id": "account-model"}]})


def completion(**changes):
    proposal = {
        "action": "NO_TRADE",
        "symbol": "BTC-USDT",
        "quantity": "0",
        "intent_id": "safe",
        "summary": "No verified opportunity",
        **changes,
    }
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(proposal),
                        "reasoning_content": "PRIVATE_REASONING_MUST_NOT_BE_AUDITED",
                    }
                }
            ]
        },
    )


def test_environment_aliases_and_bounded_settings(monkeypatch):
    monkeypatch.setenv("EVREN_BASE_URL", "https://account.invalid/v1")
    monkeypatch.setenv("EVREN_API_KEY", "secret-env-only")
    monkeypatch.setenv("EVREN_MODEL", "actual-selected-model")
    monkeypatch.setenv("EVREN_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("EVREN_MAX_REQUESTS_PER_RUN", "4")
    settings = Settings(_env_file=None)
    assert settings.evren_base_url == "https://account.invalid/v1"
    assert settings.evren_model == "actual-selected-model"
    assert settings.evren_api_key.get_secret_value() == "secret-env-only"
    assert settings.evren_timeout_seconds == 1.5 and settings.evren_max_requests_per_run == 4
    with pytest.raises(ValueError):
        configured(evren_max_requests_per_run=0)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["429", "json", "timeout", "long_rationale", "tools"])
async def test_evren_provider_failures_fail_closed_with_no_retry_or_private_output(failure):
    requests = []

    def handle(request):
        requests.append(request)
        found = discovery(request)
        if found is not None:
            return found
        if failure == "429":
            return httpx.Response(429, text="canary-key PRIVATE_PROVIDER_BODY")
        if failure == "json":
            return httpx.Response(200, text="not valid JSON canary-key")
        if failure == "timeout":
            raise httpx.ReadTimeout("canary-key")
        if failure == "tools":
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}", "tool_calls": [{}]}}]})
        return completion(summary="x" * 241)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(configured(), client)
        result = await models.reason(inputs()[0], inputs()[1], "run")
        assert result.action == "NO_TRADE" and result.quantity == 0
        assert models.capabilities["EVREN"].status == "FAIL"
        records = models.tool_events()
        assert len(requests) == 3 and records
        assert "canary-key" not in str([event.model_dump() for event in records])
        assert "PRIVATE_PROVIDER_BODY" not in str([event.model_dump() for event in records])
        if failure == "429":
            assert records[-1].details["tool_call"]["status_code"] == 429
            assert models.evren_metadata["reason_code"] == "PROVIDER_RATE_LIMITED"


@pytest.mark.asyncio
async def test_structured_proposal_excludes_private_account_and_hidden_reasoning():
    def handle(request):
        found = discovery(request)
        if found is not None:
            return found
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        assert body["evren_tools"] is False and "tools" not in body
        data = json.loads(body["messages"][1]["content"])
        assert "quote_available" not in data["state"] and "base_available" not in data["state"]
        assert "UNTRUSTED" in body["messages"][0]["content"]
        return completion()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(configured(), client)
        result = await models.reason(inputs()[0], inputs()[1], "run")
        assert result.summary == "No verified opportunity"
        assert models.evren_metadata["model"] == "account-model"
        assert "PRIVATE_REASONING" not in str([e.model_dump() for e in models.tool_events()])


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["run", "minute"])
async def test_evren_request_budgets_block_more_network_requests(scope):
    calls = []

    def handle(request):
        calls.append(request)
        found = discovery(request)
        return found if found is not None else completion()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        limits = {"evren_max_requests_per_run": 3} if scope == "run" else {"evren_max_requests_per_minute": 3}
        models = Models(configured(**limits), client)
        await models.reason(inputs()[0], inputs()[1], "same-run")
        result = await models.reason(inputs()[0], inputs()[1], "same-run" if scope == "run" else "new-run")
        assert len(calls) == 3 and result.action == "NO_TRADE"
        assert models.evren_metadata["reason_code"] == "REQUEST_CAP_REACHED"


@pytest.mark.asyncio
async def test_native_structured_output_and_tool_calling_probes_are_independent_and_never_execute():
    tool_requests = []

    def handle(request):
        found = discovery(request)
        if found is not None:
            return found
        body = json.loads(request.content)
        assert body["max_tokens"] <= 64
        if "tools" in body:
            tool_requests.append(body)
            name = body["tools"][0]["function"]["name"]
            assert name == "aegis_capability_probe" and body["evren_tools"] is False
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {"type": "function", "function": {"name": name, "arguments": "{}"}}
                                ]
                            }
                        }
                    ]
                },
            )
        return httpx.Response(400, text="unsupported response format")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(configured(evren_max_tokens=64), client)
        await models.verify_evren_features("probe-run")
        assert models.capabilities["EVREN_DISCOVERY"].status == "PASS"
        assert models.capabilities["EVREN_STRUCTURED_OUTPUT"].status == "FAIL"
        assert models.capabilities["EVREN_TOOL_CALLING"].status == "PASS"
        assert len(tool_requests) == 1
        # Even after a successful diagnostic, the runtime never accepts a model tool call.
        result = await models.reason(inputs()[0], inputs()[1], "runtime-run")
        assert result.action == "NO_TRADE"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "unavailable", "version", "timeout"])
async def test_laya_unavailability_and_version_are_explicit_and_advisory(failure):
    def handle(request):
        assert request.url.path == "/classify"
        body = json.loads(request.content)
        assert body["run_id"] == "run" and body["correlation_id"] == "cycle"
        if failure == "timeout":
            raise httpx.ReadTimeout("private error")
        return httpx.Response(
            200,
            json={
                "label": "UNAVAILABLE" if failure == "unavailable" else "CONTINUE",
                "confidence": 1,
                "abstained": False,
                "model_version": "laya-v2",
                "latency_ms": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(
            Settings(
                _env_file=None,
                laya_url=None if failure == "missing" else "http://lan.invalid",
                laya_expected_version="laya-v1" if failure == "version" else None,
            ),
            client,
        )
        result = await models.classify(inputs()[0], "run", "cycle")
        assert result.label == "REVIEW" and result.abstained
        assert models.laya_metadata["availability"] == "UNAVAILABLE"
        assert models.laya_metadata["source"] == ("NOT_CONFIGURED" if failure == "missing" else "LAN")
        if failure == "unavailable":
            assert models.laya_metadata["reported_label"] == "UNAVAILABLE"
            assert models.laya_metadata["model_version"] == "laya-v2"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["LAYA", "EVREN"])
async def test_outer_cancellation_does_not_retain_a_previous_pass(provider):
    import asyncio

    slow = False

    async def handle(request):
        if slow:
            await asyncio.sleep(1)
        if provider == "LAYA":
            return httpx.Response(200, json=inputs()[1].model_dump(mode="json"))
        found = discovery(request)
        return found if found is not None else completion()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(configured(laya_url="http://lan.invalid"), client)

        async def call():
            if provider == "LAYA":
                await models.classify(inputs()[0], "run", "cycle")
            else:
                await models.reason(inputs()[0], inputs()[1], "run")

        await call()
        assert models.capabilities[provider].status == "PASS"
        slow = True
        models.begin_cycle("run", "next-cycle")
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.01):
                await call()
        assert models.capabilities[provider].status == "FAIL"
        assert models.tool_events()[-1].details["tool_call"]["success"] is False


@pytest.mark.asyncio
async def test_autonomous_and_service_clients_share_deployment_request_cap():
    from aegis.integrations import EvrenBudget

    calls = []

    def handle(request):
        calls.append(request)
        found = discovery(request)
        return found if found is not None else completion()

    budget = EvrenBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        settings = configured(evren_max_requests_per_minute=3)
        autonomous = Models(settings, client, budget=budget)
        service = Models(settings, client, budget=budget)
        await autonomous.reason(inputs()[0], inputs()[1], "autonomous-run")
        result = await service.reason(inputs()[0], inputs()[1], "service-run")
        assert len(calls) == 3 and result.action == "NO_TRADE"
        assert service.evren_metadata["reason_code"] == "REQUEST_CAP_REACHED"


def test_exhausted_run_cannot_regain_budget_after_other_runs():
    from aegis.integrations import EvrenBudget, RequestCapReached

    budget = EvrenBudget()
    settings = configured(evren_max_requests_per_run=1)
    budget.consume("exhausted", settings)
    for number in range(130):
        budget.hits.clear()  # Advance the independent minute window without wall-clock sleeps.
        budget.consume(str(number), settings)
    with pytest.raises(RequestCapReached):
        budget.consume("exhausted", settings)


@pytest.mark.asyncio
async def test_provider_echoed_credential_cannot_enter_public_rationale_or_evidence():
    def handle(request):
        if request.url.path.endswith("terms/status"):
            return httpx.Response(200, json={"current_version": 1, "accepted": True})
        if request.url.path.endswith("models"):
            return httpx.Response(200, json={"data": [{"id": "canary-key"}]})
        return completion(summary="canary-key")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        settings = configured().model_copy(update={"evren_model": "canary-key"})
        models = Models(settings, client)
        result = await models.reason(inputs()[0], inputs()[1], "run")
        assert "canary-key" not in result.summary
        assert "canary-key" not in str([event.model_dump() for event in models.tool_events()])
