"""Shared pytest fixtures: make scripts/ and health macros importable.

The macros live under docs/notes/health/macros/ (loaded by the mkdocs macros
plugin at build time) and the CLI scripts under scripts/; tests import them
directly, so both directories are added to sys.path once here instead of in
every test file.
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "docs" / "notes" / "health" / "macros"))


@pytest.fixture()
def clear_bucket_env(monkeypatch):
    """Drop developer .env overrides (e.g. BUCKET_SYNC_REMOTE / BUCKET_UPLOAD_RULE)
    that may have leaked into os.environ from the calling process (bot CI gate
    loads .env) — the rclone tests assert default values."""
    for key in [k for k in os.environ if k.startswith(("BUCKET_SYNC_", "BUCKET_UPLOAD_"))]:
        monkeypatch.delenv(key, raising=False)
    return None


@pytest.fixture(autouse=True)
def tg_off(monkeypatch):
    """Never let the real Telegram bot start during tests.

    ``load_env_files()`` injects the developer's `.env.local` TG_* values
    into the test process, so a TestClient lifespan boot would call
    ``initialize()``/``start_polling()`` against api.telegram.org (network!).
    Force the token empty — TG tests re-enable it per-test with a fake token.
    """
    from api.config import tg_settings

    monkeypatch.setattr(tg_settings, "bot_token", "")
    monkeypatch.setattr(tg_settings, "allowed_user_ids", "")
