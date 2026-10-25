import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from starlette._utils import get_route_path
from starlette.responses import JSONResponse, StreamingResponse

from .agent import Agent
from .models import (
    AwareDatetime,
    Capability,
    Classification,
    Decision,
    Event,
    Identity,
    Observation,
    SourceMode,
    StrictModel,
)
from .request_limits import RiskRequestLimit
from .risk_service import RiskService
from .service_models import (
    RiskAssessment,
    RiskEvaluationRequest,
    RiskEvaluationResponse,
    RiskRequest,
    ServiceInfo,
)
from .settings import Settings


class Health(StrictModel):
    status: Literal["ok"] = "ok"
    running: bool
    source_mode: SourceMode
    live_execution_enabled: Literal[False] = False


class ControlState(StrictModel):
    running: bool
    run_id: str
    source_mode: SourceMode


class ScenarioRequest(StrictModel):
    scenario: Literal[
        "normal",
        "stale_feed",
        "laya_halt",
        "excess_exposure",
        "invalid_quantity",
        "missing_approval",
        "unknown_order",
        "duplicate_intent",
    ]


class PnlMark(StrictModel):
    symbol: str
    price: str
    bid: str
    ask: str
    observed_at: AwareDatetime
    source: str
    age_seconds: float
    stale: bool
    max_age_seconds: float


class DemoPnl(StrictModel):
    """Additive, versioned demo PnL; the frozen Metrics.pnl stays null."""

    schema_version: Literal["aegis-demo-pnl-2"]
    # Accounting figures are null when an accounting issue makes them unknowable (see `issues`).
    realized: str | None
    unrealized: str | None
    net: str | None
    fees: str | None
    fee_breakdown: dict[str, str]
    inventory_qty: str | None
    cost_basis: str | None
    average_cost: str | None
    fill_count: int
    unmatched_sell_qty: str
    complete: bool
    issues: list[str]
    warnings: list[str]
    ledger: list[dict]
    mark_price: str | None
    mark: PnlMark | None
    valuation_status: Literal[
        "CURRENT_MARK", "STALE_MARK", "NO_MARK", "CLOSED_NO_MARK_NEEDED", "ACCOUNTING_INCOMPLETE"
    ]
    excluded_unowned_fills: int
    method: str
    as_of: AwareDatetime


class CostGateSummary(StrictModel):
    schema_version: Literal["aegis-cost-gate-1"]
    evaluated_trade_proposals: int
    cost_approved: int
    blocked_when_enforced: int
    would_block_unenforced: int
    reason_counts: dict[str, int]
    latest: dict | None


class ExitShadowRead(StrictModel):
    """Latest persisted SHADOW exit assessment; reading it never computes or sends anything."""

    schema_version: Literal["aegis-exit-shadow-read-1"]
    mode: Literal["SHADOW"]
    orders_sent: Literal[False]
    executable: Literal[False]
    read_at: AwareDatetime
    max_age_seconds: float
    state: Literal["NO_ASSESSMENT", "CURRENT", "STALE", "SUPERSEDED"]
    current: bool
    age_seconds: float | None
    # Age of the observation behind the capacity, at read time; judged apart from the record age.
    market_dependent: bool
    market_age_seconds: float | None
    market_max_age_seconds: float | None
    not_current_reasons: list[str]
    assessment: dict | None


class Metrics(StrictModel):
    decisions: int
    vetoed: int
    verified_exchange_orders: int
    mock_executions: int
    unresolved_orders: int
    pnl: None = None


class Snapshot(StrictModel):
    running: bool
    run_id: str
    source_mode: SourceMode
    last_cycle_at: AwareDatetime | None
    observation: Observation | None
    classification: Classification | None
    latest_decision: Decision | None
    capabilities: dict[str, Capability]
    identity: Identity
    execution_enabled: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.agent = Agent(settings or Settings())
        app.state.control_lock = asyncio.Lock()
        app.state.risk_service = RiskService(
            app.state.agent.settings,
            app.state.agent.store,
            evren_budget=app.state.agent.models.evren_budget,
        )
        agent_settings = app.state.agent.settings
        if agent_settings.autostart and agent_settings.source_mode in {"MARKET_ONLY", "MOCK"}:
            await app.state.agent.start()
        yield
        await app.state.risk_service.close()
        await app.state.agent.close()

    app = FastAPI(
        title="AEGIS Person 1 API",
        version="2.0.0",
        lifespan=lifespan,
        description="Off-chain demo-only agent runtime. ERC-8004 identity is a separate testnet registration.",
    )
    bearer = HTTPBearer(auto_error=False)
    app.add_middleware(RiskRequestLimit)

    @app.exception_handler(RequestValidationError)
    async def safe_service_validation(request: Request, exc: RequestValidationError):
        if get_route_path(request.scope) != "/api/v1/risk/evaluate":
            return await request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=422,
            content={
                "detail": [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
            },
        )

    def agent(request: Request) -> Agent:
        return request.app.state.agent

    def control_auth(
        runtime: Annotated[Agent, Depends(agent)],
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ):
        expected = runtime.settings.control_token
        if not expected or not expected.get_secret_value():
            raise HTTPException(503, "Control disabled: configure AEGIS_CONTROL_TOKEN locally")
        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not secrets.compare_digest(
                credentials.credentials.encode(), expected.get_secret_value().encode()
            )
        ):
            raise HTTPException(401, "Invalid control token", headers={"WWW-Authenticate": "Bearer"})

    Runtime = Annotated[Agent, Depends(agent)]
    service_key_header = APIKeyHeader(name="X-AEGIS-Key", scheme_name="AEGISServiceKey", auto_error=False)

    def service_auth(request: Request, supplied: Annotated[str | None, Depends(service_key_header)]):
        expected = request.app.state.agent.settings.service_api_key
        if not expected or not expected.get_secret_value():
            raise HTTPException(503, "Assessment service disabled: configure its separate key locally")
        if supplied is None or not secrets.compare_digest(
            supplied.encode(), expected.get_secret_value().encode()
        ):
            raise HTTPException(401, "Invalid assessment service credential")

    @app.get("/api/v1/service", response_model=ServiceInfo)
    async def service_info(request: Request):
        return request.app.state.risk_service.info()

    @app.post(
        "/api/v1/risk/evaluate",
        response_model=RiskEvaluationResponse | RiskAssessment,
        dependencies=[Depends(service_auth)],
        responses={
            408: {"description": "Request body deadline exceeded"},
            413: {"description": "Request exceeds 2048 bytes"},
            409: {"description": "Request ID already used for a different effective intent"},
            401: {"description": "Invalid service key"},
            429: {"description": "Busy or rate limited"},
            503: {"description": "Service key not configured"},
        },
    )
    async def evaluate_risk(body: RiskEvaluationRequest | RiskRequest, request: Request):
        if isinstance(body, RiskEvaluationRequest):
            return await request.app.state.risk_service.notional.evaluate(body)
        return await request.app.state.risk_service.evaluate(body)

    @app.get("/api/health", response_model=Health)
    async def health(runtime: Runtime):
        return Health(running=runtime.running, source_mode=runtime.settings.source_mode)

    @app.get("/api/snapshot", response_model=Snapshot)
    async def snapshot(runtime: Runtime):
        return runtime.snapshot()

    @app.get("/api/events", response_model=list[Event])
    async def events(runtime: Runtime, limit: int = Query(100, ge=1, le=1000)):
        return runtime.store.events(limit)

    @app.get("/api/decisions", response_model=list[Decision])
    async def decisions(runtime: Runtime, limit: int = Query(50, ge=1, le=500)):
        return runtime.store.decisions(limit)

    @app.get("/api/metrics", response_model=Metrics)
    async def metrics(runtime: Runtime):
        return runtime.store.metrics()

    @app.get("/api/metrics/pnl", response_model=DemoPnl | None)
    async def demo_pnl(runtime: Runtime):
        # Additive endpoint: the frozen Metrics schema keeps pnl=null. The mark is the persisted
        # venue ticker (survives restarts) with its exchange time and staleness.
        return runtime.store.demo_pnl(mark_max_age_seconds=runtime.settings.pnl_mark_max_age_seconds)

    @app.get("/api/metrics/cost-gate", response_model=CostGateSummary)
    async def cost_gate(runtime: Runtime):
        return runtime.store.cost_summary()

    @app.get("/api/metrics/exit-shadow", response_model=ExitShadowRead)
    async def exit_shadow(runtime: Runtime):
        # Operator read of the last cycle's SHADOW exit assessment: no cycle, venue call or order.
        return runtime.store.exit_shadow(
            max_age_seconds=runtime.settings.exit_shadow_max_age_seconds,
            source_mode=runtime.settings.source_mode,
        )

    @app.get("/api/web3/identity", response_model=Identity)
    async def identity():
        # Person 3 owns actual Fuji registration and independent owner/URI read-back.
        # No operator-supplied JSON can elevate this to verified.
        return Identity()

    @app.get("/api/capabilities", response_model=dict[str, Capability])
    async def capabilities(runtime: Runtime):
        return runtime.capabilities()

    @app.post("/api/agent/start", response_model=ControlState, dependencies=[Depends(control_auth)])
    async def start(request: Request, runtime: Runtime):
        async with request.app.state.control_lock:
            await runtime.start()
        return ControlState(
            running=runtime.running, run_id=runtime.run_id, source_mode=runtime.settings.source_mode
        )

    @app.post("/api/agent/stop", response_model=ControlState, dependencies=[Depends(control_auth)])
    async def stop(request: Request, runtime: Runtime):
        async with request.app.state.control_lock:
            await runtime.stop()
        return ControlState(
            running=runtime.running, run_id=runtime.run_id, source_mode=runtime.settings.source_mode
        )

    @app.post("/api/demo/scenario", response_model=Decision, dependencies=[Depends(control_auth)])
    async def scenario(body: ScenarioRequest, runtime: Runtime):
        if runtime.settings.source_mode != "MOCK":
            raise HTTPException(409, "Scenarios are available only in MOCK mode")
        return runtime.store.sanitize((await runtime.cycle(body.scenario)).model_dump(mode="json"))

    @app.get(
        "/api/stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "SSE event replay followed by new events; resume with Last-Event-ID.",
                "content": {"text/event-stream": {"schema": {"type": "string"}}},
            }
        },
    )
    async def stream(
        request: Request,
        runtime: Runtime,
        last_event_id: Annotated[str | None, Header(max_length=128)] = None,
    ):
        async def generate():
            cursor = last_event_id
            if cursor is None:
                batch = runtime.store.events(100)
            else:
                batch = runtime.store.events(100, after=cursor)
            heartbeat = 0
            while not await request.is_disconnected():
                for event in batch:
                    cursor = event["id"]
                    yield f"id: {cursor}\nevent: aegis\ndata: {json.dumps(event)}\n\n"
                if heartbeat % 15 == 0:
                    yield ": heartbeat\n\n"
                heartbeat += 1
                await asyncio.sleep(1)
                batch = runtime.store.events(100, after=cursor) if cursor else runtime.store.events(100)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
