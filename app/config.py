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
    auto_create_schema: bool
    tutorial_version: int
    allowed_origins: tuple[str, ...]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

@lru_cache
def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./chs_recruta.db")
    environment = os.getenv("APP_ENV", "development").strip().lower()
    origins = tuple(item.strip() for item in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if item.strip())
    return Settings(
        app_name=os.getenv("APP_NAME", "CHS RH"),
        environment=environment,
        database_url=database_url,
        session_ttl_hours=max(1, int(os.getenv("SESSION_TTL_HOURS", "12"))),
        auto_create_schema=_as_bool(os.getenv("AUTO_CREATE_SCHEMA"), database_url.startswith("sqlite") and environment != "production"),
        tutorial_version=max(1, int(os.getenv("TUTORIAL_VERSION", "3"))),
        allowed_origins=origins,
    )
