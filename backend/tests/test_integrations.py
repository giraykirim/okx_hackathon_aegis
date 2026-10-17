import json
from datetime import timedelta

import httpx
import pytest
from test_policy import inputs

from aegis.models import utcnow
from aegis.settings import Settings


@pytest.mark.asyncio
async def test_evren_uses_only_account_discovered_model():
    from aegis.integrations import Models

    seen = []

    def handle(request):
        seen.append(request)
        assert request.headers["X-API-Key"] == "local"
        if request.url.path == "/v1/terms/status":
            return httpx.Response(200, json={"current_version": 1, "accepted": True})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "actual-account-model"}]})
        body = json.loads(request.content)
        assert body["model"] == "actual-account-model"
        assert "tools" not in body
        assert body["evren_tools"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "action": "NO_TRADE",
                                    "symbol": "BTC-USDT",
                                    "quantity": "0",
                                    "intent_id": "test",
                                    "summary": "No confirmed opportunity",
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(Settings(evren_base_url="https://provider.invalid/v1", evren_api_key="local"), client)
        obs, classification, _, _ = inputs()
        proposal = await models.reason(obs, classification, "run")
    assert proposal.action == "NO_TRADE"
    assert len(seen) == 3
    assert models.capabilities["EVREN"].status == "PASS"


@pytest.mark.asyncio
async def test_guessed_model_is_rejected_without_generation():
    from aegis.integrations import Models

    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/v1/terms/status":
            return httpx.Response(200, json={"current_version": 1, "accepted": True})
        return httpx.Response(200, json={"data": [{"id": "actual"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(
            Settings(
                evren_base_url="https://provider.invalid/v1", evren_api_key="local", evren_model="guessed"
            ),
            client,
        )
        obs, classification, _, _ = inputs()
        proposal = await models.reason(obs, classification, "run")
    assert proposal.action == "NO_TRADE"
    assert calls == ["/v1/terms/status", "/v1/models"]
    assert models.capabilities["EVREN"].status == "FAIL"


@pytest.mark.asyncio
async def test_oversized_laya_response_is_bounded(monkeypatch):
    import aegis.integrations as integration_module
    from aegis.integrations import Models

    monkeypatch.setattr(integration_module, "MAX_RESPONSE_BYTES", 64, raising=False)

    def handle(request):
        return httpx.Response(
            200,
            json={
                "label": "CONTINUE",
                "confidence": 1,
                "abstained": False,
                "model_version": "a" * 100,
                "latency_ms": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(Settings(laya_url="http://192.168.1.10:8001"), client)
        result = await models.classify(inputs()[0], "run", "x")
    assert result.abstained and result.label == "REVIEW"


@pytest.mark.asyncio
async def test_trickling_laya_response_has_total_deadline(monkeypatch):
    import asyncio

    import aegis.integrations as integration_module
    from aegis.integrations import Models

    monkeypatch.setattr(integration_module, "REQUEST_TIMEOUT_SECONDS", 0.02, raising=False)

    class Trickled(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(20):
                await asyncio.sleep(0.01)
                yield b" "
            yield b'{"label":"CONTINUE","confidence":1,"abstained":false,"model_version":"test","latency_ms":1}'

    def handle(request):
        return httpx.Response(200, stream=Trickled())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(Settings(laya_url="http://192.168.1.10:8001"), client)
        result = await models.classify(inputs()[0], "run", "x")
    assert result.abstained and result.label == "REVIEW"


@pytest.mark.asyncio
async def test_invalid_or_tool_bearing_evren_response_fails_closed():
    from aegis.integrations import Models

    def handle(request):
        if request.url.path.endswith("terms/status"):
            return httpx.Response(200, json={"current_version": 1, "accepted": True})
        if request.url.path.endswith("models"):
            return httpx.Response(200, json={"data": [{"id": "actual"}]})
        return httpx.Response(
            200, json={"choices": [{"message": {"tool_calls": [{"name": "withdraw"}], "content": "{}"}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(Settings(evren_base_url="https://provider.invalid/v1", evren_api_key="local"), client)
        obs, classification, _, _ = inputs()
        assert (await models.reason(obs, classification, "run")).action == "NO_TRADE"
    assert models.capabilities["EVREN"].status == "FAIL"


@pytest.mark.asyncio
async def test_laya_contract_and_invalid_confidence():
    from aegis.integrations import Models

    def handle(request):
        body = json.loads(request.content)
        assert set(body) == {"state", "run_id", "correlation_id"}
        assert request.url.path == "/classify"
        return httpx.Response(
            200,
            json={
                "label": "CONTINUE",
                "confidence": 1.5,
                "abstained": False,
                "model_version": "local",
                "latency_ms": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(Settings(laya_url="http://192.168.1.10:8001"), client)
        result = await models.classify(inputs()[0], "run", "correlation")
    assert result.label == "REVIEW" and result.abstained
    assert models.capabilities["LAYA"].status == "FAIL"


@pytest.mark.asyncio
async def test_missing_models_are_explicit_fallbacks():
    from aegis.integrations import Models

    models = Models(Settings())
    assert (await models.classify(inputs()[0], "run", "x")).model_version == "advisory-fallback"
    assert (await models.reason(inputs()[0], inputs()[1], "run")).action == "NO_TRADE"
    assert all(c.status == "NOT_TESTED" for c in models.capabilities.values())
    await models.close()


def test_live_source_mode_is_unconfigurable():
    with pytest.raises(ValueError):
        Settings(source_mode="LIVE")


@pytest.mark.asyncio
async def test_atk_allowlist_and_demo_interlocks():
    from aegis.atk import ATK

    atk = ATK(Settings())
    with pytest.raises(ValueError):
        await atk.call("withdraw")
    with pytest.raises(RuntimeError):
        await atk.place(inputs()[2], "a" * 32)


def test_atk_child_environment_does_not_inherit_secrets_or_overrides(monkeypatch, tmp_path):
    from aegis.atk import ATK

    monkeypatch.setenv("OKX_API_BASE_URL", "https://evil.invalid")
    monkeypatch.setenv("OKX_API_KEY", "personal-live-key")
    monkeypatch.setenv("UNRELATED_SECRET", "secret")
    atk = ATK(Settings())
    env = atk.child_environment(tmp_path, private=False)
    assert not {"OKX_API_BASE_URL", "OKX_API_KEY", "UNRELATED_SECRET"} & env.keys()
    assert env["OKX_DEMO"] == "1"
    assert env["OKX_SITE"] == "tr"


def test_windows_child_environment_keeps_systemroot_only(monkeypatch, tmp_path):
    import aegis.atk as atk_module

    monkeypatch.setattr(atk_module.sys, "platform", "win32")
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-inherit")
    env = atk_module.ATK(Settings()).child_environment(tmp_path, private=False)
    assert env["SystemRoot"] == r"C:\Windows"
    assert "UNRELATED_SECRET" not in env


@pytest.mark.asyncio
async def test_atk_preserves_exchange_timestamp(monkeypatch):
    from aegis.atk import ATK

    atk = ATK(Settings())
    old = utcnow() - timedelta(minutes=1)

    async def call(operation, *args):
        if operation == "ticker":
            return [
                {
                    "instId": "BTC-USDT",
                    "last": "50000",
                    "askPx": "50001",
                    "bidPx": "49999",
                    "ts": str(int(old.timestamp() * 1000)),
                }
            ]
        return [
            {
                "instId": "BTC-USDT",
                "instType": "SPOT",
                "minSz": "0.00001",
                "lotSz": "0.00000001",
                "tickSz": "0.1",
                "state": "live",
            }
        ]

    monkeypatch.setattr(atk, "call", call)
    obs = await atk.observe()
    assert (utcnow() - obs.observed_at).total_seconds() > 50
    assert not obs.account_known


@pytest.mark.asyncio
async def test_reconciliation_does_not_trust_mismatched_order(monkeypatch):
    from aegis.atk import ATK

    atk = ATK(Settings())

    async def call(*args):
        return [
            {
                "instId": "ETH-USDT",
                "clOrdId": "a" * 32,
                "ordId": "123",
                "side": "buy",
                "sz": "0.0001",
                "state": "filled",
            }
        ]

    monkeypatch.setattr(atk, "call", call)
    with pytest.raises(ValueError):
        await atk.reconcile(inputs()[2], "a" * 32)


@pytest.mark.asyncio
async def test_demo_placement_is_ioc_with_policy_price_cap(monkeypatch):
    from decimal import Decimal

    from aegis.atk import ATK

    atk = ATK(
        Settings(
            source_mode="OKX_DEMO",
            demo_enabled=True,
            demo_region_confirmed=True,
            okx_demo_api_key="test",
            okx_demo_secret_key="test",
            okx_demo_passphrase="test",
        )
    )
    seen = []

    async def call(operation, *args):
        seen.extend(args)
        return [{"sCode": "0", "ordId": "123"}]

    monkeypatch.setattr(atk, "call", call)
    assert await atk.place(inputs()[2], "a" * 32, Decimal("50501.1")) == "123"
    assert seen[seen.index("--ordType") + 1] == "ioc"
    assert seen[seen.index("--px") + 1] == "50501.1"
    assert "market" not in seen


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,expected",
    [("filled", "VERIFIED"), ("canceled", "VERIFIED"), ("live", "PENDING"), ("partially_filled", "PENDING")],
)
async def test_venue_readback_matches_price_and_cash_mode(monkeypatch, state, expected):
    from decimal import Decimal

    from aegis.atk import ATK

    atk = ATK(Settings())

    async def call(*args):
        return [
            {
                "instId": "BTC-USDT",
                "clOrdId": "a" * 32,
                "ordId": "123",
                "side": "buy",
                "sz": "0.0001",
                "state": state,
                "ordType": "ioc",
                "tdMode": "cash",
                "px": "50501.1",
            }
        ]

    monkeypatch.setattr(atk, "call", call)
    assert (await atk.reconcile(inputs()[2], "a" * 32, Decimal("50501.1")))[0] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        {"current_version": 2, "accepted": False},
        {"current_version": 1},
        {},
        {"current_version": 1, "accepted_version": 1},
        {"current_version": 1, "accepted": "true"},
    ],
)
async def test_unaccepted_or_unknown_terms_block_discovery_and_generation(status):
    from aegis.integrations import Models

    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json=status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = Models(Settings(evren_base_url="https://provider.invalid/v1", evren_api_key="local"), client)
        result = await models.reason(inputs()[0], inputs()[1], "run")
    assert result.action == "NO_TRADE"
    assert calls == ["/v1/terms/status"]
    assert models.capabilities["EVREN"].status == "FAIL"
