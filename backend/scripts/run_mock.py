"""Start isolated loopback MOCK runtime and notional service; keep local keys off screen."""

import argparse
import os

import uvicorn

from aegis.app import create_app
from aegis.settings import ROOT, Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    local = Settings()
    if not local.control_token or not local.service_api_key:
        raise SystemExit("Run uv run python -m scripts.init_local first")
    mock = Settings(
        _env_file=None,
        source_mode="MOCK",
        service_source_mode="MOCK",
        mock_autonomous_scenario="no_trade",
        db_path=ROOT / "data/mock-acceptance.sqlite3",
        control_token=local.control_token,
        service_api_key=local.service_api_key,
        service_requests_per_minute=6,
        demo_enabled=False,
        demo_region_confirmed=False,
        okx_demo_api_key=None,
        okx_demo_secret_key=None,
        okx_demo_passphrase=None,
        laya_url=None,
        laya_token=None,
        evren_base_url=None,
        evren_api_key=None,
        evren_model=None,
    )
    path = ROOT / "data/mock-service.curl"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write('header = "X-AEGIS-Key: ' + local.service_api_key.get_secret_value() + '"\n')
    path.chmod(0o600)
    print("MOCK autonomous NO_TRADE + notional service; real integrations are not certified.")
    print("Local curl credential config saved under ignored backend/data/; values are not displayed.")
    uvicorn.run(create_app(mock), host="127.0.0.1", port=args.port, workers=1, access_log=False)


if __name__ == "__main__":
    main()
