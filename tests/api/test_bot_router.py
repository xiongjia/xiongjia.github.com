"""Router-level tests via FastAPI TestClient (fake runner, no real poe bot)."""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient


class FakeStream:
    def __init__(self, lines: list[str]):
        self._lines = [f"{line}\n".encode() for line in lines]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._lines:
            raise StopAsyncIteration
        return self._lines.pop(0)


class FakeProc:
    def __init__(self, lines: list[str], code: int = 0):
        self.stdout = FakeStream(lines)
        self._code = code

    async def wait(self) -> int:
        return self._code

    def terminate(self) -> None:
        pass


class FakeRunner:
    def __init__(self, lines: list[str] | None = None, code: int = 0, gate=None):
        self.argv: list[str] = []
        self.cwd = None
        self.gate = gate  # asyncio.Event: when set, run() blocks until released
        self.proc = FakeProc(lines or [], code)

    async def run(self, argv, cwd, env=None):
        self.argv = argv
        self.cwd = cwd
        self.env = env
        if self.gate is not None:
            await self.gate.wait()
        return self.proc


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from api import executor, history
    from api.server import app

    monkeypatch.setenv("BOT_API_STARTUP_CLEANUP", "false")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / ".bot-api-history.jsonl")
    monkeypatch.setattr(history, "REPO_ROOT", tmp_path)
    runner = FakeRunner(
        ["🌿 branch bot/weight/20260814-0109", "📦 Draft PR #142: https://github.com/x/pull/142"],
        code=0,
    )
    monkeypatch.setattr(executor, "runner", runner)
    with TestClient(app) as c:
        c._runner = runner  # type: ignore[attr-defined]
        yield c
    # clean up any leftover active runs between tests
    from api.state import active_runs

    active_runs.clear()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version(client, monkeypatch):
    monkeypatch.setenv("GIT_HASH", "abc1234")
    r = client.get("/api/version")
    assert r.json()["git_hash"] == "abc1234"


def test_tasks_and_schema(client):
    tasks = client.get("/api/tasks").json()["tasks"]
    assert "weight" in tasks
    schema = client.get("/api/schema/weight").json()
    assert schema["task"] == "weight"
    assert any(f["name"] == "value" for f in schema["fields"])
    assert client.get("/api/schema/nope").status_code == 404


def test_upload_images(client, tmp_path, monkeypatch):
    from api import uploads as up

    monkeypatch.setattr(up, "UPLOAD_DIR", tmp_path / "uploads")
    import base64

    payload = {
        "files": [
            {"name": "photo.png", "data": base64.b64encode(b"PNGDATA").decode()},
            {"name": "My Photo.jpg", "data": base64.b64encode(b"JPEG").decode()},
        ]
    }
    r = client.post("/api/upload", json=payload)
    assert r.status_code == 200
    paths = r.json()["files"]
    assert len(paths) == 2
    assert all(p.startswith(str(tmp_path / "uploads")) for p in paths)
    assert all(" " not in p for p in paths)  # spec-safe: no spaces
    saved = sorted((tmp_path / "uploads").iterdir())
    # the staging file keeps the author's name — no timestamp/uuid prefix
    assert {s.name for s in saved} == {"my_photo.jpg", "photo.png"}


def test_upload_rejects_unsupported(client):
    import base64

    r = client.post(
        "/api/upload",
        json={"files": [{"name": "notes.txt", "data": base64.b64encode(b"x").decode()}]},
    )
    assert r.status_code == 400
    assert "unsupported image type" in r.json()["detail"]


def test_upload_rejects_invalid_base64(client):
    r = client.post("/api/upload", json={"files": [{"name": "x.png", "data": "!!"}]})
    assert r.status_code == 400
    assert "invalid base64" in r.json()["detail"]


def test_upload_empty_list(client, tmp_path, monkeypatch):
    from api import uploads as up

    monkeypatch.setattr(up, "UPLOAD_DIR", tmp_path / "uploads")
    r = client.post("/api/upload", json={"files": []})
    assert r.status_code == 200
    assert r.json() == {"files": []}


def test_run_and_status(client):
    r = client.post("/api/bot/run", json={"task": "weight", "fields": {"value": 82.5}})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["stream_url"] == f"/api/bot/stream/{body['run_id']}"

    st = client.get(f"/api/bot/status/{body['run_id']}")
    assert st.status_code == 200
    assert st.json()["task"] == "weight"
    assert st.json()["args"] == "82.5"

    assert client.get("/api/bot/status/nope").status_code == 404


def test_run_field_validation(client):
    r = client.post("/api/bot/run", json={"task": "weight", "fields": {}})
    assert r.status_code == 422


def test_run_raw_args(client):
    r = client.post("/api/bot/run", json={"task": "weight", "args": ["83"]})
    assert r.json()["args"] == "83"


def test_run_handoff_only_ignores_auto_merge(client):
    # dev decision: never auto-merge — an auto_merge field sent by a client
    # is ignored (removed from the API contract) and --auto-merge never lands
    # in the engine argv
    r = client.post(
        "/api/bot/run",
        json={"task": "weight", "fields": {"value": 80}, "auto_merge": True},
    )
    assert r.status_code == 200
    for _ in range(100):  # wait for the background task to spawn
        if client._runner.argv:
            break
        __import__("time").sleep(0.01)
    assert "--handoff" in client._runner.argv
    assert "--auto-merge" not in client._runner.argv


def test_run_wait_ci_when_handoff_off(client):
    r = client.post(
        "/api/bot/run",
        json={"task": "weight", "fields": {"value": 80}, "handoff": False},
    )
    assert r.status_code == 200
    for _ in range(100):  # wait for the background task to spawn
        if client._runner.argv:
            break
        time.sleep(0.01)
    assert "--wait-ci" in client._runner.argv
    assert "--handoff" not in client._runner.argv


def test_run_subprocess_env_merges_not_replaces(client):
    # the PYTHONUNBUFFERED flag must be merged into the current env, not
    # replace it — a bare dict loses PATH and the `uv` exec fails ENOENT
    r = client.post("/api/bot/run", json={"task": "weight", "fields": {"value": 80}})
    assert r.status_code == 200
    for _ in range(100):  # wait for the background task to spawn
        if client._runner.argv:
            break
        time.sleep(0.01)
    env = client._runner.env
    assert env is not None
    assert env.get("PYTHONUNBUFFERED") == "1"
    assert env.get("PATH") == os.environ.get("PATH")


def test_run_unknown_task(client):
    r = client.post("/api/bot/run", json={"task": "nope"})
    assert r.status_code == 422


def test_stream_events(client):
    r = client.post("/api/bot/run", json={"task": "weight", "fields": {"value": 80}})
    run_id = r.json()["run_id"]
    with client.stream("GET", f"/api/bot/stream/{run_id}") as resp:
        assert resp.status_code == 200
        data = "".join(resp.iter_text())
    assert "RESET" in data
    assert "Draft PR" in data
    assert "DONE" in data


def test_stream_unknown(client):
    assert client.get("/api/bot/stream/nope").status_code == 404


def test_history_empty(client):
    r = client.get("/api/bot/history")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_history_running_then_finished(client, monkeypatch):
    # the contract auto-refresh depends on: a running run appears under
    # "running", and after completion moves to "records"
    import asyncio

    from api import executor

    gate = asyncio.Event()
    runner = FakeRunner(["📦 Draft PR #1: https://g/x/pull/1"], code=0, gate=gate)
    monkeypatch.setattr(executor, "runner", runner)

    r = client.post("/api/bot/run", json={"task": "weight", "fields": {"value": 80}})
    run_id = r.json()["run_id"]
    hist = client.get("/api/bot/history").json()
    assert any(x["run_id"] == run_id and x["status"] == "running" for x in hist["running"])

    gate.set()
    for _ in range(100):
        hist = client.get("/api/bot/history").json()
        if not any(x["run_id"] == run_id for x in hist["running"]):
            break
        time.sleep(0.01)
    assert any(x["run_id"] == run_id and x["status"] == "submitted" for x in hist["records"])


def test_abort(client):
    import asyncio

    from api import executor
    from api.state import active_runs

    gate = asyncio.Event()
    runner = FakeRunner([], code=0, gate=gate)
    executor.runner = runner  # keep the run blocked → status stays running

    r = client.post("/api/bot/run", json={"task": "weight", "fields": {"value": 80}})
    run_id = r.json()["run_id"]
    assert active_runs[run_id].status == "running"

    ar = client.post(f"/api/bot/abort/{run_id}")
    assert ar.status_code == 200
    assert ar.json()["status"] == "aborted"
    assert client.post("/api/bot/abort/nope").status_code == 404


def test_abort_status_not_overwritten_by_finish(client, monkeypatch):
    # regression: abort marks ABORTED, but the finishing _run_bot must not
    # overwrite it with FAILED/SUBMITTED afterwards
    import asyncio

    from api import executor
    from api import history as history_store
    from api.state import active_runs

    gate = asyncio.Event()
    runner = FakeRunner(
        ["🌿 branch bot/x/1", "📦 Draft PR #1: https://g/x/pull/1"], code=0, gate=gate
    )
    monkeypatch.setattr(executor, "runner", runner)

    r = client.post("/api/bot/run", json={"task": "weight", "fields": {"value": 80}})
    run_id = r.json()["run_id"]
    ar = client.post(f"/api/bot/abort/{run_id}")
    assert ar.json()["status"] == "aborted"

    gate.set()  # release the spawn — the run would finish "submitted" if unchecked
    for _ in range(100):
        if active_runs[run_id].status != "running":
            break
        time.sleep(0.01)
    assert active_runs[run_id].status == "aborted"  # not overwritten by _finalize
    records, _ = history_store.load()
    assert any(r["run_id"] == run_id and r["status"] == "aborted" for r in records)


def test_stream_heartbeat(client, monkeypatch):
    import asyncio
    import queue
    import threading

    from api import executor
    from api.routers import bot as bot_router

    monkeypatch.setattr(bot_router, "HEARTBEAT_S", 0.05)
    gate = asyncio.Event()
    runner = FakeRunner([], code=0, gate=gate)
    monkeypatch.setattr(executor, "runner", runner)

    r = client.post("/api/bot/run", json={"task": "weight", "fields": {"value": 80}})
    run_id = r.json()["run_id"]
    result = queue.Queue()

    def read_stream():
        with client.stream("GET", f"/api/bot/stream/{run_id}") as resp:
            result.put("".join(resp.iter_text()))

    t = threading.Thread(target=read_stream, daemon=True)
    t.start()
    time.sleep(0.5)  # several heartbeat ticks while the run is still running
    gate.set()  # finish the run so the stream closes
    t.join(timeout=5)
    data = result.get_nowait()
    assert ": ping" in data
    assert "DONE" in data


def test_static_console_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Bot Control Panel" in r.text
