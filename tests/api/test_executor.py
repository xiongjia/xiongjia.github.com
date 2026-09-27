"""Tests for api.executor: argv assembly, schema→args mapping, outcomes."""

from __future__ import annotations

import pytest

from api.executor import _finalize, assemble_argv
from api.models import assemble_args, task_names, task_schema
from api.state import MERGED, SUBMITTED, BotRun, active_runs


def test_task_names_curated_usage_order():
    # console quick-task pane: curated usage order, not the full engine
    # registry — health-summary / create-post stay runnable via /api/bot/run
    # but are hidden from the list
    assert task_names() == [
        "text-moment",
        "weight",
        "enu",
        "sync-running",
        "collect",
        "collect-todo",
        "collect-idea",
    ]


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


def test_assemble_argv_local_mode():
    """Local runs use ``--local`` and drop the handoff/CI flags (meaningless
    without a worktree/branch/PR)."""
    argv = assemble_argv("weight", ["82"], local=True)
    assert argv == ["uv", "run", "poe", "bot", "run", "weight 82", "--local"]
    assert "--handoff" not in argv and "--wait-ci" not in argv
    # auto_merge is irrelevant in local mode too
    assert "--auto-merge" not in assemble_argv("weight", ["82"], auto_merge=True, local=True)


def test_local_mode_resolution(monkeypatch):
    """``local=None`` follows BOT_API_LOCAL; an explicit flag always wins."""
    from api import config, executor

    monkeypatch.setattr(config.settings, "local", False)
    assert executor._resolve_local(None) is False
    assert executor._resolve_local(True) is True
    monkeypatch.setattr(config.settings, "local", True)
    assert executor._resolve_local(None) is True
    assert executor._resolve_local(False) is False


def test_assemble_args_positional_and_flag():
    args = assemble_args("weight", {"value": 82.5, "use_date": True, "date": "2026-08-14"})
    assert args == ["82.5", "--date=2026-08-14"]


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
    # checkbox checked + picked date → --date=<iso> (single token — the bot
    # spec format re-splits on whitespace, so flag values ride the flag)
    assert assemble_args("weight", {"value": 82.5, "use_date": True, "date": "2026-08-14"}) == [
        "82.5",
        "--date=2026-08-14",
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


# ---------------------------------------------------------------------------
# text-moment (create_moment.py) schema — full parameter surface
# ---------------------------------------------------------------------------


def _moment_schema() -> dict[str, object]:
    return {f.name: f for f in task_schema("text-moment").fields}


def test_text_moment_schema_exposes_all_parameters():
    """The moment form exposes every create_moment.py option."""
    s = _moment_schema()
    assert {f"{n}:{f.type}" for n, f in s.items()} >= {
        "content:textarea",
        "time:text",
        "time_from_exif:checkbox",
        "slug:text",
        "tags:text",
        "images:images",
        "no_upload:checkbox",
        "draft:checkbox",
        "place:text",
        "set_gps:checkbox",
        "lng:number",
        "lat:number",
        "crs:select",
        "region:text",
        "meta:repeat",
    }
    assert s["lng"].arg == "--lng"
    assert s["lat"].arg == "--lat"
    assert s["tags"].arg == "--tags"
    assert s["images"].arg is None  # paired rows are assembled specially
    assert s["meta"].arg == "--meta"
    assert s["images"].upload is True  # browser file-picker stages via /api/upload
    assert s["meta"].upload is False


def test_text_moment_tab_grouping():
    """Fields are grouped into console tabs; order = first-seen."""
    s = task_schema("text-moment")
    tabs = {}
    for f in s.fields:
        if f.tab:
            tabs.setdefault(f.tab, []).append(f.name)
    assert list(tabs) == ["Content", "Images", "Location", "Meta"]
    assert tabs["Content"] == ["content", "time", "time_from_exif", "slug", "tags", "draft"]
    assert tabs["Images"] == ["images", "no_upload"]
    assert tabs["Location"] == ["place", "set_gps", "lng", "lat", "crs", "region"]
    assert tabs["Meta"] == ["meta"]


def test_text_moment_time_from_exif_flag():
    """The EXIF-time checkbox maps to --time-from-exif (checked-only emit)."""
    s = _moment_schema()
    f = s["time_from_exif"]
    assert f.type == "checkbox" and f.arg == "--time-from-exif" and f.emit == "checked"
    # the checkbox requires an image and turns the manual Time input off in
    # the console (the conflict is prevented in the UI, still guarded here)
    assert f.requires == "images" and f.disables == "time" and f.conflicts_with == "time"
    # the flag rides the uploaded photos' EXIF DateTimeOriginal
    assert assemble_args(
        "text-moment",
        {"content": "x", "time_from_exif": True, "images": [{"path": "a.jpg"}]},
    ) == ["x", "--time-from-exif", "--image=a.jpg"]
    assert assemble_args("text-moment", {"content": "x", "time_from_exif": False}) == ["x"]
    # a raw client sending the string spelling "false" is unchecked (matches
    # _as_bool elsewhere) so it does not trip the mutual-exclusion check
    assert assemble_args(
        "text-moment", {"content": "x", "time": "9am", "time_from_exif": "false"}
    ) == ["x", "--time=9am"]


def test_text_moment_time_and_exif_are_mutually_exclusive():
    """--time and --time-from-exif both set must fail early, naming both fields
    (the CLI would otherwise error after a worktree + subprocess started)."""
    # the photo is included so the `requires: images` rule cannot mask the
    # conflict regardless of field order in the schema
    with pytest.raises(ValueError, match="'time' and 'time_from_exif' are mutually exclusive"):
        assemble_args(
            "text-moment",
            {
                "content": "x",
                "time": "9am",
                "time_from_exif": True,
                "images": [{"path": "a.jpg"}],
            },
        )
    # either one alone is fine
    assert assemble_args("text-moment", {"content": "x", "time": "9am"}) == ["x", "--time=9am"]
    assert assemble_args(
        "text-moment",
        {"content": "x", "time_from_exif": True, "images": [{"path": "a.jpg"}]},
    ) == ["x", "--time-from-exif", "--image=a.jpg"]


def test_text_moment_time_from_exif_requires_images():
    """Checking the EXIF-time box without any photo must fail early (422),
    not inside the CLI after a worktree has been created."""
    with pytest.raises(ValueError, match="'time_from_exif' requires 'images'"):
        assemble_args("text-moment", {"content": "x", "time_from_exif": True})
    # an empty images list is not a photo either
    with pytest.raises(ValueError, match="requires 'images'"):
        assemble_args("text-moment", {"content": "x", "time_from_exif": True, "images": []})
    # nor is a list of blank strings (repeat-field edge case)
    with pytest.raises(ValueError, match="requires 'images'"):
        assemble_args("text-moment", {"content": "x", "time_from_exif": True, "images": [""]})
    # a row with no path emits no --image, so it must not satisfy the requires
    with pytest.raises(ValueError, match="requires 'images'"):
        assemble_args(
            "text-moment", {"content": "x", "time_from_exif": True, "images": [{"path": ""}]}
        )
    # a real photo satisfies it
    assert assemble_args(
        "text-moment", {"content": "x", "time_from_exif": True, "images": [{"path": "a.jpg"}]}
    ) == ["x", "--time-from-exif", "--image=a.jpg"]


def test_text_moment_fields_carry_help_text():
    """Every text-moment field has user-facing help (the meta explanation
    must be detailed enough to learn the KEY=VALUE format and rating scale)."""
    s = _moment_schema()
    assert all(f.help for f in s.values())
    meta_help = s["meta"].help
    assert "KEY=VALUE" in meta_help
    assert "rating" in meta_help and "1–5" in meta_help
    # the EXIF/GPS behaviour is spelled out where users look for it
    assert "EXIF" in s["time_from_exif"].help
    assert "EXIF" in s["set_gps"].help and "WGS-84" in s["set_gps"].help


def test_non_moment_tasks_have_no_tabs():
    """Other tasks keep the single-pane form (no tab metadata)."""
    for task in ["weight", "enu", "create-post"]:
        s = task_schema(task)
        assert all(f.tab is None for f in s.fields)


def test_text_moment_assemble_full():
    """Every filled option maps to the engine flag list."""
    args = assemble_args(
        "text-moment",
        {
            "content": "hello world",
            "time": "9pm",
            "slug": "my-slug",
            "tags": "food,film",
            "images": [
                {"path": "a.jpg", "caption": "第一张"},
                {"path": "b.png"},  # no caption — sparse stays aligned
            ],
            "no_upload": True,
            "draft": True,
            "place": "徐汇",
            "set_gps": True,
            "lng": 121.47,
            "lat": 31.16,
            "crs": "gcj02",
            "region": "shanghai",
            "meta": ["name=La_Mian", "rating=4"],
        },
    )
    assert args == [
        "hello world",
        "--time=9pm",
        "--slug=my-slug",
        "--tags=food,film",
        "--draft",
        "--image=a.jpg|第一张",
        "--image=b.png",
        "--no-upload",
        "--place=徐汇",
        "--lng=121.47",
        "--lat=31.16",
        "--crs=gcj02",
        "--region=shanghai",
        "--meta=name=La_Mian",
        "--meta=rating=4",
    ]


def test_text_moment_gps_gate_drops_coords():
    """Unchecked "Set coordinates" drops lng/lat/crs server-side too."""
    args = assemble_args(
        "text-moment",
        {"content": "x", "lng": 121.47, "lat": 31.16, "crs": "gcj02"},
    )
    assert args == ["x"]


def test_text_moment_checked_flags_emit_only_when_checked():
    """--draft / --no-upload are emitted when checked (emit: checked)."""
    assert assemble_args("text-moment", {"content": "x"}) == ["x"]
    assert assemble_args("text-moment", {"content": "x", "draft": False}) == ["x"]
    assert assemble_args("text-moment", {"content": "x", "draft": True}) == [
        "x",
        "--draft",
    ]
    assert assemble_args("text-moment", {"content": "x", "no_upload": True}) == [
        "x",
        "--no-upload",
    ]
    # string truthy/falsy spellings behave like the console checkbox
    assert assemble_args("text-moment", {"content": "x", "draft": "false"}) == ["x"]
    assert assemble_args("text-moment", {"content": "x", "draft": "true"}) == [
        "x",
        "--draft",
    ]


def test_text_moment_images_accepts_scalar_and_inline():
    """A raw API client may send a scalar string or the inline path|caption."""
    assert assemble_args("text-moment", {"content": "x", "images": "photo.jpg"}) == [
        "x",
        "--image=photo.jpg",
    ]
    assert assemble_args("text-moment", {"content": "x", "images": []}) == ["x"]
    assert assemble_args("text-moment", {"content": "x", "images": ["a.jpg|c1"]}) == [
        "x",
        "--image=a.jpg|c1",
    ]


def test_assemble_args_rejects_spaces_in_flag_values():
    """A flag value with whitespace would be split by the bot spec format
    and silently corrupt the moment content — block with a clear error."""
    with pytest.raises(ValueError, match="must not contain spaces"):
        assemble_args("text-moment", {"content": "x", "time": "2026-08-09 14:30"})
    with pytest.raises(ValueError, match="must not contain spaces"):
        assemble_args("text-moment", {"content": "x", "place": "Xuhui Riverside"})
    with pytest.raises(ValueError, match="must not contain spaces"):
        assemble_args(
            "text-moment", {"content": "x", "images": [{"path": "a.jpg", "caption": "two words"}]}
        )
    with pytest.raises(ValueError, match="must not contain spaces"):
        assemble_args("text-moment", {"content": "x", "meta": ["name=La Mian"]})
    # space-free values still pass
    assert assemble_args("text-moment", {"content": "x", "time": "2026-08-09T14:30"}) == [
        "x",
        "--time=2026-08-09T14:30",
    ]


def test_validate_schemas_accepts_comma_enables():
    """A checkbox may gate a group (lng,lat,crs) via comma-separated enables."""
    from api import models

    assert models.validate_schemas() is None  # the real moment schema validates


def test_validate_schemas_rejects_unknown_comma_enables(monkeypatch):
    from api import models

    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {
            "weight": [
                {"name": "use_date", "type": "checkbox", "enables": "date,nope"},
                {"name": "date", "type": "date"},
            ]
        },
    )
    with pytest.raises(RuntimeError, match="enables unknown field 'nope'"):
        models.validate_schemas()


def test_field_schema_rejects_bad_emit():
    """A checkbox ``emit`` typo must fail fast, not silently invert the flag."""
    from pydantic import ValidationError

    from api import models

    with pytest.raises(ValidationError, match="emit"):
        models.FieldSchema(name="draft", type="checkbox", label="D", arg="--draft", emit="checkedd")


def test_validate_schemas_catches_task_drift(monkeypatch):
    from api import models

    # a curated name removed/renamed in the engine must be loud, not a
    # silent drop of the console button
    monkeypatch.setattr(models, "TASKS", {k: v for k, v in models.TASKS.items() if k != "weight"})
    with pytest.raises(RuntimeError, match="missing from engine registry"):
        models.validate_schemas()


def test_validate_schemas_catches_unknown_conflicts_with(monkeypatch):
    from api import models

    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {
            "weight": [
                {"name": "value", "type": "number", "arg": 0},
                {"name": "use_date", "type": "checkbox", "conflicts_with": "nope"},
            ]
        },
    )
    with pytest.raises(RuntimeError, match="conflicts with unknown field 'nope'"):
        models.validate_schemas()


@pytest.mark.parametrize("prop", ["requires", "disables"])
def test_validate_schemas_catches_unknown_relation(prop, monkeypatch):
    from api import models

    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {
            "weight": [
                {"name": "value", "type": "number", "arg": 0},
                {"name": "use_date", "type": "checkbox", prop: "nope"},
            ]
        },
    )
    with pytest.raises(RuntimeError, match=f"{prop} unknown field 'nope'"):
        models.validate_schemas()


def test_validate_schemas_rejects_duplicate_field_names(monkeypatch):
    from api import models

    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {
            "weight": [
                {"name": "value", "type": "number", "arg": 0},
                {"name": "value", "type": "text"},
            ]
        },
    )
    with pytest.raises(RuntimeError, match="duplicate field name 'value'"):
        models.validate_schemas()


@pytest.mark.parametrize("prop", ["enables", "disables"])
def test_validate_schemas_rejects_gate_on_non_checkbox(prop, monkeypatch):
    from api import models

    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {
            "weight": [
                {"name": "value", "type": "number", "arg": 0},
                {"name": "note", "type": "text", prop: "value"},
            ]
        },
    )
    with pytest.raises(RuntimeError, match=f"declares '{prop}' but is not a checkbox"):
        models.validate_schemas()


def test_validate_schemas_rejects_self_reference(monkeypatch):
    from api import models

    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {"weight": [{"name": "value", "type": "checkbox", "conflicts_with": "value"}]},
    )
    with pytest.raises(RuntimeError, match="lists itself in 'conflicts_with'"):
        models.validate_schemas()


def test_validate_schemas_rejects_enable_disable_overlap(monkeypatch):
    """A field governed by both an `enables` and a `disables` checkbox would
    have its disabled state decided by call order — reject it at import."""
    from api import models

    monkeypatch.setattr(
        models,
        "_TASK_FIELDS",
        {
            "weight": [
                {"name": "value", "type": "number", "arg": 0},
                {"name": "a", "type": "checkbox", "enables": "note"},
                {"name": "b", "type": "checkbox", "disables": "note"},
                {"name": "note", "type": "text"},
            ]
        },
    )
    with pytest.raises(RuntimeError, match="both enabled and disabled"):
        models.validate_schemas()


def test_text_moment_meta_help_matches_mkdocs_config():
    """The meta help hardcodes the configured keys — fail when mkdocs.yml
    gains/loses a category or key so the help cannot silently drift."""
    from shared.mkdocs_yaml import load_extra

    meta_fields = load_extra("moment", label="test").get("meta_fields") or {}
    assert meta_fields, "mkdocs.yml extra.moment.meta_fields must not be empty"
    help_text = _moment_schema()["meta"].help
    for tag, fields in meta_fields.items():
        assert tag in help_text, f"tag {tag!r} missing from the meta help"
        for f in fields:
            assert f["key"] in help_text, f"key {f['key']!r} missing from the meta help"


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


def test_finalize_local_run():
    """A local run finishes as LOCAL (no PR) even though the output has no
    Draft-PR line."""
    from api.state import LOCAL

    run = BotRun(run_id="l", task="text-moment", args="hi")
    run.log("🧪 local run — working tree directly (no worktree / branch / PR)")
    _finalize(run, 0, local=True)
    assert run.status == LOCAL
    assert run.pr_url is None


def test_finalize_noop_no_changes():
    from api.state import NOOP

    run = BotRun(run_id="n", task="weight", args="82")
    run.log("⏭ no changes (already recorded) — skipping PR")
    _finalize(run, 0)
    assert run.status == NOOP
    assert run.pr_url is None


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
