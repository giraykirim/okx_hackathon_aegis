import hashlib
import json

import pytest

from aegis.atk import ATK
from aegis.models import utcnow
from aegis.settings import Settings


@pytest.mark.asyncio
async def test_receipt_contains_actual_command_timestamps_hash_elapsed_and_run(monkeypatch):
    ticker = [
        {
            "instId": "BTC-USDT",
            "last": "50000",
            "askPx": "50001",
            "bidPx": "49999",
            "ts": str(int(utcnow().timestamp() * 1000)),
        }
    ]
    raw = json.dumps(ticker).encode()
    seen = []

    class Process:
        returncode = 0

        async def communicate(self):
            return raw, b"sensitive stderr must not appear"

    async def spawn(*args, **kwargs):
        seen.append(args)
        assert "OKX_API_KEY" not in kwargs["env"]
        return Process()

    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    atk = ATK(Settings(_env_file=None, atk_transport="cli"))
    atk.begin_observation("actual-server-run")
    assert await atk.call("ticker") == ticker
    receipt = atk.market_receipts[0]
    assert receipt.command == list(seen[0])
    assert receipt.run_id == "actual-server-run" and receipt.source_mode == "MARKET_ONLY"
    assert receipt.status == "PASS" and receipt.market_timestamp is not None
    assert receipt.requested_at <= receipt.completed_at and receipt.elapsed_ms >= 0
    assert receipt.stdout_sha256 == hashlib.sha256(raw).hexdigest()
    assert (
        receipt.result_sha256
        == hashlib.sha256(json.dumps(ticker, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    )
    assert "sensitive" not in receipt.model_dump_json()


@pytest.mark.asyncio
async def test_failed_atk_receipt_contains_no_provider_error(monkeypatch):
    class Process:
        returncode = 1

        async def communicate(self):
            return b"", b"private provider failure text"

    async def spawn(*args, **kwargs):
        return Process()

    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    atk = ATK(Settings(_env_file=None, atk_transport="cli"))
    atk.begin_observation("failed-run")
    with pytest.raises(RuntimeError):
        await atk.call("ticker")
    receipt = atk.market_receipts[0]
    assert receipt.status == "FAIL" and receipt.result_sha256 is None
    assert receipt.error_type == "RuntimeError"
    assert "private provider" not in receipt.model_dump_json()
