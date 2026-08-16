"""Server configuration (pydantic-settings, ``BOT_API_*`` env vars).

``shared.env.load_env_files()`` already ran at package import, so ``.env`` /
``.env.local`` values (loaded with shell-env-wins precedence) are visible
here. No auth by design — the default bind is 0.0.0.0 so other machines on
a trusted network can reach it; pin ``BOT_API_HOST=127.0.0.1`` (or put it
behind a firewall / reverse proxy) when the network is not trusted.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOT_API_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8100
    # runtime data dir: history JSONL (+ rotation) and uploads staging.
    # Absolute path or repo-relative; default: repo-local .bot-api/
    log_dir: str = ".bot-api"


settings = Settings()
