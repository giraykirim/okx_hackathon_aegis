import json
import re
import sqlite3
from pathlib import Path

from .models import Decision, Event, OrderStatus, Proposal, utcnow


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
        self, proposal: Proposal, client_id: str, source_mode: str, pending_decision: Decision | None = None
    ) -> bool:
        """Atomically prevent duplicate or concurrent unresolved external submissions."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.duplicate(proposal.intent_id) or self.unresolved():
                self.db.rollback()
                return False
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

    def metrics(self) -> dict:
        # Counts describe audit decisions, never fabricated profit or balances.
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
