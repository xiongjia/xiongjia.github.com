"""Tests for api.executor: argv assembly, schema→args mapping, outcomes."""

from __future__ import annotations

import pytest

from api.executor import _finalize, assemble_argv
from api.models import assemble_args, task_names, task_schema
from api.state import MERGED, SUBMITTED, BotRun, active_runs


def test_task_names_curated_usage_order():
    # console quick-task pane: curated usage order, not the full engine
    # registry — health-summary / text-moment / create-post stay runnable
    # via /api/bot/run but are hidden from the list
    assert task_names() == ["weight", "enu", "sync-running"]


def test_assemble_argv_flat():
    argv = assemble_argv("weight", ["82.5", "--date", "2026-08-14"], auto_merge=True)
    assert argv == [
        "uv",
        "run",
        "poe",
        "bot",
        "run",
        "weight 82.5 --date 2026-08-14",
        "--handoff",
        "--auto-merge",
    ]
    # handoff is the default; auto-merge is an internal test-only knob
    argv2 = assemble_argv("weight", ["82"], auto_merge=False)
    assert "--handoff" in argv2
    assert "--auto-merge" not in argv2


def test_assemble_argv_wait_ci_when_handoff_off():
    argv = assemble_argv("weight", ["82"], handoff=False)
    assert "--wait-ci" in argv
    assert "--handoff" not in argv
    assert "--auto-merge" not in argv  # wait-ci still never merges


def test_assemble_argv_stage_dir():
    argv = assemble_argv("text-moment", ["x"], auto_merge=False, stage_dir=".bot-api/stage/r1")
    assert argv[-2:] == ["--stage-dir", ".bot-api/stage/r1"]


def test_assemble_args_positional_and_flag():
    args = assemble_args("weight", {"value": 82.5, "use_date": True, "date": "2026-08-14"})
    assert args == ["82.5", "--date", "2026-08-14"]


def test_assemble_args_optional_omitted():
    assert assemble_args("weight", {"value": 82}) == ["82"]


def test_weight_date_is_gated_date_picker():
    # console version: a "Specify date" checkbox (default unchecked) gates a
    # native date picker — unchecked sends no --date; text-moment's optional
    # time stays free text
    s = task_schema("weight")
    gate = next(f for f in s.fields if f.name == "use_date")
    date_field = next(f for f in s.fields if f.name == "date")
    time_field = next(f for f in task_schema("text-moment").fields if f.name == "time")
    assert date_field.type == "date"
    assert gate.type == "checkbox" and gate.default is False
    assert gate.enables == "date"
    assert time_field.type == "text"
    # default (no date) → no --date flag
    assert assemble_args("weight", {"value": 82}) == ["82"]
    # date without the gate checked → dropped server-side too (the API
    # contract matches the console's gated UI)
    assert assemble_args("weight", {"value": 82.5, "date": "2026-08-14"}) == ["82.5"]
    # checkbox checked + picked date → --date <iso>
    assert assemble_args("weight", {"value": 82.5, "use_date": True, "date": "2026-08-14"}) == [
        "82.5",
        "--date",
        "2026-08-14",
    ]


def test_assemble_args_required_missing():
    with pytest.raises(ValueError, match="missing required field: value"):
        assemble_args("weight", {})


def test_assemble_args_defaults():
    args = assemble_args("create-post", {"title": "Hello"})
    assert args == ["Hello", "bits"]  # category default


def test_assemble_args_draft_flag_when_unchecked():
    args = assemble_args("create-post", {"title": "T", "draft": False})
    assert args[-1] == "--no-draft"


@pytest.mark.parametrize(
    "falsy",
    ["false", "FALSE", "0", "", "no", "off", "n", "f", " false "],
)
def test_checkbox_string_falsy_spellings(falsy):
    # a raw API client sending string falsy spellings must not enable the
    # gate (or suppress the draft flag)
    assert assemble_args("weight", {"value": 82.5, "use_date": falsy, "date": "2026-08-14"}) == [
        "82.5"
    ]
    assert assemble_args("create-post", {"title": "T", "draft": falsy}) == [
        "T",
        "bits",
        "--no-draft",
    ]


def test_assemble_args_unknown_task():
    with pytest.raises(ValueError, match="unknown task"):
        assemble_args("nope", {})


def test_assemble_args_skipped_positional_refused(monkeypatch):
    # an empty optional positional before a later one would shift engine slots
    from api import models

    schema = models.TaskSchema(
        task="fake",
        fields=[
            models.FieldSchema(name="a", label="A", required=False, arg=0),
            models.FieldSchema(name="b", label="B", required=False, arg=1),
        ],
    )
    monkeypatch.setattr(models, "task_schema", lambda t: schema if t == "fake" else None)
    with pytest.raises(ValueError, match="cannot skip positional"):
        models.assemble_args("fake", {"b": "x"})  # skipping a would shift b
    assert models.assemble_args("fake", {"a": "1", "b": "2"}) == ["1", "2"]


def test_schema_fallback_for_template_task():
    s = task_schema("text-moment")
    assert s is not None
    assert s.fields[0].name == "content"
    assert s.fields[0].arg == 0


def test_validate_schemas_catches_task_drift(monkeypatch):
    from api import models

    # a curated name removed/renamed in the engine must be loud, not a
    # silent drop of the console button
    monkeypatch.setattr(models, "TASKS", {k: v for k, v in models.TASKS.items() if k != "weight"})
    with pytest.raises(RuntimeError, match="missing from engine registry"):
        models.validate_schemas()


def test_validate_schemas_catches_bad_enables(monkeypatch):
    from api import models

    # a checkbox ``enables`` pointing at a nonexistent sibling is dead config
    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {"weight": [{"name": "use_date", "type": "checkbox", "enables": "nope"}]},
    )
    with pytest.raises(RuntimeError, match="enables unknown field"):
        models.validate_schemas()


def test_validate_schemas_rejects_required_gated_field(monkeypatch):
    from api import models

    # a gated field is an optional option by definition — required + gate is
    # contradictory config that assemble_args would silently drop
    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {
            "weight": [
                {"name": "use_date", "type": "checkbox", "enables": "date"},
                {"name": "date", "type": "date", "required": True, "arg": "--date"},
            ]
        },
    )
    with pytest.raises(RuntimeError, match="must not be required"):
        models.validate_schemas()


def test_finalize_outcomes():
    run = BotRun(run_id="x", task="weight", args="82")
    run.log("🌿 branch bot/weight/20260814-0109")
    run.log("📦 Draft PR #142: https://github.com/x/pull/142")
    _finalize(run, 0)
    assert run.status == SUBMITTED
    assert run.pr_url == "https://github.com/x/pull/142"

    run2 = BotRun(run_id="y", task="weight", args="82")
    run2.log("✅ merged PR #143")
    _finalize(run2, 0)
    assert run2.status == MERGED

    run3 = BotRun(run_id="z", task="weight", args="82")
    _finalize(run3, 1)
    assert run3.status == "failed"


def test_finalize_trims_history_logs(monkeypatch):
    from api import executor

    captured: dict = {}
    monkeypatch.setattr(executor.history_store, "append", lambda rec: captured.update(rec))
    run = BotRun(run_id="h", task="weight", args="82")
    for i in range(30):
        run.log(f"line {i}")
    executor._finalize(run, 1)
    assert len(captured["logs"]) == executor.HISTORY_LOG_TAIL
    assert captured["logs"][-1]["msg"] == "❌ bot exited with code 1"
    assert captured["logs"][0]["msg"] == "line 11"  # 31 entries, tail 20 → 11 dropped


def test_terminate_proc_kills_process_group():
    # the direct child is `uv`-style; terminating must kill the whole group,
    # not orphan a grandchild that keeps running
    import asyncio
    import sys

    from api.executor import Runner, terminate_proc

    async def go():
        proc = await Runner().run([sys.executable, "-c", "import time; time.sleep(30)"], cwd=".")
        terminate_proc(proc)
        code = await asyncio.wait_for(proc.wait(), timeout=5)
        assert code != 0  # terminated, not completed

    asyncio.run(go())


def test_trim_active(monkeypatch):
    from api import state

    monkeypatch.setattr(state, "ACTIVE_CAP", 3)
    for i in range(5):
        r = BotRun(run_id=str(i), task="t", args="")
        r.finish("submitted")
        active_runs[str(i)] = r
    state.trim_active()
    assert len(active_runs) == 3
    assert "0" not in active_runs and "1" not in active_runs
    active_runs.clear()
