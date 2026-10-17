import asyncio
import hashlib
import json
import os
import re
import shutil
import signal
import tempfile
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .models import Capability, Observation, Proposal, new_id, utcnow
from .service_models import ATKReceipt
from .settings import ROOT, Settings

OPERATIONS = {
    "ticker": ("market", "ticker", "BTC-USDT"),
    "instruments": ("market", "instruments", "--instType", "SPOT", "--instId", "BTC-USDT"),
    "balance": ("account", "balance"),
    "config": ("account", "config"),
    "orders": ("spot", "orders"),
    "place": ("spot", "place"),
    "get": ("spot", "get"),
}
PRIVATE = {"balance", "config", "orders", "place", "get"}


class ATK:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.run_id = new_id()
        self.market_receipts: list[ATKReceipt] = []
        self.capabilities = {
            "ATK_MARKET": Capability(),
            "ATK_ACCOUNT": Capability(),
            "ATK_DEMO": Capability(),
        }

    def begin_observation(self, run_id: str):
        self.run_id = run_id
        self.market_receipts = []

    def child_environment(self, directory: Path, *, private: bool) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "en_US.UTF-8",
            "AEGIS_ATK_HOME": str(directory),
            "OKX_DEMO": "1",
            "OKX_SITE": self.settings.okx_site,
            "OKX_TIMEOUT_MS": "10000",
        }
        if private:
            if not self.settings.demo_ready():
                raise RuntimeError("Isolated demo credentials and regional confirmation required")
            for name, value in (
                ("OKX_API_KEY", self.settings.okx_demo_api_key),
                ("OKX_SECRET_KEY", self.settings.okx_demo_secret_key),
                ("OKX_PASSPHRASE", self.settings.okx_demo_passphrase),
            ):
                env[name] = value.get_secret_value()
        return env

    async def call(self, operation: str, *args: str):
        if operation not in OPERATIONS:
            raise ValueError("ATK operation is not allowlisted")
        command = [
            shutil.which("node") or "node",
            "--import",
            str(ROOT / "aegis/atk-isolation.mjs"),
            str(ROOT / "node_modules/@okx_ai/okx-trade-cli/dist/index.js"),
            *OPERATIONS[operation],
            *args,
            "--site",
            self.settings.okx_site,
            "--demo",
            "--json",
        ]
        requested_at, started = utcnow(), time.perf_counter()
        stdout_hash, result_hash, market_timestamp, error_type = None, None, None, None
        status = "FAIL"
        try:
            stdout = await self.run_subprocess(command, private=operation in PRIVATE)
            stdout_hash = hashlib.sha256(stdout).hexdigest()
            if len(stdout) > 2_000_000:
                raise ValueError("ATK response exceeded bounds")
            result = json.loads(stdout)
            if not isinstance(result, list):
                raise ValueError("Unexpected ATK JSON envelope")
            result_hash = hashlib.sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if operation == "ticker":
                market_timestamp = datetime.fromtimestamp(int(result[0]["ts"]) / 1000, timezone.utc)
            status = "PASS"
            return result
        except BaseException as exc:
            error_type = type(exc).__name__
            raise
        finally:
            if operation in {"ticker", "instruments"}:
                self.market_receipts.append(
                    ATKReceipt(
                        id=new_id(),
                        operation=operation,
                        command=command,
                        site=self.settings.okx_site,
                        requested_at=requested_at,
                        completed_at=utcnow(),
                        market_timestamp=market_timestamp,
                        source_mode="OKX_DEMO" if self.settings.source_mode == "OKX_DEMO" else "MARKET_ONLY",
                        run_id=self.run_id,
                        status=status,
                        result_sha256=result_hash,
                        stdout_sha256=stdout_hash,
                        elapsed_ms=(time.perf_counter() - started) * 1000,
                        error_type=error_type,
                    )
                )

    async def run_subprocess(self, command: list[str], *, private: bool) -> bytes:
        with tempfile.TemporaryDirectory(prefix="aegis-atk-") as directory:
            env = self.child_environment(Path(directory), private=private)
            process = await asyncio.create_subprocess_exec(
                *command,
                env=env,
                cwd=ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            try:
                stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=20)
            except BaseException:
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await process.communicate()
                raise
            # Never include raw stderr or arbitrary provider errors in public logs.
            if process.returncode != 0 or len(stdout) > 2_000_000:
                raise RuntimeError("ATK subprocess failed or response exceeded bounds")
            return stdout

    async def observe(self) -> Observation:
        ticker = (await self.call("ticker"))[0]
        instrument = (await self.call("instruments"))[0]
        if ticker["instId"] != "BTC-USDT" or instrument["instId"] != "BTC-USDT":
            raise ValueError("ATK symbol mismatch")
        observation = Observation(
            symbol="BTC-USDT",
            observed_at=datetime.fromtimestamp(int(ticker["ts"]) / 1000, timezone.utc),
            price=ticker["last"],
            ask=ticker["askPx"],
            bid=ticker["bidPx"],
            min_size=instrument["minSz"],
            lot_size=instrument["lotSz"],
            tick_size=instrument["tickSz"],
            instrument_live=instrument["state"] == "live" and instrument["instType"] == "SPOT",
        )
        self.capabilities["ATK_MARKET"] = Capability(
            status="PASS",
            checked_at=utcnow(),
            evidence=[
                "Official @okx_ai/okx-trade-cli@1.4.8 ticker + instruments returned JSON",
                "site=" + self.settings.okx_site,
                "exchange_timestamp=" + observation.observed_at.isoformat(),
            ],
        )
        if self.settings.source_mode == "OKX_DEMO":
            try:
                config = (await self.call("config"))[0]
                permissions = {p.strip() for p in config.get("perm", "").split(",")}
                if not {"read_only", "trade"} <= permissions or "withdraw" in permissions:
                    raise ValueError("Read/trade permissions required; withdraw forbidden")
                account = (await self.call("balance"))[0]
                orders = await self.call("orders")
                balances = {d["ccy"]: d for d in account["details"]}
                exposure = sum(
                    (Decimal(d["eqUsd"]) for d in account["details"] if d["ccy"] != "USDT"), Decimal("0")
                )
                observation.quote_available = balances.get("USDT", {}).get("availBal", "0")
                observation.base_available = balances.get("BTC", {}).get("availBal", "0")
                observation.exposure_quote = exposure
                observation.account_observed_at = datetime.fromtimestamp(
                    int(account["uTime"]) / 1000, timezone.utc
                )
                observation.external_open_orders = bool(orders)
                # Debt or derivative exposure requires a more complete policy; refuse such accounts.
                debt_free = all(Decimal(d.get("liab") or "0") == 0 for d in account["details"])
                observation.account_known = debt_free and config.get("acctLv") == "1"
                self.capabilities["ATK_ACCOUNT"] = Capability(
                    status="PASS",
                    checked_at=utcnow(),
                    evidence=[
                        "Authenticated forced-demo config/balance/open-orders read via ATK",
                        "cash-only account_known=" + str(observation.account_known),
                    ],
                )
            except Exception as exc:
                observation.account_known = False
                self.capabilities["ATK_ACCOUNT"] = Capability(
                    status="FAIL",
                    checked_at=utcnow(),
                    evidence=["Demo account observation failed: " + type(exc).__name__],
                )
        return observation

    async def place(self, proposal: Proposal, client_id: str, limit_price: Decimal | None = None) -> str:
        if not self.settings.demo_ready():
            raise RuntimeError("Exchange execution disabled")
        if proposal.action not in {"BUY", "SELL"} or proposal.quantity <= 0:
            raise ValueError("Invalid order")
        if limit_price is None or not limit_price.is_finite() or limit_price <= 0:
            raise ValueError("Policy-approved execution price required")
        if proposal.quantity * limit_price * Decimal("1.01") > 25:
            raise ValueError("Order exceeds quote cap")
        if not re.fullmatch(r"[a-zA-Z0-9]{32}", client_id):
            raise ValueError("Invalid client order ID")
        rows = await self.call(
            "place",
            "--instId",
            "BTC-USDT",
            "--side",
            proposal.action.lower(),
            "--ordType",
            "ioc",
            "--px",
            format(limit_price, "f"),
            "--tdMode",
            "cash",
            "--sz",
            format(proposal.quantity, "f"),
            "--clOrdId",
            client_id,
        )
        row = rows[0]
        if row.get("sCode") != "0" or not row.get("ordId"):
            # Even a malformed/rejected acknowledgement is reconciled by client ID; never retry placement.
            raise ValueError("Order acknowledgement not confirmed")
        return row["ordId"]

    async def reconcile(
        self, proposal: Proposal, client_id: str, limit_price: Decimal | None = None
    ) -> tuple[str, str, str]:
        if limit_price is None:
            raise ValueError("Persisted policy price required for reconciliation")
        row = (await self.call("get", "--instId", "BTC-USDT", "--clOrdId", client_id))[0]
        if not (
            row.get("instId") == proposal.symbol
            and row.get("clOrdId") == client_id
            and row.get("side") == proposal.action.lower()
            and Decimal(row["sz"]) == proposal.quantity
            and row.get("ordId")
            and row.get("ordType") == "ioc"
            and row.get("tdMode") == "cash"
            and Decimal(row["px"]) == limit_price
        ):
            raise ValueError("Venue order does not match intent")
        state = row["state"]
        if state in {"filled", "canceled", "mmp_canceled"}:
            self.capabilities["ATK_DEMO"] = Capability(
                status="PASS",
                checked_at=utcnow(),
                evidence=[
                    "Forced-demo order read-back matched client ID/symbol/side/quantity",
                    "state=" + state,
                ],
            )
            return "VERIFIED", row["ordId"], state
        if state in {"live", "partially_filled"}:
            return "PENDING", row["ordId"], state
        raise ValueError("Unknown venue state")
