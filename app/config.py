from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache

def _as_bool(value: str | None, default: bool = False) -> bool:
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    environment: str
    database_url: str
    session_ttl_hours: int
    session_idle_minutes: int
    max_active_sessions: int
    security_secret_key: str
    password_reset_ttl_minutes: int
    password_reset_url: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    smtp_starttls: bool
    auto_create_schema: bool
    tutorial_version: int
    allowed_origins: tuple[str, ...]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def session_cookie_name(self) -> str:
        return "__Host-chs_session" if self.is_production else "chs_session"

@lru_cache
def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./chs_recruta.db")
    environment = os.getenv("APP_ENV", "development").strip().lower()
    origins = tuple(item.strip() for item in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if item.strip())
    configured_secret = os.getenv("SECURITY_SECRET_KEY")
    security_secret = configured_secret or "development-only-change-this-secret"
    password_reset_url = os.getenv("PASSWORD_RESET_URL", "http://127.0.0.1:8000/#reset_token={token}")
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()
    if environment == "production":
        if not configured_secret or len(configured_secret) < 32:
            raise RuntimeError("Defina SECURITY_SECRET_KEY com ao menos 32 caracteres em produção")
        reset_fragment = password_reset_url.partition("#")[2]
        if not password_reset_url.startswith("https://") or "{token}" not in reset_fragment:
            raise RuntimeError("PASSWORD_RESET_URL deve usar HTTPS e manter {token} no fragmento em produção")
        if not smtp_host or not smtp_from:
            raise RuntimeError("SMTP_HOST e SMTP_FROM são obrigatórios em produção")
    return Settings(
        app_name=os.getenv("APP_NAME", "CHS RH"),
        environment=environment,
        database_url=database_url,
        session_ttl_hours=max(1, int(os.getenv("SESSION_TTL_HOURS", "12"))),
        session_idle_minutes=max(5, int(os.getenv("SESSION_IDLE_MINUTES", "60"))),
        max_active_sessions=max(1, int(os.getenv("MAX_ACTIVE_SESSIONS", "5"))),
        security_secret_key=security_secret,
        password_reset_ttl_minutes=max(5, int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "20"))),
        password_reset_url=password_reset_url,
        smtp_host=smtp_host,
        smtp_port=max(1, int(os.getenv("SMTP_PORT", "587"))),
        smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=smtp_from,
        smtp_starttls=_as_bool(os.getenv("SMTP_STARTTLS"), True),
        auto_create_schema=_as_bool(os.getenv("AUTO_CREATE_SCHEMA"), database_url.startswith("sqlite") and environment != "production"),
        tutorial_version=max(1, int(os.getenv("TUTORIAL_VERSION", "5"))),
        allowed_origins=origins,
    )
