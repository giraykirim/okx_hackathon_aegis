"""Opt-in account capability diagnostics. Returned tool calls are never executed."""

from .atk_evidence import strict_json
from .models import Capability, utcnow


async def verify_features(models, run_id):
    models.begin_cycle(run_id, run_id)
    for name in ("EVREN_STRUCTURED_OUTPUT", "EVREN_TOOL_CALLING"):
        models.capabilities[name] = Capability()
    if not models.settings.evren_base_url or not models.settings.evren_api_key:
        return
    try:
        base, headers = await models.discover_evren(run_id)
    except Exception:
        return
    for feature in ("STRUCTURED_OUTPUT", "TOOL_CALLING"):
        try:
            body = {
                "model": models.selected_model,
                "stream": False,
                "max_tokens": min(128, models.settings.evren_max_tokens),
                "evren_tools": False,
                "messages": [
                    {
                        "role": "user",
                        "content": 'Capability probe only. Return {"status":"probe_ok"} or call the provided no-op probe function. Do not execute any tool.',
                    }
                ],
            }
            if feature == "STRUCTURED_OUTPUT":
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "aegis_probe",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {"status": {"type": "string", "enum": ["probe_ok"]}},
                            "required": ["status"],
                            "additionalProperties": False,
                        },
                    },
                }
            else:
                body["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": "aegis_capability_probe",
                            "description": "No-op capability probe; never executed",
                            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                        },
                    }
                ]
                body["tool_choice"] = {"type": "function", "function": {"name": "aegis_capability_probe"}}
            response = await models.request_json(
                "POST",
                base + "/chat/completions",
                headers=headers,
                json=body,
                operation="probe_" + feature.lower(),
            )
            message = response["choices"][0]["message"]
            if feature == "STRUCTURED_OUTPUT":
                if message.get("tool_calls") or strict_json(message["content"]) != {"status": "probe_ok"}:
                    raise ValueError("Structured probe invalid")
            else:
                tools = message.get("tool_calls")
                if not isinstance(tools, list) or len(tools) != 1 or tools[0].get("type") != "function":
                    raise ValueError("Tool probe invalid")
                function = tools[0]["function"]
                if function["name"] != "aegis_capability_probe" or strict_json(function["arguments"]) != {}:
                    raise ValueError("Tool probe invalid")
            models.capabilities["EVREN_" + feature] = Capability(
                status="PASS",
                checked_at=utcnow(),
                evidence=[models.journal.entries[-1]["tool_call"]["evidence_id"]],
            )
        except BaseException as exc:
            models.capabilities["EVREN_" + feature] = Capability(
                status="FAIL",
                checked_at=utcnow(),
                evidence=[models.journal.entries[-1]["tool_call"]["evidence_id"]]
                if models.journal.entries
                else [],
            )
            if not isinstance(exc, Exception):
                raise
