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


def test_tg_defaults_disabled(monkeypatch):
    for key in ("TG_BOT_TOKEN", "TG_MODE", "TG_ALLOWED_USER_IDS"):
        monkeypatch.delenv(key, raising=False)
    from api.config import TgSettings

    tg = TgSettings()
    assert tg.enabled is False
    assert tg.mode == "polling"
    assert tg.allowed_ids == set()


def test_tg_env_maps_and_parses_allowlist(monkeypatch):
    from api.config import TgSettings

    monkeypatch.setenv("TG_BOT_TOKEN", "123456:abc")
    monkeypatch.setenv("TG_MODE", "webhook")
    monkeypatch.setenv("TG_WEBHOOK_URL", "https://bot.example.com/webhook")
    monkeypatch.setenv("TG_ALLOWED_USER_IDS", "111, 222, bad, 333")
    tg = TgSettings()
    assert tg.enabled is True
    assert tg.mode == "webhook"
    assert tg.allowed_ids == {111, 222, 333}  # malformed entry dropped
