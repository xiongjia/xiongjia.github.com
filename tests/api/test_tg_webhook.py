"""Telegram webhook/command tests: allowlist gate, 3 commands, album
aggregation, completion push, update_id dedupe.

No network: a PTB ``Application`` is built with a fake token, sends are
captured via a mocked ``_send``, photo downloads are mocked, and
``execute_bot_task`` never spawns a real ``poe bot``.
"""

from __future__ import annotations

import asyncio

from telegram import Update

from api import state
from api.routers import tg as tg_module


def _cmd_entities(text: str) -> list:
    """bot_command entities — CommandHandler requires them to match."""
    if not text.startswith("/"):
        return []
    first = text.split(" ", 1)[0]
    return [{"type": "bot_command", "offset": 0, "length": len(first)}]


def _msg(
    update_id: int,
    chat_id: int,
    user_id: int,
    text: str | None = None,
    caption: str | None = None,
    photos: list | None = None,
    media_group_id: str | None = None,
) -> dict:
    msg = {
        "message_id": update_id,
        "date": 1700000000,
        "chat": {"id": chat_id, "type": "private"},
        "from": {"id": user_id, "first_name": "T", "is_bot": False},
    }
    if text is not None:
        msg["text"] = text
        msg["entities"] = _cmd_entities(text)
    if caption is not None:
        msg["caption"] = caption
        msg["caption_entities"] = _cmd_entities(caption)
    if photos is not None:
        msg["photo"] = photos
    if media_group_id is not None:
        msg["media_group_id"] = media_group_id
    return msg


def _photo(fid: str = "fid1", uid: str = "ufid1", size: int = 1000) -> dict:
    return {"file_id": fid, "file_unique_id": uid, "width": 100, "height": 100, "file_size": size}


class Harness:
    """Fresh PTB app per test; captures sends, runs and photo downloads."""

    def __init__(self, monkeypatch, allowed: str = "111, 222"):
        from telegram import Bot, User

        async def fake_get_me(self, *args, **kwargs):
            """Application.initialize() calls bot.get_me() — stub so tests
            never touch api.telegram.org. Sets ``_bot_user`` (Bot.username
            reads it via ``bot.bot``)."""
            self._bot_user = User(id=111, first_name="TestBot", is_bot=True, username="test_bot")
            return self._bot_user

        monkeypatch.setattr(Bot, "get_me", fake_get_me)
        monkeypatch.setattr(tg_module, "_app", None)
        monkeypatch.setattr(tg_module.tg_settings, "bot_token", "123456:test-token")
        monkeypatch.setattr(tg_module.tg_settings, "allowed_user_ids", allowed)
        self.sent: list[str] = []
        self.runs: list[tuple] = []
        self.downloaded: list[str] = []
        monkeypatch.setattr(tg_module, "_send", self._send)
        monkeypatch.setattr(tg_module, "_download_photo", self._download)
        monkeypatch.setattr(tg_module, "execute_bot_task", self._run)

    async def _send(self, chat_id: int, text: str) -> None:
        self.sent.append(text)

    async def _download(self, photo) -> str:
        self.downloaded.append(photo.file_id)
        return f"/tmp/tg_{photo.file_unique_id}.jpg"

    def _run(self, task: str, args: list[str], **kw):
        run = state.BotRun(run_id=f"r{len(self.runs)}", task=task, args=" ".join(args))
        run.chat_id = kw.get("chat_id")
        run.on_done = kw.get("on_done")
        self.runs.append((task, args, run.chat_id, run.on_done))
        return run

    def dispatch(self, *msg_dicts: dict) -> None:
        """process_update each message inside ONE event loop (album timers)."""

        async def go():
            app = tg_module.get_app()
            assert app is not None
            await app.initialize()
            try:
                for m in msg_dicts:
                    update = Update.de_json({"update_id": m["message_id"], "message": m}, app.bot)
                    await app.process_update(update)
                    await asyncio.sleep(0.05)  # async handlers are fire-and-forget
                await asyncio.sleep(tg_module.ALBUM_WAIT_S + 0.3)
            finally:
                await app.shutdown()

        asyncio.run(go())

    def run_once(self, task: str, args: list[str]) -> None:
        """Trigger _start_run and let the completion push fire on finish."""

        async def go():
            run = tg_module._start_run(111, task, args)
            run.finish("submitted", pr_url="https://github.com/x/pr/1")
            await asyncio.sleep(0)

        asyncio.run(go())


def test_denied_user_silently_ignored(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(1, 333, 333, text="/weight 82"))
    assert h.sent == []
    assert h.runs == []


def test_ping_replies_pong(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(15, 111, 111, text="/ping"))
    assert any("pong" in s for s in h.sent)
    assert h.runs == []


def test_ping_bypasses_allowlist(monkeypatch):
    """Config self-check: works even for a denied user, so first-time setup
    can tell a connection problem from an allowlist one."""
    h = Harness(monkeypatch)
    h.dispatch(_msg(16, 333, 333, text="/ping"))
    assert any("pong" in s for s in h.sent)
    assert h.runs == []


def test_help_lists_commands(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(17, 111, 111, text="/help"))
    assert any("/weight <kg>" in s for s in h.sent)
    assert h.runs == []


def test_help_bypasses_allowlist(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(18, 333, 333, text="/help"))
    assert any("Available commands" in s for s in h.sent)


def test_allowed_user_runs_weight(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(2, 111, 111, text="/weight 82"))
    assert h.runs == [("weight", ["82"], 111, h.runs[0][3])]
    assert any("Submitted" in s for s in h.sent)


def test_weight_no_args_usage(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(3, 111, 111, text="/weight"))
    assert h.runs == []
    assert any("Usage: /weight" in s for s in h.sent)


def test_weight_invalid_value(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(4, 111, 111, text="/weight abc"))
    assert h.runs == []
    assert any("Invalid weight" in s for s in h.sent)


def test_enu_joins_multi_word_text(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(5, 111, 111, text="/enu a cumbersome word"))
    assert h.runs[0][0] == "enu"
    assert h.runs[0][1] == ["a cumbersome word"]


def test_enu_no_args_usage(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(6, 111, 111, text="/enu"))
    assert h.runs == []
    assert any("Usage: /enu" in s for s in h.sent)


def test_moment_text_only(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(7, 111, 111, text="/moment morning run 5km"))
    assert h.runs[0][0] == "text-moment"
    assert h.runs[0][1] == ["morning run 5km"]
    assert h.downloaded == []


def test_moment_photo_caption_command(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(8, 111, 111, caption="/moment at the cafe", photos=[_photo(fid="f1")]))
    assert h.runs[0][0] == "text-moment"
    assert h.runs[0][1] == ["at the cafe", "--image=/tmp/tg_ufid1.jpg"]
    assert h.downloaded == ["f1"]


def test_moment_caption_mention_other_bot_ignored(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(24, 111, 111, caption="/moment@other_bot x", photos=[_photo(fid="c1")]))
    assert h.runs == []
    assert h.downloaded == []


def test_moment_caption_mention_self_works(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(
        _msg(25, 111, 111, caption="/moment@test_bot hi", photos=[_photo(fid="c2", uid="uc2")])
    )
    assert h.runs[0][1] == ["hi", "--image=/tmp/tg_uc2.jpg"]


def test_download_photo_prunes_stale(monkeypatch, tmp_path):
    """TG photo downloads must prune staging too (they bypass save_uploads)."""
    from pathlib import Path

    from telegram import PhotoSize

    pruned: list = []
    monkeypatch.setattr(tg_module, "prune_stale", lambda: pruned.append(1))
    monkeypatch.setattr(tg_module, "UPLOAD_DIR", tmp_path)

    class FakeFile:
        file_unique_id = "ud1"

        async def download_to_drive(self, custom_path):
            Path(custom_path).write_bytes(b"x")

    async def fake_get_file(self):
        return FakeFile()

    monkeypatch.setattr(PhotoSize, "get_file", fake_get_file)
    ps = PhotoSize.de_json(_photo(fid="d1", uid="ud1"), None)
    out = asyncio.run(tg_module._download_photo(ps))
    assert pruned
    assert out.endswith("tg_ud1.jpg")
    assert (tmp_path / "tg_ud1.jpg").exists()


def test_moment_photo_only_no_editor_flag(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(9, 111, 111, caption="/moment", photos=[_photo(fid="f2", uid="ufid2")]))
    assert h.runs[0][1] == ["", "--image=/tmp/tg_ufid2.jpg", "--no-editor"]


def test_album_aggregates_one_run(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(
        _msg(
            10,
            111,
            111,
            caption="/moment sunset",
            photos=[_photo(fid="a1", uid="ua1")],
            media_group_id="g1",
        ),
        _msg(11, 111, 111, photos=[_photo(fid="a2", uid="ua2")], media_group_id="g1"),
        _msg(12, 111, 111, photos=[_photo(fid="a3", uid="ua3")], media_group_id="g1"),
    )
    assert len(h.runs) == 1  # ONE run for the whole album
    task, args, chat_id, _ = h.runs[0]
    assert task == "text-moment"
    assert args == [
        "sunset",
        "--image=/tmp/tg_ua1.jpg",
        "--image=/tmp/tg_ua2.jpg",
        "--image=/tmp/tg_ua3.jpg",
    ]
    assert h.downloaded == ["a1", "a2", "a3"]


def test_single_non_command_photo_ignored(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(13, 111, 111, photos=[_photo(fid="f3")]))
    assert h.runs == []
    assert h.downloaded == []


def test_update_id_dedupe(monkeypatch):
    h = Harness(monkeypatch)
    msg = _msg(14, 111, 111, text="/weight 82")
    h.dispatch(msg)
    h.dispatch(msg)  # webhook retry — same update_id
    assert len(h.runs) == 1


def test_completion_push_on_finish(monkeypatch):
    h = Harness(monkeypatch)
    h.run_once("weight", ["82"])
    assert any("submitted" in s for s in h.sent)
    assert any("PR: https://github.com/x/pr/1" in s for s in h.sent)


def test_weight_nan_inf_rejected(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(21, 111, 111, text="/weight nan"))
    h.dispatch(_msg(22, 111, 111, text="/weight inf"))
    assert h.runs == []
    assert len([s for s in h.sent if "Invalid weight" in s]) == 2


def test_moment_empty_command_refused(monkeypatch):
    h = Harness(monkeypatch)
    h.dispatch(_msg(19, 111, 111, text="/moment"))
    assert h.runs == []
    assert any("nothing to create" in s for s in h.sent)


def test_moment_all_photos_fail_no_run(monkeypatch):
    h = Harness(monkeypatch)

    async def fail_download(photo):
        raise RuntimeError("download failed")

    monkeypatch.setattr(tg_module, "_download_photo", fail_download)
    h.dispatch(_msg(20, 111, 111, caption="/moment", photos=[_photo(fid="f9")]))
    assert h.runs == []
    assert any("photo failed" in s for s in h.sent)
    assert any("nothing to create" in s for s in h.sent)


def test_finish_survives_on_done_exception():
    run = state.BotRun(run_id="e", task="weight", args="82")

    def boom(run):
        raise RuntimeError("boom")

    run.on_done = boom
    run.finish("submitted")  # must not raise
    assert run.status == "submitted"


def test_finish_logs_on_done_failure(caplog):
    run = state.BotRun(run_id="e2", task="weight", args="82")

    def boom(run):
        raise RuntimeError("boom")

    run.on_done = boom
    with caplog.at_level("WARNING", logger="api.state"):
        run.finish("submitted")
    assert any("on_done" in r.message for r in caplog.records)


def test_album_flush_error_logged_not_fatal(monkeypatch, caplog):
    h = Harness(monkeypatch)

    async def boom_moment(chat_id, text, photos):
        raise RuntimeError("moment boom")

    monkeypatch.setattr(tg_module, "_run_moment", boom_moment)
    with caplog.at_level("WARNING", logger="api.tg"):
        h.dispatch(
            _msg(23, 111, 111, caption="/moment x", photos=[_photo(fid="b1")], media_group_id="g2")
        )
    assert any("album flush failed" in r.message for r in caplog.records)


class _BadJsonRequest:
    async def json(self):
        raise ValueError("not json")


def test_webhook_malformed_body_returns_ok(monkeypatch):
    Harness(monkeypatch)  # ensure the app exists (enabled token)
    result = asyncio.run(tg_module.webhook(_BadJsonRequest()))
    assert result == {"ok": True}
