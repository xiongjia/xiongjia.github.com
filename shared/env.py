"""Project .env loading with a defined precedence.

Loads git-ignored env files at repo root so developer-local settings (R2
credentials, bucket test overrides, analytics tokens) work without being
committed. Python's ``python-dotenv`` supplies the parser; this module owns
the precedence.

Precedence (highest first):

1. **shell / already-exported environment variables** — never overridden
2. ``.env.local`` — machine/user-specific overrides (git-ignored)
3. ``.env`` — shared defaults (git-ignored; the committed template is
   ``.env.example``)

Call ``load_env_files()`` early in any entrypoint that needs them (build
hooks, scripts). Build hooks are imported during ``load_config`` — after
mkdocs.yml's ``!ENV`` tags are resolved — so ``.env`` does **not** feed
``!ENV`` values; it does feed everything read at hook/script runtime (e.g.
``MKDOCS_BUCKET_ENABLED`` / ``MKDOCS_BUCKET_BASE_URL`` / R2 credentials).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent

# Order matters: later files override earlier ones (within .env universe).
ENV_FILES = (".env", ".env.local")


def load_env_files(root: Path | None = None) -> None:
    """Merge ``.env`` then ``.env.local`` into ``os.environ``.

    Existing environment variables (shell / CI) always win; missing keys are
    filled from ``.env.local`` first, then ``.env``. Missing files are ignored.
    """
    root = root or REPO_ROOT
    merged: dict[str, str] = {}
    for name in ENV_FILES:
        merged.update(dotenv_values(root / name))
    for key, value in merged.items():
        os.environ.setdefault(key, value)
