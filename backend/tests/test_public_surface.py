import pytest
from fastapi.testclient import TestClient

from aegis.public_app import create_public_app
from aegis.settings import Settings


@pytest.mark.parametrize(
    "path",
    [
        "/api/agent/start",
        "/api/agent/stop",
        "/api/demo/scenario",
        "/api/events",
        "/api/snapshot",
        "/docs",
        "/openapi.json",
    ],
)
def test_public_surface_never_exposes_control_or_private_audit(tmp_path, path):
    surface = create_public_app(
        Settings(
            _env_file=None,
            db_path=tmp_path / "public.sqlite3",
            control_token="unit-control",
            service_api_key="unit-service",
        )
    )
    with TestClient(surface) as client:
        response = client.post(path, headers={"Authorization": "Bearer unit-control"}, json={})
        assert response.status_code == 404
        assert client.get(path).status_code == 404
        assert client.get("/api/health").json()["running"] is False


def test_public_service_health_metadata_and_auth_work(tmp_path):
    surface = create_public_app(
        Settings(_env_file=None, db_path=tmp_path / "public.sqlite3", service_api_key="unit-service")
    )
    with TestClient(surface) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/v1/service").json()["execution_authority"] is False
        request = {
            "request_id": "public-unit",
            "symbol": "BTC-USDT",
            "proposed_action": "BUY",
            "proposed_notional": "10",
        }
        assert client.post("/api/v1/risk/evaluate", json=request).status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"source_mode": "OKX_DEMO"},
        {"source_mode": "MOCK"},
        {"demo_enabled": True},
        {"demo_region_confirmed": True},
    ],
)
def test_public_runtime_rejects_exchange_execution_configuration(changes):
    with pytest.raises(ValueError):
        create_public_app(Settings(_env_file=None, **changes))


A2MCP_REQUEST = {
    "request_id": "a2mcp-unit",
    "symbol": "BTC-USDT",
    "proposed_action": "BUY",
    "proposed_notional": "10",
}


def public(tmp_path, **changes):
    return create_public_app(
        Settings(_env_file=None, db_path=tmp_path / "public.sqlite3", service_api_key="unit-service", **changes)
    )


def test_keyless_a2mcp_route_is_absent_unless_enabled(tmp_path):
    with TestClient(public(tmp_path)) as client:
        assert client.post("/api/v1/a2mcp/risk/evaluate", json=A2MCP_REQUEST).status_code == 404


def test_keyless_a2mcp_route_serves_assessment_and_rate_limits(tmp_path):
    surface = public(tmp_path, service_public_tier=True, service_public_requests_per_minute=1)
    with TestClient(surface) as client:
        first = client.post(
            "/api/v1/a2mcp/risk/evaluate", json=A2MCP_REQUEST, headers={"X-AEGIS-Key": "wrong"}
        )
        assert first.status_code == 200
        assert first.json()["request_id"] == "a2mcp-unit"
        assert "unit-service" not in first.text
        second = client.post("/api/v1/a2mcp/risk/evaluate", json={**A2MCP_REQUEST, "request_id": "b"})
        assert second.status_code == 429
        assert int(second.headers["Retry-After"]) >= 1
        # The keyed route still requires its credential.
        assert client.post("/api/v1/risk/evaluate", json=A2MCP_REQUEST).status_code == 401
