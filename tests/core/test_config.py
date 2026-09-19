import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base_kwargs() -> dict[str, object]:
    return {
        "postgres_password": "x" * 20,
        "jwt_secret_key": "y" * 32,
    }


def test_settings_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(**{**_base_kwargs(), "jwt_secret_key": "too-short"})


def test_settings_rejects_wildcard_cors_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(**{**_base_kwargs(), "cors_origins": ["*"]})


def test_settings_accepts_valid_values() -> None:
    settings = Settings(**{**_base_kwargs(), "cors_origins": ["https://example.com"]})

    assert settings.cors_origins == ["https://example.com"]
    assert "y" * 32 in settings.jwt_secret_key.get_secret_value()
