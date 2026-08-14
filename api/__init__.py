"""Remote API service (thin shell over ``scripts/git_bot.py``).

Importing this package bootstraps the repo root onto ``sys.path`` (same
pattern as every script) and loads the developer env files, so any
``import api.*`` works regardless of the current working directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.env import load_env_files  # noqa: E402

load_env_files()
