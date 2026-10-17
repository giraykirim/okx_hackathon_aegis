from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import SourceMode

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AEGIS_",
        env_file=ROOT / ".env",
        env_ignore_empty=True,
        extra="forbid",
        populate_by_name=True,
    )
    source_mode: SourceMode = "MARKET_ONLY"
    db_path: Path = ROOT / "data" / "aegis.sqlite3"
    control_token: SecretStr | None = None
    service_api_key: SecretStr | None = None
    service_source_mode: Literal["MOCK", "MARKET_ONLY"] = "MARKET_ONLY"
    service_requests_per_minute: int = Field(default=6, ge=1, le=60)
    service_timeout_seconds: float = Field(default=30, gt=0, le=45)
    # Key-less A2MCP tier for OKX.AI marketplace calls (OKX does not forward provider keys).
    service_public_tier: bool = False
    service_public_requests_per_minute: int = Field(default=3, ge=1, le=30)
    cycle_seconds: float = Field(default=10, ge=1, le=3600)
    cycle_timeout_seconds: float = Field(default=180, gt=0, le=300)
    max_run_orders: int = Field(default=1, ge=1, le=10)
    max_run_notional: Decimal = Field(default=Decimal("25"), gt=0, le=25, allow_inf_nan=False)
    # Caps risk-increasing BUYs only; demo accounts ship with large preloaded holdings.
    max_exposure_quote: Decimal = Field(default=Decimal("1000"), gt=0, le=1_000_000, allow_inf_nan=False)
    # OKX_DEMO only: "advisory" lets a LAYA HALT veto while abstention/low confidence does not block.
    laya_gate_demo: Literal["advisory", "required"] = "advisory"
    # Hosted read-only dashboards: start the loop at boot. Ignored unless MARKET_ONLY or MOCK.
    autostart: bool = False
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
    laya_timeout_seconds: float = Field(default=3, gt=0, le=15)
    laya_expected_version: str | None = Field(default=None, min_length=1, max_length=128)
    evren_base_url: str | None = Field(
        default=None, validation_alias=AliasChoices("EVREN_BASE_URL", "AEGIS_EVREN_BASE_URL")
    )
    evren_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("EVREN_API_KEY", "AEGIS_EVREN_API_KEY")
    )
    evren_model: str | None = Field(
        default=None, max_length=128, validation_alias=AliasChoices("EVREN_MODEL", "AEGIS_EVREN_MODEL")
    )
    evren_timeout_seconds: float = Field(
        default=10,
        gt=0,
        le=60,
        validation_alias=AliasChoices("EVREN_TIMEOUT_SECONDS", "AEGIS_EVREN_TIMEOUT_SECONDS"),
    )
    evren_max_requests_per_run: int = Field(
        default=6,
        ge=1,
        le=5000,
        validation_alias=AliasChoices("EVREN_MAX_REQUESTS_PER_RUN", "AEGIS_EVREN_MAX_REQUESTS_PER_RUN"),
    )
    evren_max_requests_per_minute: int = Field(
        default=12,
        ge=1,
        le=60,
        validation_alias=AliasChoices("EVREN_MAX_REQUESTS_PER_MINUTE", "AEGIS_EVREN_MAX_REQUESTS_PER_MINUTE"),
    )
    evren_max_tokens: int = Field(
        default=600,
        ge=64,
        le=4096,
        validation_alias=AliasChoices("EVREN_MAX_TOKENS", "AEGIS_EVREN_MAX_TOKENS"),
    )
    evren_max_response_bytes: int = Field(
        default=262144,
        ge=1024,
        le=262144,
        validation_alias=AliasChoices("EVREN_MAX_RESPONSE_BYTES", "AEGIS_EVREN_MAX_RESPONSE_BYTES"),
    )

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
