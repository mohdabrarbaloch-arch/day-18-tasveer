"""Application settings, loaded from the environment.

Every value has a safe development default so the app boots with zero setup,
but nothing secret is ever hardcoded — production values must come from env.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    app_name: str = "Tasveer"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    # --- Security ---
    secret_key: str = "dev-only-insecure-key-change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # --- Database ---
    # SQLite by default; set DATABASE_URL to a Postgres DSN in production.
    database_url: str = f"sqlite:///{BASE_DIR / 'tasveer.db'}"

    # --- CORS ---
    cors_origins: str = "*"

    # --- Rate limiting ---
    rate_limit_generate: str = "20/minute"
    rate_limit_default: str = "120/minute"

    # --- Storage ---
    storage_dir: Path = BASE_DIR / "storage" / "generated"
    # Where the built UI lives. Kept separate from storage_dir so tests can
    # point storage at a temp dir without losing the frontend.
    static_dir: Path = BASE_DIR / "static"
    max_upload_mb: int = 10

    # --- Generation ---
    # Credits granted to a new account.
    signup_credits: int = 60
    # How many images one generation request produces (Midjourney-style grid).
    grid_size: int = 4
    # Hard ceiling on output pixels so a request can never exhaust memory.
    max_output_pixels: int = 4_000_000

    # --- Optional remote provider ---
    # When set, generation is delegated to a real hosted model instead of the
    # built-in deterministic renderer. Left empty by default.
    image_provider: str = "local"  # "local" | "replicate" | "openai"
    replicate_api_token: str = ""
    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
