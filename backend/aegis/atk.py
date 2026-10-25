import asyncio
import hashlib
import json
import os
import re
import shutil
import signal
import sys
import tempfile
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .atk_evidence import ToolJournal, strict_json
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
    # Fixed public OHLCV window for EVREN's trend features (48 x 15m = 12h).
    "candles": ("market", "candles", "BTC-USDT", "--bar", "15m", "--limit", "48"),
}
PRIVATE = {"balance", "config", "orders", "place", "get"}
ORDER_NOT_FOUND = "51603"


class ATKCommandError(RuntimeError):
    """Non-zero CLI exit with the venue's numeric code and a short, secret-redacted message."""

    def __init__(self, code: str | None, detail: str | None):
        super().__init__("ATK subprocess failed")
        self.code, self.detail = code, detail


class ATK:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.run_id = new_id()
        self.market_receipts: list[ATKReceipt] = []
        self.journal = ToolJournal(self)
        self.evidence_sink = None
        # Venue-reported fill of the most recent reconcile() call, if any.
        self.last_fill: dict | None = None
        # Top-of-book sizes from the most recent ticker (same response as Observation bid/ask).
        self.last_top_of_book: dict | None = None
        self.capabilities = {
            "ATK_MARKET": Capability(),
            "ATK_ACCOUNT": Capability(),
            "ATK_DEMO": Capability(),
            **{
                name: Capability()
                for name in (
                    "ATK_PACKAGE_INSTALLED",
                    "ATK_MARKET_READ",
                    "ATK_MCP_LIST_TOOLS",
                    "ATK_MCP_CALL_TOOL",
                    "ATK_TR_ROUTING",
                    "ATK_DEMO_ACCOUNT_READ",
                    "ATK_DEMO_ORDER_SUBMISSION",
                    "ATK_ORDER_RECONCILIATION",
                )
            },
        }

    def begin_observation(self, run_id: str, correlation_id: str | None = None):
        self.run_id = run_id
        self.correlation_id = correlation_id or run_id
        self.market_receipts = []
        self.journal.entries = []
        started, requested = time.perf_counter(), utcnow()
        packages = {}
        for package in ("okx-trade-cli", "okx-trade-mcp"):
            try:
                manifest = strict_json((ROOT / f"node_modules/@okx_ai/{package}/package.json").read_bytes())
                packages[package] = (
                    manifest["name"] == f"@okx_ai/{package}" and manifest["version"] == "1.4.8"
                )
            except (OSError, ValueError, KeyError):
                packages[package] = False
        evidence = self.journal.record(
            "local:official-atk-package-inspection",
            requested,
            (time.perf_counter() - started) * 1000,
            all(packages.values()),
            response=packages,
            packages=packages,
            private_capabilities="NOT_TESTED until authenticated demo operation is actually observed",
            demo_gate={
                "enabled": self.settings.demo_enabled,
                "region_confirmed": self.settings.demo_region_confirmed,
                "isolated_demo_ready": bool(self.settings.demo_ready()),
                "personal_profile_used": False,
            },
        )
        self.capabilities["ATK_PACKAGE_INSTALLED"] = Capability(
            status="PASS" if all(packages.values()) else "FAIL", evidence=[evidence], checked_at=utcnow()
        )
        for name in ("ATK_DEMO_ACCOUNT_READ", "ATK_DEMO_ORDER_SUBMISSION", "ATK_ORDER_RECONCILIATION"):
            if self.capabilities[name].status == "NOT_TESTED":
                self.capabilities[name] = Capability(evidence=[evidence], checked_at=utcnow())

    def tool_events(self):
        return self.journal.events()

    def child_environment(self, directory: Path, *, private: bool) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "en_US.UTF-8",
            "AEGIS_ATK_HOME": str(directory),
            "OKX_DEMO": "1",
            "OKX_SITE": self.settings.okx_site,
            "OKX_TIMEOUT_MS": "10000",
        }
        if sys.platform == "win32":
            # Windows Node/OpenSSL needs SystemRoot to initialize its random source.
            # Do not inherit the rest of the parent environment or its credentials.
            env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
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
        if operation not in PRIVATE and operation != "candles" and self.settings.atk_transport == "mcp":
            if args:
                raise ValueError("MCP public operation arguments are fixed")
            return await self.call_mcp(operation)
        command = [
            shutil.which("node") or "node",
            "--import",
            (ROOT / "aegis/atk-isolation.mjs").as_uri(),
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
        error_code, error_detail = None, None
        status, result = "FAIL", None
        try:
            stdout = await self.run_subprocess(command, private=operation in PRIVATE)
            stdout_hash = hashlib.sha256(stdout).hexdigest()
            if len(stdout) > 2_000_000:
                raise ValueError("ATK response exceeded bounds")
            result = strict_json(stdout)
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
            if isinstance(exc, ATKCommandError):
                # Receipt contract keeps the generic type; venue codes are journaled for order calls only.
                error_type = "RuntimeError"
                if operation in {"place", "get"}:
                    error_code, error_detail = exc.code, exc.detail
            raise
        finally:
            evidence_id = self.journal.record(
                "@okx_ai/okx-trade-cli@1.4.8:" + operation,
                requested_at,
                (time.perf_counter() - started) * 1000,
                status == "PASS",
                response=result,
                source_ts=market_timestamp if status == "PASS" else None,
                transport="official-cli",
                site=self.settings.okx_site,
                payload_redacted=operation in PRIVATE,
                error_type=error_type,
                error_code=error_code,
                error_detail=error_detail,
            )
            if operation == "ticker":
                self.public_capabilities(status == "PASS", evidence_id)
            if operation in {"place", "get"}:
                name = "ATK_DEMO_ORDER_SUBMISSION" if operation == "place" else "ATK_ORDER_RECONCILIATION"
                # A JSON envelope alone is insufficient: mark PASS only after semantic checks below.
                self.capabilities[name] = Capability(
                    status="FAIL", evidence=[evidence_id], checked_at=utcnow()
                )
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

    def public_capabilities(self, success: bool, evidence_id: str):
        capability = Capability(
            status="PASS" if success else "FAIL", evidence=[evidence_id], checked_at=utcnow()
        )
        self.capabilities["ATK_MARKET_READ"] = capability
        if self.settings.okx_site == "tr":
            self.capabilities["ATK_TR_ROUTING"] = capability

    async def call_mcp(self, operation: str):
        tool = {"ticker": "market_get_ticker", "instruments": "market_get_instruments"}[operation]
        command = [
            shutil.which("node") or "node",
            str(ROOT / "aegis/atk-mcp-client.mjs"),
            operation,
            self.settings.okx_site,
        ]
        requested, started = utcnow(), time.perf_counter()
        call, discovery = None, None
        success, source_ts, capabilities = False, None, {}
        try:
            reply = strict_json(await self.run_subprocess(command, private=False))
            discovery = reply.get("discovery")
            if not isinstance(discovery, dict) or not isinstance(
                discovery.get("result", {}).get("tools"), list
            ):
                raise ValueError("MCP discovery unavailable")
            evidence_id = self.journal.record(
                "@okx_ai/okx-trade-mcp@1.4.8:tools/list",
                discovery["request_ts"],
                discovery.get("latency_ms", "UNKNOWN"),
                True,
                response=discovery["result"],
                transport="mcp-stdio",
                site=self.settings.okx_site,
                tools=discovery["result"]["tools"],
                server_args=reply.get("server_args", []),
            )
            self.capabilities["ATK_MCP_LIST_TOOLS"] = Capability(
                status="PASS", evidence=[evidence_id], checked_at=utcnow()
            )
            call = reply.get("call")
            if not isinstance(call, dict) or not isinstance(call.get("result"), dict):
                raise ValueError("MCP tool invocation unavailable")
            result = call["result"]
            data = result.get("structuredContent")
            if isinstance(data, dict) and isinstance(data.get("capabilities"), dict):
                capabilities = data["capabilities"]
            if (
                result.get("isError")
                or not isinstance(data, dict)
                or data.get("ok") is not True
                or data.get("tool") != tool
                or data.get("capabilities", {}).get("readOnly") is not True
                or data.get("capabilities", {}).get("hasAuth") is not False
                or not isinstance(data.get("data"), dict)
            ):
                raise ValueError("MCP public tool result rejected")
            rows = data["data"].get("data")
            if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
                raise ValueError("Unexpected MCP market rows")
            if rows[0].get("instId") != "BTC-USDT":
                raise ValueError("MCP symbol mismatch")
            if operation == "ticker":
                source_ts = datetime.fromtimestamp(int(rows[0]["ts"]) / 1000, timezone.utc)
            success = True
            return rows
        finally:
            evidence_id = self.journal.record(
                "@okx_ai/okx-trade-mcp@1.4.8:" + tool if call else "mcp:session",
                call["request_ts"] if call else requested,
                call.get("latency_ms", "UNKNOWN") if call else (time.perf_counter() - started) * 1000,
                success,
                response=call.get("result") if call else None,
                source_ts=source_ts,
                transport="mcp-stdio",
                site=self.settings.okx_site,
                read_only=capabilities.get("readOnly", "UNKNOWN"),
                has_auth=capabilities.get("hasAuth", "UNKNOWN"),
                payload_redacted=False,
            )
            self.capabilities["ATK_MCP_CALL_TOOL"] = Capability(
                status="PASS" if success else "FAIL", evidence=[evidence_id], checked_at=utcnow()
            )
            if discovery is None:
                self.capabilities["ATK_MCP_LIST_TOOLS"] = Capability(
                    status="FAIL", evidence=[evidence_id], checked_at=utcnow()
                )
            if operation == "ticker":
                self.public_capabilities(success, evidence_id)

    async def run_subprocess(self, command: list[str], *, private: bool) -> bytes:
        with tempfile.TemporaryDirectory(prefix="aegis-atk-") as directory:
            env = self.child_environment(Path(directory), private=private)
            process = await asyncio.create_subprocess_exec(
                *command,
                env=env,
                cwd=ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=sys.platform != "win32",
            )
            try:
                stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=20)
            except BaseException:
                if process.returncode is None:
                    try:
                        if sys.platform == "win32":
                            process.kill()
                        else:
                            os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await process.communicate()
                raise
            if len(stdout) > 2_000_000:
                raise RuntimeError("ATK subprocess response exceeded bounds")
            if process.returncode != 0:
                # Only the venue code and a bounded first error line leave; secrets are redacted.
                # `--json` failures may print to either stream; both are bounded and redacted.
                text = (_stderr[:4096] + b"\n" + stdout[:4096]).decode(errors="replace")
                for value in env.values():
                    if len(value) >= 8 and value in text and value not in {env.get("PATH"), directory}:
                        text = text.replace(value, "[REDACTED]")
                # Prefer the per-order sCode/sMsg over the envelope's generic code.
                code = next(
                    (
                        m.group(1)
                        for p in (
                            r"\"sCode\"\s*:\s*\"?(\d{1,8})",
                            r"Code:\s*(\d{1,8})",
                            r"\[(\d{4,8})\]",
                            r"\"code\"\s*:\s*\"?(\d{1,8})",
                        )
                        if (m := re.search(p, text))
                    ),
                    None,
                )
                message = next(
                    (
                        m.group(1).strip()
                        for p in (
                            r"\"sMsg\"\s*:\s*\"([^\"]{1,160})",
                            r"Error:\s*([^\n]{1,160})",
                            r"\"msg\"\s*:\s*\"([^\"]{1,160})",
                        )
                        if (m := re.search(p, text))
                    ),
                    None,
                )
                first = next((line.strip()[:160] for line in text.splitlines() if line.strip()), None)
                raise ATKCommandError(code, message or first)
            return stdout

    async def observe(self) -> Observation:
        self.last_top_of_book = None
        ticker = (await self.call("ticker"))[0]
        instrument = (await self.call("instruments"))[0]
        if ticker["instId"] != "BTC-USDT" or instrument["instId"] != "BTC-USDT":
            raise ValueError("ATK symbol mismatch")
        if instrument.get("baseCcy") != "BTC" or instrument.get("quoteCcy") != "USDT":
            raise ValueError("ATK base/quote currency mismatch or unavailable")
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
        self.last_top_of_book = {
            "bid_sz": ticker.get("bidSz") or None,
            "ask_sz": ticker.get("askSz") or None,
            "observed_at": observation.observed_at.isoformat(),
        }
        self.capabilities["ATK_MARKET"] = Capability(
            status="PASS",
            checked_at=utcnow(),
            evidence=[
                "Official ATK " + self.settings.atk_transport + " ticker + instruments returned JSON",
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
                self.capabilities["ATK_DEMO_ACCOUNT_READ"] = Capability(
                    status="PASS",
                    checked_at=utcnow(),
                    evidence=[
                        e.details["tool_call"]["evidence_id"]
                        for e in self.tool_events()
                        if e.details["tool_call"]["tool_id"].endswith((":config", ":balance", ":orders"))
                    ],
                )
            except Exception as exc:
                observation.account_known = False
                self.capabilities["ATK_ACCOUNT"] = Capability(
                    status="FAIL",
                    checked_at=utcnow(),
                    evidence=["Demo account observation failed: " + type(exc).__name__],
                )
                self.capabilities["ATK_DEMO_ACCOUNT_READ"] = Capability(
                    status="FAIL",
                    checked_at=utcnow(),
                    evidence=[
                        e.details["tool_call"]["evidence_id"]
                        for e in self.tool_events()
                        if e.details["tool_call"]["tool_id"].endswith((":config", ":balance", ":orders"))
                    ],
                )
        return observation

    async def trend(self) -> dict:
        """Deterministic 15m trend features from closed official ATK candles (strings, no floats)."""
        rows = await self.call("candles")
        closed = [r for r in rows if isinstance(r, list) and len(r) >= 9 and r[8] == "1"]
        if len(closed) < 33:
            raise ValueError("Insufficient closed candles")
        closes = [Decimal(r[4]) for r in reversed(closed)]  # oldest -> newest
        last = closes[-1]

        def pct(new: Decimal, old: Decimal) -> str:
            return format(((new / old) - 1) * 100, ".3f")

        def sma(n: int) -> Decimal:
            return sum(closes[-n:], Decimal(0)) / n

        returns = [(closes[i] / closes[i - 1]) - 1 for i in range(len(closes) - 32, len(closes))]
        mean = sum(returns, Decimal(0)) / len(returns)
        volatility = (sum(((r - mean) ** 2 for r in returns), Decimal(0)) / len(returns)).sqrt() * 100
        window = closes[-32:]
        high, low = max(window), min(window)
        return {
            "bar": "15m",
            "candle_open_ts": closed[0][0],
            "closed_candles": len(closes),
            "last_close": format(last, "f"),
            "return_1h_pct": pct(last, closes[-5]),
            "return_4h_pct": pct(last, closes[-17]),
            "return_8h_pct": pct(last, closes[-33]),
            "sma_8": format(sma(8).quantize(Decimal("0.1")), "f"),
            "sma_32": format(sma(32).quantize(Decimal("0.1")), "f"),
            "sma_8_vs_32_pct": pct(sma(8), sma(32)),
            "volatility_15m_pct": format(volatility, ".3f"),
            "range_position_8h": format((last - low) / (high - low), ".2f") if high > low else "0.50",
        }

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
        self.capabilities["ATK_DEMO_ORDER_SUBMISSION"] = Capability(
            status="PASS",
            checked_at=utcnow(),
            evidence=self.capabilities["ATK_DEMO_ORDER_SUBMISSION"].evidence,
        )
        return row["ordId"]

    async def reconcile(
        self, proposal: Proposal, client_id: str, limit_price: Decimal | None = None
    ) -> tuple[str, str, str]:
        if limit_price is None:
            raise ValueError("Persisted policy price required for reconciliation")
        self.last_fill = None
        try:
            row = (await self.call("get", "--instId", "BTC-USDT", "--clOrdId", client_id))[0]
        except ATKCommandError as exc:
            if exc.code == ORDER_NOT_FOUND:
                # The venue has no order for this client ID: the submission never landed.
                return "FAILED", None, "not_found"
            raise
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
        if state in {"filled", "partially_filled", "canceled", "mmp_canceled"}:
            # Preserve the venue's own execution figures verbatim for PnL reporting; a canceled
            # IOC may still carry a partial fill. A missing fee stays None, never "0", and the
            # execution time is the venue's fillTime, not this read-back's wall clock.
            self.last_fill = {
                "schema": 2,
                "ord_id": row["ordId"],
                "cl_ord_id": row.get("clOrdId"),
                "inst_id": row.get("instId"),
                "side": row.get("side"),
                "ord_type": row.get("ordType"),
                "avg_price": row.get("avgPx") or None,
                "filled_qty": row.get("accFillSz") or None,
                "fee": row.get("fee") if row.get("fee") not in (None, "") else None,
                "fee_ccy": row.get("feeCcy") or None,
                "rebate": row.get("rebate") or "",
                "rebate_ccy": row.get("rebateCcy") or None,
                "fill_time_ms": row.get("fillTime") or None,
                "u_time_ms": row.get("uTime") or None,
                "c_time_ms": row.get("cTime") or None,
                "state": state,
                "source_mode": "OKX_DEMO",
            }
        if state in {"filled", "canceled", "mmp_canceled"}:
            self.capabilities["ATK_ORDER_RECONCILIATION"] = Capability(
                status="PASS",
                checked_at=utcnow(),
                evidence=self.capabilities["ATK_ORDER_RECONCILIATION"].evidence,
            )
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
