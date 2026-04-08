"""Application settings (env-driven)."""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Fast Home Tbilisi API"
    debug: bool = False

    # PostgreSQL (async SQLAlchemy) — required for API worker; bot-only can omit
    database_url: str | None = Field(
        default=None,
        description="postgresql+asyncpg://user:pass@host:5432/dbname",
    )

    # Telegram (used by backend for notifications; bot uses BOT_TOKEN too)
    bot_token: str = Field(..., description="Telegram bot token")
    admin_ids: str = Field(default="", description="Comma-separated Telegram user IDs")

    # Optional API protection (bot → backend)
    internal_api_key: str | None = Field(default=None, description="If set, required in X-Internal-Key")

    # TBC Pay — выключено по умолчанию, пока нет ключей от банка (см. docs/TBC_SETUP.md)
    tbc_enabled: bool = Field(default=False, description="Включить оплату через TBC tpay API")

    # Ручная оплата (пока TBC выключен): реквизиты для текста в боте
    iban_tbc: str | None = None
    iban_bog: str | None = None
    recipient_name: str | None = None

    # TBC Pay (нужны только при tbc_enabled=true)
    tbc_apikey: str | None = None
    tbc_client_id: str | None = None
    tbc_client_secret: str | None = None
    tbc_api_base: str = "https://api.tbcbank.ge"
    tbc_token_endpoint: str = "/v2/tpay/access-token"
    tbc_payments_endpoint: str = "/v1/tpay/payments"
    tbc_return_url: str = "https://example.com/payment/return"
    tbc_callback_url: str | None = Field(default=None, description="Public HTTPS URL for TBC webhook")

    # Webhook security (optional HMAC; if unset, only rate-limit + server-side verify)
    tbc_webhook_secret: str | None = None

    # Admin web (Basic auth)
    admin_username: str = "admin"
    admin_password: str = Field(default="change-me-in-prod", min_length=8)

    # Public base URL of this API (for links in admin)
    public_api_base: str = "http://127.0.0.1:8000"

    # Bot HTTP client
    backend_base_url: str = "http://127.0.0.1:8000"

    # Payment service fee amounts (GEL)
    price_urgent_gel: float = 79.0
    price_normal_gel: float = 59.0

    @property
    def admin_id_list(self) -> List[int]:
        if not self.admin_ids.strip():
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
