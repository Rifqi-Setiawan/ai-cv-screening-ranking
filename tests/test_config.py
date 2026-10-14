import pytest
from pydantic import ValidationError

from src.infrastructure.config import Settings


def test_config_rejects_short_jwt_in_production():
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            JWT_SECRET="short",
            DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/db",
        )


def test_config_rejects_insecure_default_keywords_in_production():
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            JWT_SECRET="default-insecure-secret-key-change-in-production-12345",
            DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/db",
        )


def test_config_accepts_strong_secret():
    s = Settings(
        APP_ENV="production",
        JWT_SECRET="8058e8757806ab6d42d4127510a6d5b5691e11cf01f04e4a4dac2314846b035c",
        DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/db",
    )
    assert s.JWT_SECRET == "8058e8757806ab6d42d4127510a6d5b5691e11cf01f04e4a4dac2314846b035c"


def test_config_allows_test_env_bypass():
    s = Settings(
        APP_ENV="test",
        JWT_SECRET="short-test-secret",
        DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/db",
    )
    assert s.JWT_SECRET == "short-test-secret"
