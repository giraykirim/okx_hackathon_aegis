from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import SourceMode

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AEGIS_", env_file=ROOT / ".env", env_ignore_empty=True, extra="forbid"
    )
    source_mode: SourceMode = "MARKET_ONLY"
    db_path: Path = ROOT / "data" / "aegis.sqlite3"
    control_token: SecretStr | None = None
    service_api_key: SecretStr | None = None
    service_source_mode: Literal["MOCK", "MARKET_ONLY"] = "MARKET_ONLY"
    service_requests_per_minute: int = Field(default=6, ge=1, le=60)
    service_timeout_seconds: float = Field(default=30, gt=0, le=45)
    cycle_seconds: float = Field(default=10, ge=1, le=3600)
    cycle_timeout_seconds: float = Field(default=180, gt=0, le=300)
    mock_autonomous_scenario: Literal["normal", "no_trade", "laya_halt"] = "normal"
    okx_site: Literal["tr", "global", "eea", "us"] = "tr"
    atk_transport: Literal["mcp", "cli"] = "mcp"
    demo_enabled: bool = False
    demo_region_confirmed: bool = False
    okx_demo_api_key: SecretStr | None = None
    okx_demo_secret_key: SecretStr | None = None
    okx_demo_passphrase: SecretStr | None = None
    laya_url: str | None = None
    laya_token: SecretStr | None = None
    evren_base_url: str | None = "https://evren-llmapi.ssyz.org.tr/v1"
    evren_api_key: SecretStr | None = None
    evren_model: str | None = None

    def demo_ready(self) -> bool:
        return (
            self.source_mode == "OKX_DEMO"
            and self.demo_enabled
            and self.demo_region_confirmed
            and all(
                x and x.get_secret_value()
                for x in (self.okx_demo_api_key, self.okx_demo_secret_key, self.okx_demo_passphrase)
            )
        )
