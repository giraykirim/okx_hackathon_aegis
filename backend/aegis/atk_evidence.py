"""Sanitized internal evidence, stored only inside the existing Event.details."""

import hashlib
import json
import math

from .models import Event, new_id, utcnow


def strict_json(raw):
    def invalid_constant(_value):
        raise ValueError("Non-JSON numeric constant")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("Nonfinite JSON numeric overflow")
        return parsed

    return json.loads(raw, parse_constant=invalid_constant, parse_float=finite_float)


def response_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class ToolJournal:
    def __init__(self, owner, *, actor="atk", message="Sanitized official ATK invocation evidence"):
        self.owner = owner
        self.actor, self.message = actor, message
        self.entries = []

    def record(
        self,
        tool_id,
        request_ts,
        latency_ms,
        success,
        *,
        response=None,
        source_ts=None,
        status_code="UNKNOWN",
        **metadata,
    ):
        evidence_id = new_id()
        metadata.setdefault(
            "correlation_id", getattr(self.owner, "correlation_id", None) or self.owner.run_id
        )
        self.entries.append(
            {
                "tool_call": {
                    "run_id": self.owner.run_id,
                    "tool_id": tool_id,
                    "request_ts": request_ts.isoformat() if hasattr(request_ts, "isoformat") else request_ts,
                    "source_ts": source_ts.isoformat() if source_ts else "UNKNOWN",
                    "source_mode": "OKX_DEMO"
                    if self.owner.settings.source_mode == "OKX_DEMO"
                    else "MARKET_ONLY",
                    "symbol": "BTC-USDT",
                    "latency_ms": latency_ms,
                    "success": success,
                    "response_hash": response_hash(response) if response is not None else "UNKNOWN",
                    # Neither the CLI JSON nor MCP result exposes the upstream HTTP status.
                    "status_code": status_code,
                    "evidence_id": evidence_id,
                },
                **metadata,
            }
        )
        if self.owner.evidence_sink:
            self.owner.evidence_sink(self.event(self.entries[-1]))
        return evidence_id

    def event(self, entry):
        return Event(
            id=entry["tool_call"]["evidence_id"],
            run_id=entry["tool_call"]["run_id"],
            timestamp=utcnow(),
            type="tool_call",
            severity="INFO" if entry["tool_call"]["success"] else "ERROR",
            actor=self.actor,
            message=self.message,
            details=entry,
            source_mode=entry["tool_call"]["source_mode"],
        )

    def events(self):
        return [self.event(entry) for entry in self.entries]
