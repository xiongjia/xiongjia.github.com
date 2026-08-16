"""Telegram bot: allowlisted private bot for ``/weight``, ``/enu``, ``/moment``.

Only allowlisted users (``TG_ALLOWED_USER_IDS``) are answered — everyone
else is silently ignored (no reply, no hint the bot exists). Commands go
through the shared ``execute_bot_task()`` (the web console's path), never
``git_bot.py`` directly. Completion results are pushed one-way to the
issuing chat via the ``BotRun.on_done`` hook.

The PTB ``Application`` lifecycle (initialize/start + polling vs webhook)
lives in ``api/lifespan.py``; this module only defines the handlers and
the singleton accessor. ``POST /webhook/{secret}`` is mounted by
``api/server.py``.
"""

from __future__ import annotations

import asyncio
import logging
import math
import secrets
from collections import deque
from typing import TypedDict

from telegram import PhotoSize, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from api.config import tg_settings
from api.executor import execute_bot_task
from api.state import NOOP, BotRun
from api.uploads import MAX_UPLOAD_BYTES, UPLOAD_DIR, prune_stale, sanitize_name

logger = logging.getLogger("api.tg")

# cheap dedupe against Telegram webhook retries (5s timeout → same update
# delivered twice; a replayed /moment would otherwise run twice)
_SEEN_UPDATE_IDS: deque[int] = deque(maxlen=1000)


class _AlbumPending(TypedDict):
    chat_id: int
    text: str
    photos: list[list[PhotoSize]]


# album aggregation: media_group_id → pending; flushed ~ALBUM_WAIT_S after
# the first photo so the whole album lands in ONE moment run (Telegram
# delivers album members as separate updates)
_pending_albums: dict[str, _AlbumPending] = {}

ALBUM_WAIT_S = 1.0

_webhook_path: str | None = None


def webhook_path() -> str:
    """Unguessable webhook path segment.

    ``TG_WEBHOOK_PATH`` pins it (stable URL for nginx/tunnel config);
    otherwise a fresh random value per process (forward the whole
    ``/webhook/`` prefix and the value itself never needs to be known).
    """
    global _webhook_path
    if _webhook_path is None:
        _webhook_path = tg_settings.webhook_path.strip() or secrets.token_hex(16)
    return _webhook_path


def _seen(update: Update) -> bool:
    """True if this update_id was already handled (webhook retry dedupe)."""
    uid = update.update_id
    if uid in _SEEN_UPDATE_IDS:
        return True
    _SEEN_UPDATE_IDS.append(uid)
    return False


_app: Application | None = None


def get_app() -> Application | None:
    """PTB Application singleton; None when the bot is disabled (no token)."""
    global _app
    if _app is None:
        if not tg_settings.enabled:
            return None
        builder = Application.builder().token(tg_settings.bot_token)
        if tg_settings.proxy:
            # PTB does not read proxy env vars — plumb BOT_HTTP_PROXY
            # (or TG_PROXY) into both the API client and getUpdates
            builder = builder.proxy(tg_settings.proxy).get_updates_proxy(tg_settings.proxy)
        # The privoxy chain is slow (getMe took 2–10s) and getUpdates long-polls
        # for POLL_TIMEOUT_S — PTB's 5s defaults would time out both.
        builder = builder.read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30)
        _app = builder.build()
        _app.add_handler(CommandHandler("ping", cmd_ping))
        _app.add_handler(CommandHandler("help", cmd_help))
        _app.add_handler(CommandHandler("weight", cmd_weight))
        _app.add_handler(CommandHandler("enu", cmd_enu))
        _app.add_handler(CommandHandler("moment", cmd_moment))
        # photo moments: CommandHandler only matches message.text, but a
        # photo moment arrives as a caption command (``/moment …`` written
        # in the photo's caption) — handle it here, incl. album members
        _app.add_handler(MessageHandler(filters.PHOTO, on_photo_message))
    return _app


def _allowed(update: Update) -> bool:
    user = update.effective_user
    return user is not None and user.id in tg_settings.allowed_ids


async def _send(chat_id: int, text: str) -> None:
    app = get_app()
    if app is None:
        return
    try:
        await app.bot.send_message(chat_id=chat_id, text=text)
    except Exception as exc:
        logger.warning("tg send_message failed (chat %s): %s", chat_id, exc)


def _start_run(chat_id: int, task: str, args: list[str]) -> BotRun:
    """execute_bot_task with the one-way completion push attached."""

    def on_done(run) -> None:
        asyncio.get_running_loop().create_task(_push_result(chat_id, run))

    return execute_bot_task(task, args, chat_id=chat_id, on_done=on_done)


def _submitted_message(run) -> str:
    return (
        f"✅ Submitted: {run.task} {run.args}\n"
        f"Run ID: {run.run_id}\n"
        "Result will be pushed here when the run finishes."
    )


async def _push_result(chat_id: int, run) -> None:
    emoji = {"submitted": "📦", "merged": "✅", "failed": "❌", "aborted": "⏹", "noop": "⏭"}.get(
        run.status, "ℹ️"
    )
    lines = [f"{emoji} {run.task}: {run.status}", f"Run ID: {run.run_id}", f"Args: {run.args}"]
    if run.status == NOOP:
        lines.append("No changes (already recorded) — no PR created.")
    elif run.pr_url:
        lines.append(f"PR: {run.pr_url}")
    await _send(chat_id, "\n".join(lines))


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Config self-check: replies ``pong`` regardless of the allowlist.

    No side effects (no bot run) — a first-time setup can distinguish a
    connection/token problem (no reply at all) from an allowlist problem
    (other commands ignored but ping answers).
    """
    if _seen(update):
        return
    chat = update.effective_chat
    if chat is None:
        return
    await _send(chat.id, "pong")


HELP_TEXT = (
    "Available commands:\n"
    "/ping - connection self-check (always answers)\n"
    "/weight <kg> - record today's weight\n"
    "/enu <text> - add an English scrap\n"
    "/moment <text> [photos] - create a moment (text + optional photos)"
)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List the available commands (no side effects — like /ping, it also
    answers non-allowlisted accounts so setup is self-service)."""
    if _seen(update):
        return
    chat = update.effective_chat
    if chat is None:
        return
    await _send(chat.id, HELP_TEXT)


async def cmd_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _seen(update) or not _allowed(update):
        return
    chat = update.effective_chat
    if chat is None:
        return
    if not context.args:
        await _send(chat.id, "Usage: /weight <kg>\nExample: /weight 82.5")
        return
    value = context.args[0]
    try:
        num = float(value)
    except ValueError:
        await _send(chat.id, f"Invalid weight: {value!r}\nUsage: /weight <kg>")
        return
    if not math.isfinite(num):  # nan / inf would poison the weight data
        await _send(chat.id, f"Invalid weight: {value!r}\nUsage: /weight <kg>")
        return
    run = _start_run(chat.id, "weight", [value])
    await _send(chat.id, _submitted_message(run))


async def cmd_enu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _seen(update) or not _allowed(update):
        return
    chat = update.effective_chat
    if chat is None:
        return
    if not context.args:
        await _send(chat.id, "Usage: /enu <text>\nExample: /enu cumbersome")
        return
    run = _start_run(chat.id, "enu", [" ".join(context.args)])
    await _send(chat.id, _submitted_message(run))


async def cmd_moment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _seen(update) or not _allowed(update):
        return
    chat = update.effective_chat
    msg = update.effective_message
    if chat is None or msg is None:
        return
    if msg.photo:
        return  # photo moments go through on_photo_message (caption command)
    await _run_moment(chat.id, " ".join(context.args), [])


def _bot_username() -> str | None:
    """Our bot's username (for @-suffix command matching); None when the
    app isn't ready — a bare ``/moment`` still matches."""
    app = get_app()
    if app is None:
        return None
    try:
        return app.bot.username
    except Exception:
        return None


def _moment_caption_text(caption: str, bot_username: str | None = None) -> str | None:
    """Extract the /moment argument text from a photo caption.

    None → the caption is not a /moment command (photo ignored). Matches a
    bare ``/moment`` or ``/moment@<our-bot>`` — an @-mention of some OTHER
    bot is ignored (Telegram delivers @-suffixed commands for any bot).
    """
    head = caption.strip().split(" ", 1)[0]
    if head == "/moment":
        return caption.strip()[len(head) :].strip()
    if bot_username and head == f"/moment@{bot_username}":
        return caption.strip()[len(head) :].strip()
    return None


async def on_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Photo moments: a caption command (``/moment …``) on one photo or an
    album (media group, aggregated on ``media_group_id``).
    """
    if _seen(update) or not _allowed(update):
        return
    msg = update.effective_message
    if msg is None or not msg.photo:
        return
    chat = update.effective_chat
    if chat is None:
        return
    text = _moment_caption_text(msg.caption or "", _bot_username())
    gid = msg.media_group_id
    if gid:
        pending = _pending_albums.get(gid)
        if pending is None:
            if text is None:
                return  # album without a /moment caption — not a moment
            pending = _pending_albums[gid] = {
                "chat_id": chat.id,
                "text": text,
                "photos": [],
            }
            loop = asyncio.get_running_loop()
            loop.call_later(ALBUM_WAIT_S, lambda: _schedule_album_flush(gid))
            await _send(chat.id, "📸 Album received — building the moment…")
        elif text is not None:
            pending["text"] = text  # first caption is authoritative
        pending["photos"].append(list(msg.photo))
        return
    if text is None:
        return  # single photo without a /moment caption — ignored
    await _run_moment(chat.id, text, list(msg.photo))


async def _flush_album(gid: str) -> None:
    pending = _pending_albums.pop(gid, None)
    if pending is None:
        return
    photos = [plist[-1] for plist in pending["photos"]]  # largest size per photo
    await _run_moment(pending["chat_id"], pending["text"], photos)


def _schedule_album_flush(gid: str) -> None:
    """Fire the album flush on the current loop, logging unexpected errors
    (the task otherwise dies silently with a "never retrieved" warning)."""
    loop = asyncio.get_running_loop()
    task = loop.create_task(_flush_album(gid))
    task.add_done_callback(_log_album_flush_error)


def _log_album_flush_error(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.warning("album flush failed for a media group: %s", task.exception())


async def _run_moment(chat_id: int, text: str, photos: list[PhotoSize]) -> None:
    paths: list[str] = []
    for photo in photos:
        try:
            paths.append(await _download_photo(photo))
        except Exception as exc:
            await _send(chat_id, f"⚠ photo failed: {exc}")
    if not text and not paths:
        # nothing to publish: empty command (``/moment`` alone) or every
        # photo download failed — creating a content-less moment + PR is
        # worse than refusing
        await _send(chat_id, "⚠ nothing to create — no text and no photos")
        return
    args = [text or "", *[f"--image={p}" for p in paths]]
    if not text:
        args.append("--no-editor")  # photo-only moment: skip the EDITOR step
    run = _start_run(chat_id, "text-moment", args)
    await _send(chat_id, _submitted_message(run))


async def _download_photo(photo: PhotoSize) -> str:
    """Pull the largest photo size into ``.bot-api/uploads/`` (sanitized)."""
    if photo.file_size and photo.file_size > MAX_UPLOAD_BYTES:
        raise ValueError(f"photo exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
    file = await photo.get_file()
    name = sanitize_name(f"tg_{file.file_unique_id}.jpg")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    prune_stale()  # TG downloads bypass save_uploads — prune here too
    dest = UPLOAD_DIR / name
    await file.download_to_drive(custom_path=dest)
    return str(dest)


async def webhook(request) -> dict:
    """POST /webhook/{secret} → process_update (webhook mode).

    Always returns 200 even on processing errors — Telegram retries on
    non-200 and a replayed update would start a duplicate run (the
    update_id dedupe in the handlers is the second line of defense). The
    JSON parse / update decode are inside the try for the same reason: a
    malformed body must not 500 into a retry storm.
    """
    app = get_app()
    if app is None:
        return {"ok": False}
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
    except Exception as exc:
        logger.warning("tg update processing failed: %s", exc)
    return {"ok": True}
