"""Server configuration (pydantic-settings, ``BOT_API_*`` env vars).

``shared.env.load_env_files()`` already ran at package import, so ``.env`` /
``.env.local`` values (loaded with shell-env-wins precedence) are visible
here. No auth by design — the default bind is 0.0.0.0 so other machines on
a trusted network can reach it; pin ``BOT_API_HOST=127.0.0.1`` (or put it
behind a firewall / reverse proxy) when the network is not trusted.

Telegram settings come from ``TG_*`` env vars (separate class: the
``BOT_API_`` prefix is reserved for the server). An empty ``TG_BOT_TOKEN``
disables the bot — the API keeps working as a plain web management layer.
"""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOT_API_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8100
    # runtime data dir: history JSONL (+ rotation) and uploads staging.
    # Absolute path or repo-relative; default: repo-local .bot-api/
    log_dir: str = ".bot-api"


class TgSettings(BaseSettings):
    """Telegram bot config (``TG_*``). Empty token → bot disabled."""

    model_config = SettingsConfigDict(env_prefix="TG_", extra="ignore")

    bot_token: str = ""
    webhook_url: str = ""
    # optional unguessable webhook path segment; random at startup when
    # empty (nginx/tunnel can forward the whole /webhook/ prefix)
    webhook_path: str = ""
    mode: str = "polling"  # polling | webhook
    allowed_user_ids: str = ""  # comma-separated numeric Telegram user IDs
    # outbound proxy for api.telegram.org — reuses BOT_HTTP_PROXY (the
    # engine's convention) or an explicit TG_PROXY; PTB does NOT read
    # proxy env vars on its own, so this is plumbed into the builder
    proxy: str = Field(default="", validation_alias=AliasChoices("TG_PROXY", "BOT_HTTP_PROXY"))

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token)

    @property
    def allowed_ids(self) -> set[int]:
        """Parsed allowlist; malformed entries are dropped, not fatal."""
        out: set[int] = set()
        for part in self.allowed_user_ids.split(","):
            part = part.strip()
            if part:
                try:
                    out.add(int(part))
                except ValueError:
                    continue
        return out


settings = Settings()
tg_settings = TgSettings()
