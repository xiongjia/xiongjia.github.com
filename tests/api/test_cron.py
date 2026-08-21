"""Cron scheduling tests: config validation, spec execution, router, overlap guard.

Router tests drive the real FastAPI app through TestClient — the lifespan
starts the APScheduler (BOT_API_CRON_ENABLED defaults true), so
``GET /api/cron`` exercises the real mkdocs.yml ``extra.bot.cron`` config.
No cron fire can happen (none of the schedules match the test clock);
``execute_bot_spec`` uses the FakeRunner, so no real ``poe bot`` spawns.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from api import cron as cron_scheduler
from api.state import RUNNING, SUBMITTED


class FakeProc:
    stdout = None  # _run_bot checks ``proc.stdout is not None`` before reading

    async def wait(self) -> int:
        return 0


class FakeRunner:
    def __init__(self):
        self.argv: list[str] | None = None

    async def run(self, argv, cwd, env=None):
        self.argv = argv
        return FakeProc()


# ---------------------------------------------------------------------------
#  Config loading + fail-fast validation (monkeypatched extra.bot.cron)
# ---------------------------------------------------------------------------


@pytest.fixture()
def cron_cfg(monkeypatch):
    """Point ``api.cron.load_extra`` at a controlled ``extra.bot`` config.

    Usage: ``cron_cfg({...})`` with the ``cron`` mapping directly.
    """

    def _set(jobs: dict) -> None:
        monkeypatch.setattr(cron_scheduler, "load_extra", lambda *a, **k: {"cron": jobs})

    _set({})
    return _set


def test_load_jobs(cron_cfg):
    cron_cfg(
        {
            "daily-sync-running": {
                "schedule": "0 12 * * *",
                "spec": "sync-running + sync-splits --confirm",
            },
            "weekly-health-summary": {
                "schedule": "0 8 * * 6",
                "spec": "health-summary",
                "handoff": False,
                "timezone": "Asia/Shanghai",
            },
        }
    )
    jobs = cron_scheduler.load_cron_config()
    assert set(jobs) == {"daily-sync-running", "weekly-health-summary"}
    j = jobs["daily-sync-running"]
    assert j.schedule == "0 12 * * *"
    assert j.spec == "sync-running + sync-splits --confirm"
    assert j.handoff is True
    assert j.enabled is True
    assert jobs["weekly-health-summary"].handoff is False
    assert jobs["weekly-health-summary"].timezone == "Asia/Shanghai"


def test_bad_schedule(cron_cfg):
    cron_cfg({"j": {"schedule": "61 * * * *", "spec": "hello"}})
    with pytest.raises(cron_scheduler.CronConfigError):
        cron_scheduler.load_cron_config()


def test_unknown_task_in_spec(cron_cfg):
    cron_cfg({"j": {"schedule": "0 12 * * *", "spec": "nope"}})
    with pytest.raises(cron_scheduler.CronConfigError):
        cron_scheduler.load_cron_config()


def test_bad_field_type(cron_cfg):
    cron_cfg({"j": {"schedule": "0 12 * * *", "spec": "hello", "handoff": "yes"}})
    with pytest.raises(cron_scheduler.CronConfigError):
        cron_scheduler.load_cron_config()


def test_missing_fields(cron_cfg):
    cron_cfg({"j": {}})
    with pytest.raises(cron_scheduler.CronConfigError):
        cron_scheduler.load_cron_config()


def test_non_mapping_job(cron_cfg):
    cron_cfg({"j": "0 12 * * *"})
    with pytest.raises(cron_scheduler.CronConfigError):
        cron_scheduler.load_cron_config()


def test_real_mkdocs_config_has_pilot_jobs():
    """The committed mkdocs.yml must carry the two pilot jobs + the hello
    smoke job — this is what the scheduler registers at startup.

    Deliberately coupled to the production config (this is the smoke
    contract): removing/renaming a job in mkdocs.yml fails here on purpose."""
    jobs = cron_scheduler.load_cron_config()
    assert "daily-sync-running" in jobs
    assert "weekly-health-summary" in jobs
    assert "smoke-hello" in jobs
    assert jobs["daily-sync-running"].spec == "sync-running + sync-splits --confirm"
    assert jobs["smoke-hello"].spec == "hello"


# ---------------------------------------------------------------------------
#  execute_bot_spec (raw-spec executor entry)
# ---------------------------------------------------------------------------


def test_execute_bot_spec_composite(monkeypatch):
    from api import executor
    from api.state import active_runs

    runner = FakeRunner()
    monkeypatch.setattr(executor, "runner", runner)

    async def scenario():
        run = executor.execute_bot_spec("sync-running + sync-splits --confirm")
        for _ in range(100):
            if runner.argv:
                break
            await asyncio.sleep(0.01)
        return run

    run = asyncio.run(scenario())
    assert run.task == "sync-running + sync-splits --confirm"
    assert run.status == SUBMITTED
    assert runner.argv == [
        "uv",
        "run",
        "poe",
        "bot",
        "run",
        "sync-running + sync-splits --confirm",
        "--handoff",
    ]
    active_runs.clear()


def test_execute_bot_spec_handoff_off(monkeypatch):
    from api import executor
    from api.state import active_runs

    runner = FakeRunner()
    monkeypatch.setattr(executor, "runner", runner)

    async def scenario():
        run = executor.execute_bot_spec("hello", handoff=False)
        for _ in range(100):
            if runner.argv:
                break
            await asyncio.sleep(0.01)
        return run

    asyncio.run(scenario())
    assert runner.argv[-1] == "--wait-ci"
    active_runs.clear()


def test_execute_bot_spec_unknown(monkeypatch):
    from api import executor

    monkeypatch.setattr(executor, "runner", FakeRunner())
    # validation happens before any event loop is needed
    with pytest.raises(ValueError):
        executor.execute_bot_spec("nope")


# ---------------------------------------------------------------------------
#  Router (real app + real mkdocs.yml cron config)
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from api import executor, history
    from api.server import app

    monkeypatch.setenv("BOT_API_STARTUP_CLEANUP", "false")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "h.jsonl")
    monkeypatch.setattr(history, "REPO_ROOT", tmp_path)
    runner = FakeRunner()
    monkeypatch.setattr(executor, "runner", runner)
    with TestClient(app) as c:
        c._runner = runner  # type: ignore[attr-defined]
        yield c
    from api.state import active_runs

    active_runs.clear()


def test_cron_list_shape(client):
    r = client.get("/api/cron")
    assert r.status_code == 200
    jobs = {j["name"]: j for j in r.json()["jobs"]}
    assert "daily-sync-running" in jobs
    j = jobs["daily-sync-running"]
    assert j["schedule"] == "0 12 * * *"
    assert j["spec"] == "sync-running + sync-splits --confirm"
    assert j["handoff"] is True
    assert j["enabled"] is True
    # scheduler started in the lifespan → next fire is known
    assert j["next_run_at"] is not None


def test_cron_manual_run(client):
    r = client.post("/api/cron/daily-sync-running/run")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["task"] == "sync-running + sync-splits --confirm"
    assert body["stream_url"].startswith("/api/bot/stream/")
    for _ in range(100):  # wait for the background task to spawn
        if client._runner.argv:  # type: ignore[attr-defined]
            break
        time.sleep(0.01)
    assert client._runner.argv[-1] == "--handoff"  # type: ignore[attr-defined]


def test_cron_manual_unknown(client):
    assert client.post("/api/cron/nope/run").status_code == 404


def test_cron_disabled(monkeypatch, tmp_path):
    from api import executor, history
    from api.server import app

    monkeypatch.setenv("BOT_API_STARTUP_CLEANUP", "false")
    monkeypatch.setenv("BOT_API_CRON_ENABLED", "false")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "h.jsonl")
    monkeypatch.setattr(history, "REPO_ROOT", tmp_path)
    runner = FakeRunner()
    monkeypatch.setattr(executor, "runner", runner)
    with TestClient(app) as c:
        r = c.get("/api/cron")
        assert r.status_code == 200
        jobs = r.json()["jobs"]
        assert jobs  # config is still listed…
        assert all(j["next_run_at"] is None for j in jobs)  # …but scheduling is off


# ---------------------------------------------------------------------------
#  Runtime enable/disable (state persisted in .bot-api/cron-state.json)
# ---------------------------------------------------------------------------


def test_disable_persists_to_state_file(tmp_path):
    import json

    from api import history as history_store

    # conftest's isolated_history already points history.LOG_DIR at tmp_path
    assert cron_scheduler.set_disabled("smoke-hello", True) is True
    assert "smoke-hello" in cron_scheduler.disabled_jobs()
    state = json.loads((history_store.LOG_DIR / "cron-state.json").read_text(encoding="utf-8"))
    assert "smoke-hello" in state
    assert "disabled_at" in state["smoke-hello"]  # auditable timestamp
    # re-read reflects the override (no in-memory cache → fresh reads see it)
    assert cron_scheduler.set_disabled("smoke-hello", False) is False
    assert cron_scheduler.disabled_jobs() == set()
    assert json.loads((history_store.LOG_DIR / "cron-state.json").read_text(encoding="utf-8")) == {}


def test_is_active_with_override(monkeypatch, cron_cfg):
    cron_cfg({"j": {"schedule": "0 12 * * *", "spec": "hello"}})
    job = cron_scheduler.load_cron_config()["j"]
    assert cron_scheduler.is_active(job) is True
    cron_scheduler.set_disabled("j", True)
    assert cron_scheduler.is_active(job) is False
    cron_scheduler.set_disabled("j", False)
    assert cron_scheduler.is_active(job) is True


def test_last_run_falls_back_to_history(monkeypatch, cron_cfg):
    """After a restart (_last_run empty) the last run still shows — resolved
    from the JSONL history by matching the job's spec (cron runs record the
    raw spec as the run task)."""
    from api import history as history_store

    cron_cfg({"smoke-hello": {"schedule": "0 13 * * *", "spec": "hello"}})
    cron_scheduler._last_run.clear()
    history_store.append(
        {
            "run_id": "abc123",
            "task": "hello",
            "args": "",
            "status": "submitted",
            "started_at": "2026-08-21T10:00:00+08:00",
            "finished_at": "2026-08-21T10:03:00+08:00",
            "pr_url": "https://github.com/x/y/pull/1",
        }
    )
    info = cron_scheduler.last_run_info("smoke-hello")
    assert info is not None
    assert info["run_id"] == "abc123"
    assert info["status"] == "submitted"
    assert info["started_at"] == "2026-08-21T10:00:00+08:00"
    assert info["pr_url"] == "https://github.com/x/y/pull/1"
    # a different job (different spec) does not match
    assert cron_scheduler.last_run_info("weekly-health-summary") is None


def test_cron_disable_enable(client):
    # disable: paused → stops firing, next_run_at goes null
    r = client.post("/api/cron/daily-sync-running/disable")
    assert r.status_code == 200
    assert r.json() == {"name": "daily-sync-running", "disabled": True}
    jobs = {j["name"]: j for j in client.get("/api/cron").json()["jobs"]}
    assert jobs["daily-sync-running"]["disabled"] is True
    assert jobs["daily-sync-running"]["active"] is False
    assert jobs["daily-sync-running"]["next_run_at"] is None
    # enable: resumed → next run restored
    r = client.post("/api/cron/daily-sync-running/enable")
    assert r.json() == {"name": "daily-sync-running", "disabled": False}
    jobs = {j["name"]: j for j in client.get("/api/cron").json()["jobs"]}
    assert jobs["daily-sync-running"]["disabled"] is False
    assert jobs["daily-sync-running"]["active"] is True
    assert jobs["daily-sync-running"]["next_run_at"] is not None


def test_cron_disable_enable_unknown(client):
    assert client.post("/api/cron/nope/disable").status_code == 404
    assert client.post("/api/cron/nope/enable").status_code == 404


def test_start_skips_disabled_but_enable_registers(monkeypatch, cron_cfg):
    """A job runtime-disabled at startup is not scheduled; enabling it
    re-registers on the fly (the scheduler must run in an event loop)."""
    cron_cfg({"smoke-hello": {"schedule": "0 13 * * *", "spec": "hello"}})

    async def scenario():
        cron_scheduler.shutdown()  # clean slate
        cron_scheduler.set_disabled("smoke-hello", True)
        cron_scheduler.start()
        assert cron_scheduler._scheduler is not None
        assert cron_scheduler._scheduler.get_job("smoke-hello") is None
        cron_scheduler.set_disabled("smoke-hello", False)
        assert cron_scheduler._scheduler.get_job("smoke-hello") is not None
        cron_scheduler.shutdown()

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
#  Scheduler behavior (unit)
# ---------------------------------------------------------------------------


def test_start_no_jobs(monkeypatch):
    monkeypatch.setattr(cron_scheduler, "load_extra", lambda *a, **k: {"cron": {}})
    cron_scheduler.shutdown()  # clean slate
    cron_scheduler.start()
    assert cron_scheduler._scheduler is None
    cron_scheduler.shutdown()


def test_fire_skips_running_job(monkeypatch):
    from api import executor

    job = cron_scheduler.CronJob(name="j", schedule="0 12 * * *", spec="hello")
    cron_scheduler._last_run["j"] = cron_scheduler.executor.BotRun(
        run_id="prev", task="hello", args="", status=RUNNING
    )
    calls: list = []
    monkeypatch.setattr(
        executor,
        "execute_bot_spec",
        lambda *a, **k: (
            calls.append(a) or cron_scheduler.executor.BotRun(run_id="x", task="hello", args="")
        ),
    )
    try:
        asyncio.run(cron_scheduler._fire(job))
        assert calls == []
    finally:
        cron_scheduler._last_run.pop("j", None)  # no cross-test leakage


def test_fire_when_previous_finished(monkeypatch):
    from api import executor

    job = cron_scheduler.CronJob(name="j", schedule="0 12 * * *", spec="hello")
    cron_scheduler._last_run["j"] = cron_scheduler.executor.BotRun(
        run_id="prev", task="hello", args="", status=SUBMITTED
    )
    calls: list = []
    monkeypatch.setattr(
        executor,
        "execute_bot_spec",
        lambda spec, **k: (
            calls.append(spec) or cron_scheduler.executor.BotRun(run_id="x", task=spec, args="")
        ),
    )
    try:
        asyncio.run(cron_scheduler._fire(job))
        assert calls == ["hello"]
    finally:
        cron_scheduler._last_run.pop("j", None)


def test_trigger_unknown_job():
    with pytest.raises(KeyError):
        cron_scheduler.trigger("nope")
