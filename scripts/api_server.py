"""uvicorn launcher for the bot API server.

Usage:
    uv run poe api-server           # BOT_API_HOST/BOT_API_PORT from env
    uv run poe api-server-prod      # --host 0.0.0.0 (port from env)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from api.config import settings  # noqa: E402
from shared.env import load_env_files  # noqa: E402


def main() -> None:
    load_env_files()
    parser = argparse.ArgumentParser(description="Bot Remote API server")
    parser.add_argument(
        "--host", default=None, help="bind host (default: BOT_API_HOST / 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="bind port (default: BOT_API_PORT / 8100)"
    )
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=args.host or settings.host,
        port=args.port or settings.port,
    )


if __name__ == "__main__":
    main()
