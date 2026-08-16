"""Tests for api.config Settings: default bind 0.0.0.0, BOT_API_* env overrides.

The API has no auth by design, so the bind address is the trust boundary:
default is all interfaces (0.0.0.0) and ``BOT_API_HOST`` must be able to
pin it back to localhost. These tests lock in that contract.
"""

from __future__ import annotations

from api.config import Settings


def test_default_binds_all_interfaces(monkeypatch):
    monkeypatch.delenv("BOT_API_HOST", raising=False)
    monkeypatch.delenv("BOT_API_PORT", raising=False)
    settings = Settings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 8100


def test_bot_api_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("BOT_API_HOST", "127.0.0.1")
    monkeypatch.setenv("BOT_API_PORT", "9999")
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 9999
