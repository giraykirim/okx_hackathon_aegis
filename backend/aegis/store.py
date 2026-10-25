import hashlib
import json
import re
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .models import Decision, Event, OrderStatus, Proposal, utcnow

EXIT_ASSESSMENT_HISTORY = 500


class RequestConflictError(ValueError):
    pass


class Store:
    def __init__(self, path: Path, secrets: list[str] | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.secrets = [s for s in secrets or [] if s]
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, body TEXT);
            CREATE TABLE IF NOT EXISTS decisions (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, body TEXT);
            CREATE TABLE IF NOT EXISTS intents (
                intent_id TEXT PRIMARY KEY, client_id TEXT UNIQUE, proposal TEXT, source_mode TEXT,
                status TEXT, venue_order_id TEXT, venue_state TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS risk_evaluations (
                namespace TEXT, request_id TEXT, fingerprint TEXT, body TEXT,
                PRIMARY KEY (namespace, request_id)
            );
            CREATE TABLE IF NOT EXISTS run_claims (
                run_id TEXT, intent_id TEXT UNIQUE, reserved_notional TEXT,
                PRIMARY KEY (run_id, intent_id)
            );
            CREATE TABLE IF NOT EXISTS fills (intent_id TEXT PRIMARY KEY, body TEXT);
            CREATE TABLE IF NOT EXISTS marks (symbol TEXT PRIMARY KEY, body TEXT);
            CREATE TABLE IF NOT EXISTS cost_assessments (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, decision_id TEXT UNIQUE, body TEXT
            );
            CREATE TABLE IF NOT EXISTS exit_assessments (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, cycle_id TEXT UNIQUE, body TEXT
            );
        """)

    def close(self):
        self.db.close()

    def evaluation(self, namespace: str, request_id: str, fingerprint: str) -> dict | None:
        row = self.db.execute(
            "SELECT fingerprint,body FROM risk_evaluations WHERE namespace=? AND request_id=?",
            (namespace, request_id),
        ).fetchone()
        if row is None:
            return None
        if row["fingerprint"] != fingerprint:
            raise RequestConflictError("Request ID already belongs to a different effective intent")
        return json.loads(row["body"])

    def save_evaluation(self, namespace: str, fingerprint: str, body: dict, events: list[Event]) -> dict:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.evaluation(namespace, body["request_id"], fingerprint)
            if existing is not None:
                self.db.rollback()
                return existing
            for event in events:
                self.event(event)
            safe_body = self.sanitize(body)
            self.db.execute(
                "INSERT INTO risk_evaluations(namespace,request_id,fingerprint,body) VALUES (?,?,?,?)",
                (namespace, body["request_id"], fingerprint, json.dumps(safe_body)),
            )
            self.db.commit()
            return safe_body
        except BaseException:
            self.db.rollback()
            raise

    def sanitize(self, value):
        if isinstance(value, dict):
            return {
                k: (
                    "[REDACTED]"
                    if re.search(r"secret|passphrase|api.?key|token|authorization|private.?key", k, re.I)
                    else self.sanitize(v)
                )
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.sanitize(v) for v in value]
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
            return re.sub(r"evren_llm_[a-zA-Z0-9_-]+", "[REDACTED]", value)
        return value

    def event(self, event: Event) -> str:
        body = json.dumps(self.sanitize(event.model_dump(mode="json")))
        self.db.execute("INSERT INTO events(id,body) VALUES (?,?)", (event.id, body))
        return event.id

    def decision(self, decision: Decision):
        body = json.dumps(self.sanitize(decision.model_dump(mode="json")))
        self.db.execute(
            """INSERT INTO decisions(id,body) VALUES (?,?)
            ON CONFLICT(id) DO UPDATE SET body=excluded.body""",
            (decision.id, body),
        )

    def events(self, limit=100, after: str | None = None) -> list[dict]:
        if after is not None:
            # Unknown/expired cursors replay the retained history rather than silently dropping events.
            row = self.db.execute("SELECT seq FROM events WHERE id=?", (after,)).fetchone()
            rows = self.db.execute(
                "SELECT body FROM events WHERE seq>? ORDER BY seq LIMIT ?", (row["seq"] if row else 0, limit)
            ).fetchall()
        else:
            rows = reversed(
                self.db.execute("SELECT body FROM events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
            )
        return [json.loads(row["body"]) for row in rows]

    def decisions(self, limit=50) -> list[dict]:
        return [
            json.loads(row["body"])
            for row in self.db.execute(
                "SELECT body FROM decisions ORDER BY seq DESC LIMIT ?", (limit,)
            ).fetchall()
        ]

    def duplicate(self, intent_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM intents WHERE intent_id=?", (intent_id,)).fetchone() is not None

    def unresolved(self) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT * FROM intents WHERE status IN ('PENDING','UNKNOWN')"
            ).fetchall()
        ]

    def claim(
        self,
        proposal: Proposal,
        client_id: str,
        source_mode: str,
        pending_decision: Decision | None = None,
        *,
        run_id: str | None = None,
        reserved_notional: Decimal | None = None,
        max_run_notional: Decimal = Decimal("25"),
        max_run_orders: int = 1,
    ) -> bool:
        """Atomically prevent duplicate or concurrent unresolved external submissions."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.duplicate(proposal.intent_id) or self.unresolved():
                self.db.rollback()
                return False
            if run_id is not None:
                if reserved_notional is None or not reserved_notional.is_finite() or reserved_notional <= 0:
                    raise ValueError("A finite policy reservation is required")
                count, reserved = self.run_budget(run_id)
                if count >= max_run_orders or reserved + reserved_notional > max_run_notional:
                    self.db.rollback()
                    return False
                self.db.execute(
                    "INSERT INTO run_claims(run_id,intent_id,reserved_notional) VALUES (?,?,?)",
                    (run_id, proposal.intent_id, str(reserved_notional)),
                )
            self.db.execute(
                """INSERT INTO intents(intent_id,client_id,proposal,source_mode,status,updated_at)
                VALUES (?,?,?,?,?,?)""",
                (
                    proposal.intent_id,
                    client_id,
                    proposal.model_dump_json(),
                    source_mode,
                    "PENDING",
                    utcnow().isoformat(),
                ),
            )
            if pending_decision is not None:
                self.decision(pending_decision)
            self.db.commit()
            return True
        except BaseException:
            self.db.rollback()
            raise

    def run_budget(self, run_id: str) -> tuple[int, Decimal]:
        rows = self.db.execute(
            # A venue-rejected (FAILED) submission executed nothing, so it does not consume budget.
            """SELECT c.reserved_notional FROM run_claims c LEFT JOIN intents i ON i.intent_id=c.intent_id
            WHERE c.run_id=? AND COALESCE(i.status,'PENDING')!='FAILED'""",
            (run_id,),
        ).fetchall()
        return len(rows), sum((Decimal(r["reserved_notional"]) for r in rows), Decimal("0"))

    def order_status(
        self,
        intent_id: str,
        status: OrderStatus,
        venue_order_id: str | None = None,
        venue_state: str | None = None,
    ):
        self.db.execute(
            """UPDATE intents SET status=?,venue_order_id=?,venue_state=?,updated_at=?
            WHERE intent_id=?""",
            (status, venue_order_id, venue_state, utcnow().isoformat(), intent_id),
        )

    def record_fill(self, intent_id: str, fill: dict):
        """Upsert the venue-reported fill for one agent intent (cumulative per order).

        Re-reconciling the same order replaces its record, so repeated reads and partial-fill
        updates never add a second fill; a stale read can never shrink the cumulative fill.
        """
        row = self.db.execute("SELECT body FROM fills WHERE intent_id=?", (intent_id,)).fetchone()
        if row is not None:
            try:
                previous = Decimal(str(json.loads(row["body"]).get("filled_qty") or "0"))
                if Decimal(str(fill.get("filled_qty") or "0")) < previous:
                    return
            except (ArithmeticError, ValueError):
                pass
        body = json.dumps(self.sanitize(fill))
        self.db.execute(
            "INSERT INTO fills(intent_id,body) VALUES (?,?) ON CONFLICT(intent_id) DO UPDATE SET body=excluded.body",
            (intent_id, body),
        )

    def fill_intents(self, schema: int | None = None) -> set[str]:
        """Intents with a stored fill; with ``schema``, only records already at that schema."""
        return {
            row["intent_id"]
            for row in self.db.execute("SELECT intent_id, body FROM fills")
            if schema is None or json.loads(row["body"]).get("schema") == schema
        }

    def fills(self) -> list[dict]:
        return [json.loads(row["body"]) for row in self.db.execute("SELECT body FROM fills")]

    def verified_demo_intents(self) -> list[dict]:
        """Every agent-owned demo submission the venue confirmed, oldest first (no row cap)."""
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT intent_id, client_id, proposal, venue_order_id, status FROM intents
                WHERE source_mode='OKX_DEMO' AND status IN ('VERIFIED','PENDING') ORDER BY updated_at"""
            ).fetchall()
        ]

    def save_mark(self, observation) -> None:
        """Persist the latest venue ticker so valuation survives a restart, with its exchange time."""
        body = {
            "symbol": observation.symbol,
            "price": format(observation.price, "f"),
            "bid": format(observation.bid, "f"),
            "ask": format(observation.ask, "f"),
            "observed_at": observation.observed_at.isoformat(),
            "source": "OKX ticker last via official ATK",
        }
        self.db.execute(
            "INSERT INTO marks(symbol,body) VALUES (?,?) ON CONFLICT(symbol) DO UPDATE SET body=excluded.body",
            (observation.symbol, json.dumps(body)),
        )

    def mark(self, symbol: str = "BTC-USDT") -> dict | None:
        row = self.db.execute("SELECT body FROM marks WHERE symbol=?", (symbol,)).fetchone()
        return json.loads(row["body"]) if row else None

    def owned_demo_fills(self) -> tuple[list[dict], int]:
        """Fills the agent can prove it owns: its own demo intent, client ID and venue order ID."""
        owned, excluded = [], 0
        intents = {
            row["intent_id"]: dict(row)
            for row in self.db.execute(
                "SELECT intent_id, client_id, source_mode, venue_order_id FROM intents"
            ).fetchall()
        }
        for fill in self.fills():
            intent = intents.get(fill.get("intent_id"))
            if (
                fill.get("source_mode") != "OKX_DEMO"
                or intent is None
                or intent["source_mode"] != "OKX_DEMO"
                or intent["client_id"] != fill.get("decision_id")
                or (intent["venue_order_id"] and intent["venue_order_id"] != fill.get("ord_id"))
                or (fill.get("cl_ord_id") is not None and fill.get("cl_ord_id") != intent["client_id"])
            ):
                excluded += 1
                continue
            owned.append(fill)
        return owned, excluded

    def demo_pnl(self, *, now=None, mark_max_age_seconds: float = 60) -> dict | None:
        """Average-cost PnL of the agent's own verified demo fills (see ``aegis.pnl``).

        The mark is the persisted venue ticker with its exchange timestamp and age; a stale mark
        is reported as stale rather than presented as current.
        """
        # Local import: ML's offline replay loads this module with only models/policy/store present.
        from .pnl import compute, money

        fills, excluded = self.owned_demo_fills()
        if not fills:
            return None
        now = now or utcnow()
        stored = self.mark()
        mark_price, mark = None, None
        if stored:
            observed = datetime.fromisoformat(stored["observed_at"])
            age = (now - observed).total_seconds()
            mark_price = Decimal(stored["price"])
            mark = {
                **stored,
                "age_seconds": round(age, 3),
                "stale": not -2 <= age <= mark_max_age_seconds,
                "max_age_seconds": mark_max_age_seconds,
            }
        result = compute(fills, "BTC-USDT", mark_price)
        valuation = (
            "ACCOUNTING_INCOMPLETE"
            if result["inventory_qty"] is None
            else "CLOSED_NO_MARK_NEEDED"
            if result["inventory_qty"] == money(Decimal(0))
            else "NO_MARK"
            if mark is None
            else "STALE_MARK"
            if mark["stale"]
            else "CURRENT_MARK"
        )
        return {
            "schema_version": "aegis-demo-pnl-2",
            **result,
            "mark_price": money(mark_price),
            "mark": mark,
            "valuation_status": valuation,
            "excluded_unowned_fills": excluded,
            "method": "average-cost; fees in native currency (base fee adjusts inventory, quote fee adjusts "
            "cost/proceeds); verified OKX demo fills owned by agent intents only",
            "as_of": now.isoformat(),
        }

    def record_cost(self, decision_id: str, body: dict):
        self.db.execute(
            "INSERT OR REPLACE INTO cost_assessments(decision_id,body) VALUES (?,?)",
            (decision_id, json.dumps(self.sanitize(body))),
        )

    def cost_summary(self) -> dict:
        rows = [
            json.loads(r["body"])
            for r in self.db.execute("SELECT body FROM cost_assessments ORDER BY seq").fetchall()
        ]
        trades = [r for r in rows if r["assessment"]["status"] != "NOT_APPLICABLE"]
        reasons: dict[str, int] = {}
        for row in trades:
            for reason in row["assessment"]["reasons"]:
                reasons[reason] = reasons.get(reason, 0) + 1
        return {
            "schema_version": "aegis-cost-gate-1",
            "evaluated_trade_proposals": len(trades),
            "cost_approved": sum(r["assessment"]["approved"] for r in trades),
            "blocked_when_enforced": sum(
                r["enforced"] and not r["assessment"]["approved"] for r in trades
            ),
            "would_block_unenforced": sum(
                not r["enforced"] and not r["assessment"]["approved"] for r in trades
            ),
            "reason_counts": dict(sorted(reasons.items())),
            "latest": trades[-1] if trades else None,
        }

    def exit_inventory_basis(self) -> dict:
        """Identity of the owned inventory a shadow exit assessment is computed from (read-only).

        Any new or changed owned fill, or a change in unresolved demo intents, changes the
        fingerprint; reconcile wall-clock time does not, so an identical re-read is not a change.
        """
        fills, excluded = self.owned_demo_fills()
        unresolved = sorted(
            f"{row['intent_id']}:{row['status']}" for row in self.unresolved() if row["source_mode"] == "OKX_DEMO"
        )
        material = {
            "fills": sorted(
                json.dumps({k: v for k, v in fill.items() if k != "recorded_at"}, sort_keys=True) for fill in fills
            ),
            "unresolved": unresolved,
        }
        return {
            "fingerprint": hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest(),
            "owned_fill_count": len(fills),
            "excluded_unowned_fills": excluded,
            "unresolved_demo_orders": len(unresolved),
        }

    def record_exit_assessment(self, body: dict, *, keep: int = EXIT_ASSESSMENT_HISTORY):
        """One row per cycle (a repeated save of the same cycle replaces it); bounded history."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                """INSERT INTO exit_assessments(cycle_id,body) VALUES (?,?)
                ON CONFLICT(cycle_id) DO UPDATE SET body=excluded.body""",
                (body["cycle_id"], json.dumps(self.sanitize(body))),
            )
            self.db.execute(
                "DELETE FROM exit_assessments WHERE seq <= (SELECT MAX(seq) FROM exit_assessments) - ?", (keep,)
            )
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def latest_exit_assessment(self) -> dict | None:
        row = self.db.execute("SELECT body FROM exit_assessments ORDER BY seq DESC LIMIT 1").fetchone()
        return json.loads(row["body"]) if row else None

    def exit_shadow(self, *, now=None, max_age_seconds: float = 60, source_mode: str | None = None) -> dict:
        """Latest persisted shadow exit assessment with its freshness, for read-only display.

        Never recomputes a proposal, starts a cycle or calls the venue. A record older than the
        bound, from another source mode, or computed against a different owned inventory is
        reported as not current rather than as a current proposal. Record age and market age are
        judged separately: a capacity derived from an observation that has since outlived the
        record's market bound is not current, however young the record itself is.
        """
        now = now or utcnow()
        view = {
            "schema_version": "aegis-exit-shadow-read-1",
            "mode": "SHADOW",
            "orders_sent": False,
            "executable": False,
            "read_at": now.isoformat(),
            "max_age_seconds": max_age_seconds,
        }
        record = self.latest_exit_assessment()
        if record is None:
            return {**view, "state": "NO_ASSESSMENT", "current": False, "age_seconds": None,
                    "market_dependent": False, "market_age_seconds": None, "market_max_age_seconds": None,
                    "not_current_reasons": [], "assessment": None}
        reasons = []
        try:
            age = round((now - datetime.fromisoformat(record["computed_at"])).total_seconds(), 3)
        except (KeyError, TypeError, ValueError):
            age = None
        if age is None or not -2 <= age <= max_age_seconds:
            reasons.append("assessment_stale")
        proposal = record.get("proposal") or {}
        try:
            market_age = round((now - datetime.fromisoformat(proposal["market_observed_at"])).total_seconds(), 3)
        except (KeyError, TypeError, ValueError):
            market_age = None
        market_bound = record.get("market_max_age_seconds")
        if isinstance(market_bound, bool) or not isinstance(market_bound, (int, float)):
            market_bound = None
        # Lot/minimum outcomes and quantities come from the observation; inventory-only outcomes
        # (verified zero, unresolved order, uncertain accounting) do not depend on market data.
        market_dependent = proposal.get("lot_size") is not None or proposal.get("proposed_sell_btc") is not None
        if market_dependent:
            if market_bound is None:
                reasons.append("market_age_bound_missing")
            elif market_age is None or not -2 <= market_age <= market_bound:
                reasons.append("market_data_expired")
        if source_mode is not None and record.get("source_mode") != source_mode:
            reasons.append("source_mode_changed")
        if (record.get("inventory_basis") or {}).get("fingerprint") != self.exit_inventory_basis()["fingerprint"]:
            reasons.append("inventory_changed_since_assessment")
        state = (
            "CURRENT"
            if not reasons
            else "SUPERSEDED"
            if "inventory_changed_since_assessment" in reasons
            else "STALE"
        )
        return {**view, "state": state, "current": not reasons, "age_seconds": age,
                "market_dependent": market_dependent, "market_age_seconds": market_age,
                "market_max_age_seconds": market_bound, "not_current_reasons": reasons, "assessment": record}

    def metrics(self) -> dict:
        # Counts describe audit decisions, never fabricated profit or balances.
        # `pnl` stays null: account-level profit is not asserted. Demo PnL is
        # served separately from venue-confirmed fills at `/api/metrics/pnl`.
        rows = self.db.execute("SELECT body FROM decisions").fetchall()
        decisions = [json.loads(row["body"]) for row in rows]
        return {
            "decisions": len(decisions),
            "vetoed": sum(not d["risk_approved"] for d in decisions),
            "verified_exchange_orders": sum(
                d["execution_status"] == "VERIFIED" and d["source_mode"] == "OKX_DEMO" for d in decisions
            ),
            "mock_executions": sum(d["venue_state"] == "MOCK_FILLED" for d in decisions),
            "unresolved_orders": len(self.unresolved()),
            "pnl": None,
        }

    def finalize(self, decision: Decision):
        """The journal and dashboard decision must commit or roll back together."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            # A veto reusing an old intent must never overwrite that intent's prior outcome.
            self.db.execute(
                """UPDATE intents SET status=?,venue_order_id=?,venue_state=?,updated_at=?
                WHERE intent_id=? AND client_id=?""",
                (
                    decision.execution_status,
                    decision.venue_order_id,
                    decision.venue_state,
                    utcnow().isoformat(),
                    decision.intent_id,
                    decision.id,
                ),
            )
            self.decision(decision)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
