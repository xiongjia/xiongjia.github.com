"""uvicorn launcher for the bot API server.

Usage:
    uv run poe api-server         # binds 0.0.0.0 by default (BOT_API_HOST overrides)
    uv run poe api-server-prod    # same as dev (alias)
    uv run poe api-server --local # every bot run uses THIS working tree (no worktree/PR)
    python scripts/api_server.py  # BOT_API_HOST / BOT_API_PORT from env
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from api.config import settings  # noqa: E402
from shared.env import load_env_files  # noqa: E402


def main() -> None:
    load_env_files()
    parser = argparse.ArgumentParser(description="Bot Remote API server")
    parser.add_argument("--host", default=None, help="bind host (default: BOT_API_HOST / 0.0.0.0)")
    parser.add_argument(
        "--port", type=int, default=None, help="bind port (default: BOT_API_PORT / 8100)"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="run EVERY bot task in the current working tree (no worktree/branch/PR) "
        "— for testing uncommitted changes; same as BOT_API_LOCAL=true",
    )
    args = parser.parse_args()

    if args.local:
        settings.local = True
    if settings.local:
        # export so child `poe bot` subprocesses see it too — the engine's
        # `is_local_mode()` + `do_submit()` guard then also refuse any PR,
        # whether local mode came from the flag or the env var
        os.environ["BOT_API_LOCAL"] = "true"
        print(
            "🧪 BOT_API_LOCAL: every bot run executes in this working tree "
            "(no worktree/branch/PR; edits stay uncommitted)"
        )

    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=args.host or settings.host,
        port=args.port or settings.port,
    )


if __name__ == "__main__":
    main()
