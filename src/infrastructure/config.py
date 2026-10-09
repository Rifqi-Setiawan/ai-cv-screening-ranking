"""Application settings and configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "production"
    APP_PORT: int = 8110
    APP_HOST: str = "127.0.0.1"

    # Database
    DATABASE_URL: str = "postgresql://cv_screening_user:59Vf0GijbEHFxZyfUHsjoJs9@127.0.0.1:5432/cv_screening"
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 10

    # JWT Auth
    JWT_SECRET: str = "default-insecure-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Storage
    STORAGE_VAULT_PATH: str = "/srv/hermes-control/services/cv-screening/data/cv-vault"
    MAX_UPLOAD_SIZE_MB: int = 10

    # LLM Data Policy
    # 'redacted_dev_router' enables 9Router for development with automated PII pre-flight verification
    # 'paid_or_local_only' disables unmetered dev router and restricts calls to official metered APIs / local models
    LLM_DATA_POLICY: str = "redacted_dev_router"
    LLM_GATEWAY_URL: str = "http://127.0.0.1:20128/v1"
    LLM_GATEWAY_KEY: str = ""
    LLM_MODEL_JD_COMPILER: str = "ag/gemini-3.8-flash-high"
    LLM_TEMPERATURE: float = 0.0

    # Embedding
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384


settings = Settings()
