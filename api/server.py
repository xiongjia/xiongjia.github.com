"""FastAPI app: system + bot routers, Telegram webhook, static console at ``/``."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.config import tg_settings
from api.lifespan import run_lifespan
from api.routers import bot, system, tg


def create_app() -> FastAPI:
    app = FastAPI(title="Bot Remote API", version="0.1.0", lifespan=run_lifespan)
    app.include_router(system.router)
    app.include_router(bot.router)
    if tg_settings.enabled:
        app.add_api_route(f"/webhook/{tg.webhook_path()}", tg.webhook, methods=["POST"])
    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
