"""Unit tests for scripts/sync_running.py (no network) and the running macros.

Covers the offline-testable pieces: JS-string unescaping, asset discovery in
the index HTML, JSON.parse payload extraction, the Run-type filter, the
data-yaml helpers, and the running_macros aggregation/rendering functions.
"""

import health_macros
import pytest
import running_macros as rm
import yaml
from sync_running import (
    drop_polyline,
    extract_activities,
    find_asset_url,
    is_run,
    js_unescape,
)


def test_js_unescape_common_escapes():
    assert js_unescape(r"a\\b") == "a\\b"
    assert js_unescape(r"it\'s") == "it's"
    assert js_unescape(r"a\"b") == 'a"b'
    assert js_unescape(r"line\nbreak") == "line\nbreak"
    assert js_unescape(r"\u4e2d\u6587") == "中文"


def test_js_unescape_unknown_escape_drops_backslash():
    # JS semantics: unknown escapes keep the character, dropping the backslash
    assert js_unescape(r"\z") == "z"


def test_js_unescape_polyline_double_backslashes():
    # polylines arrive double-escaped in the JS string literal: the raw bundle
    # has \\\\ which JS parses to \\ (still a JSON escape, resolved by
    # json.loads downstream -> single backslash)
    assert js_unescape(r"wBr@}@fA\\\\Nd@r@") == r"wBr@}@fA\\Nd@r@"


def test_extract_activities_resolves_polyline_backslashes():
    bundle = r"""const e=JSON.parse('[{"name":"A\\\\B","type":"Run"}]');export{e as a};"""
    acts = extract_activities(bundle)
    assert acts[0]["name"] == "A\\B"


def test_find_asset_url_href_modulepreload():
    html = '<link rel="modulepreload" crossorigin href="/running_page/assets/activities-ABC123.js">'
    assert (
        find_asset_url(html)
        == "https://xiongjia.github.io/running_page/assets/activities-ABC123.js"
    )


def test_find_asset_url_script_src():
    html = '<script type="module" src="/running_page/assets/activities-xyz_9.js"></script>'
    assert (
        find_asset_url(html) == "https://xiongjia.github.io/running_page/assets/activities-xyz_9.js"
    )


def test_find_asset_url_absolute_and_missing():
    # same-origin absolute URL passes through; foreign origins are refused
    assert (
        find_asset_url('<script src="https://xiongjia.github.io/assets/activities-A1.js"></script>')
        == "https://xiongjia.github.io/assets/activities-A1.js"
    )
    assert find_asset_url("<html>no asset here</html>") is None
    external = '<script src="https://cdn.example.com/assets/activities-A1.js"></script>'
    assert find_asset_url(external) is None


def test_extract_activities_parses_payload():
    bundle = (
        r"""const e=JSON.parse('[{"run_id":1,"name":"Pudong """
        r"""\\\\ Evening","type":"Run","moving_time":"0:19:42.196000"}"""
        r""",{"run_id":2,"type":"cycling"}]');export{e as a};"""
    )
    acts = extract_activities(bundle)
    assert len(acts) == 2
    assert acts[0]["name"] == "Pudong \\ Evening"
    assert acts[0]["moving_time"] == "0:19:42.196000"


def test_extract_activities_missing_payload_raises():
    try:
        extract_activities("const e=[];export{e as a};")
    except ValueError as exc:
        assert "payload not found" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_extract_activities_invalid_json_raises():
    try:
        extract_activities("const e=JSON.parse('[not json');export{e as a};")
    except ValueError as exc:
        assert "invalid activities JSON" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_is_run_case_insensitive():
    assert is_run({"type": "Run"})
    assert is_run({"type": "run"})
    assert not is_run({"type": "cycling"})
    assert not is_run({})


def test_drop_polyline_keeps_rest():
    a = {"run_id": 1, "name": "Pudong", "summary_polyline": "xyz", "distance": 2059.83}
    out = drop_polyline(a)
    assert "summary_polyline" not in out
    assert out["run_id"] == 1
    # original dict untouched
    assert "summary_polyline" in a


def test_data_yaml_roundtrip_preserves_interval_strings():
    # PyYAML must quote interval strings, otherwise '0:19:42' parses as a
    # sexagesimal float on read-back
    payload = {
        "synced_at": "2026-08-01T12:00:00+08:00",
        "activities": [{"moving_time": "0:19:42.196000"}],
    }
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False)
    back = yaml.safe_load(text)
    assert back["activities"][0]["moving_time"] == "0:19:42.196000"
    assert isinstance(back["activities"][0]["moving_time"], str)


def test_macro_runs_sorted_newest_first():
    """running_macros._runs returns newest-first regardless of yaml order."""
    data = {
        "activities": [
            {
                "name": "old",
                "distance": 5000,
                "start_date": "2025-10-15 14:21:46",
                "start_date_local": "2025-10-15 22:21:46",
            },
            {
                "name": "new",
                "distance": 8000,
                "start_date": "2026-08-02 14:06:45",
                "start_date_local": "2026-08-02 22:06:45",
            },
        ]
    }
    runs = rm._runs(data)
    assert [a["name"] for a in runs] == ["new", "old"]

    recent = rm._recent(data)
    assert "new" in recent.splitlines()[4]  # note(0), blank(1), header(2), sep(3), data(4)
    chart = rm._monthly_chart(data)
    assert "2026" in chart.splitlines()[2]  # title uses the newest year


def test_recent_filters_to_last_two_weeks():
    """running_macros._recent keeps only activities within the last 14 days."""
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    now = _dt.now()

    def act(name, days_ago):
        dt = now - _td(days=days_ago)
        stamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        return {"name": name, "distance": 5000, "start_date": stamp, "start_date_local": stamp}

    data = {"activities": [act("old", 40), act("mid", 15), act("new", 1)]}
    table = rm._recent(data)
    rows = [line for line in table.splitlines() if line.startswith("| ") and "|" in line[2:]]
    assert len(rows) == 2  # header + one data row
    assert "new" in rows[1]
    assert "old" not in table


def test_recent_falls_back_when_no_two_week_runs():
    """When every activity is older than 14 days, show the last 10 instead."""
    data = {
        "activities": [
            {
                "name": "old1",
                "distance": 5000,
                "start_date": "2025-10-15 14:21:46",
                "start_date_local": "2025-10-15 22:21:46",
            },
            {
                "name": "old2",
                "distance": 8000,
                "start_date": "2025-10-16 14:06:45",
                "start_date_local": "2025-10-16 22:06:45",
            },
        ]
    }
    table = rm._recent(data)
    assert "old1" in table and "old2" in table


def test_all_collapsed_details():
    """running_macros._all wraps the full table in a collapsed ??? block."""
    data = {
        "activities": [
            {
                "name": "a",
                "distance": 5000,
                "start_date": "2026-08-02 14:06:45",
                "start_date_local": "2026-08-02 22:06:45",
            },
            {
                "name": "b",
                "distance": 8000,
                "start_date": "2026-08-01 14:06:45",
                "start_date_local": "2026-08-01 22:06:45",
            },
        ]
    }
    out = rm._all(data)
    assert out.startswith('??? "')  # collapsed by default (no '+')
    assert "All Activities (2)" in out
    assert out.count("| a |") == 1 and out.count("| b |") == 1
    # details content is indented
    assert any(line.startswith("    | ") for line in out.splitlines())


def test_monthly_chart_merges_distance_bar_and_hr_line():
    """running_macros._monthly_chart: one plot with bar (km) + line (bpm)."""

    def act(name, stamp, km, hr):
        return {
            "name": name,
            "distance": km * 1000,
            "start_date": stamp,
            "start_date_local": stamp,
            "average_heartrate": hr,
        }

    data = {
        "activities": [
            act("a", "2026-08-02 14:06:45", 5.0, 140),
            act("b", "2026-07-15 14:06:45", 8.0, 150),
        ]
    }
    out = rm._monthly_chart(data)
    assert 'title "Monthly Distance (km) & Avg HR (bpm) — 2026"' in out
    assert 'x-axis ["Jul", "Aug"]' in out
    assert "bar [8.0, 5.0]" in out
    assert "line [150, 140]" in out
    assert 'y-axis "km / bpm" 0 --> 165' in out


def test_monthly_chart_hr_missing_month_uses_zero():
    """A month with runs but no HR data falls back to 0 in the line series."""
    data = {
        "activities": [
            {
                "name": "a",
                "distance": 5000,
                "start_date": "2026-08-02 14:06:45",
                "start_date_local": "2026-08-02 14:06:45",
            },
            {
                "name": "b",
                "distance": 8000,
                "start_date": "2026-07-15 14:06:45",
                "start_date_local": "2026-07-15 14:06:45",
                "average_heartrate": 150,
            },
        ]
    }
    out = rm._monthly_chart(data)
    assert "line [150, 0]" in out


# ---------------------------------------------------------------------------
#  Macro aggregation / rendering coverage
# ---------------------------------------------------------------------------


def test_load_data_empty_comment_only_file_returns_empty(tmp_path):
    """running_macros._load_data: comment-only yaml -> {} (not None)."""
    data_dir = tmp_path / "notes" / "health" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "running.yml").write_text("# only a comment\n", encoding="utf-8")

    env = type("Env", (), {"conf": {"docs_dir": str(tmp_path)}})()
    assert rm._load_data(env) == {}


def test_activity_date_falls_back_to_start_date():
    """running_macros._activity_date: garbage local -> valid start_date, else None."""
    act = {"start_date_local": "not-a-date", "start_date": "2025-10-15 14:21:46"}
    dt = rm._activity_date(act)
    assert dt is not None and dt.year == 2025

    assert rm._activity_date({"start_date_local": "x", "start_date": "y"}) is None
    assert rm._activity_date({}) is None


def test_summary_aggregates_cards():
    """running_macros._summary: totals for km, time, elevation, avg HR."""
    data = {
        "activities": [
            {
                "name": "a",
                "distance": 5000,
                "moving_time": "0:30:00",
                "elevation_gain": 50,
                "average_heartrate": 140,
                "start_date_local": "2026-08-01 22:00:00",
            },
            {
                "name": "b",
                "distance": 3000,
                "moving_time": "0:20:00",
                "elevation_gain": 30,
                "average_heartrate": 120,
                "start_date_local": "2026-08-02 22:00:00",
            },
        ]
    }
    out = rm._summary(data)
    assert '<div class="label">Runs</div><div class="value">2</div>' in out
    assert '<div class="label">Distance</div><div class="value">8.0 km</div>' in out
    assert '<div class="label">Total Time</div><div class="value">50m</div>' in out
    assert '<div class="label">Elevation</div><div class="value">80 m</div>' in out
    assert '<div class="label">Avg HR</div><div class="value">130 bpm</div>' in out


def test_summary_missing_hr_shows_dash():
    """running_macros._summary: no heart-rate data -> '—' in the Avg HR card."""
    data = {
        "activities": [{"name": "a", "distance": 5000, "start_date_local": "2026-08-01 22:00:00"}]
    }
    out = rm._summary(data)
    assert '<div class="label">Avg HR</div><div class="value">—</div>' in out


def test_year_table_groups_by_year_newest_first():
    """running_macros._year_table: per-year rows sorted newest first."""
    data = {
        "activities": [
            {
                "name": "y2025",
                "distance": 5000,
                "moving_time": "0:30:00",
                "elevation_gain": 50,
                "average_heartrate": 140,
                "start_date_local": "2025-10-15 22:21:46",
            },
            {
                "name": "y2026",
                "distance": 3000,
                "moving_time": "0:20:00",
                "elevation_gain": 30,
                "average_heartrate": 120,
                "start_date_local": "2026-08-02 22:06:45",
            },
        ]
    }
    out = rm._year_table(data)
    rows = [line for line in out.splitlines() if line.startswith("| 20")]
    assert len(rows) == 2
    assert "| 2026 | 1 | 3.0 | 6:40 | 120 | 30 |" in rows[0]
    assert "| 2025 | 1 | 5.0 | 6:00 | 140 | 50 |" in rows[1]


def test_parse_moving_time_and_formatters():
    """running_macros: interval parsing, duration and pace formatting."""
    assert rm._parse_moving_time("0:19:42.196000") == pytest.approx(1182.196)
    assert rm._parse_moving_time("") is None
    assert rm._parse_moving_time(None) is None
    assert rm._parse_moving_time("nope") is None

    assert rm._fmt_hours_minutes(45240) == "12h 34m"
    assert rm._fmt_hours_minutes(3000) == "50m"
    assert rm._fmt_hours_minutes(0) == "0m"

    assert rm._fmt_pace(332) == "5:32"
    assert rm._fmt_pace(60.0) == "1:00"
    assert rm._fmt_pace(0) == "—"
    assert rm._fmt_pace(None) == "—"


def test_activity_table_duration_pace_hr_cells():
    """running_macros._activity_table: merged when-cell, pace and HR formatting."""
    runs = [
        {
            "name": "Pudong",
            "distance": 5000,
            "moving_time": "0:25:00",
            "average_heartrate": 123,
            "start_date_local": "2026-08-02 22:06:45",
        }
    ]
    out = rm._activity_table(runs)
    assert "| 2026-08-02 22:06 · 25m | Pudong | 5.00 | 5:00 | 123 |" in out


def test_load_existing_activities_reads_yaml(monkeypatch, tmp_path):
    """sync_running._load_existing_activities: reads yaml; missing file -> []."""
    import sync_running as sr

    yaml_path = tmp_path / "running.yml"
    yaml_path.write_text(
        yaml.safe_dump(
            {"activities": [{"name": "a", "distance": 5000}]},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sr, "DATA_PATH", str(yaml_path))
    assert sr._load_existing_activities() == [{"name": "a", "distance": 5000}]

    monkeypatch.setattr(sr, "DATA_PATH", str(tmp_path / "missing.yml"))
    assert sr._load_existing_activities() == []


def test_macros_render_no_data_hint_when_empty():
    """running_macros: data renderers return the no-data hint for {}."""
    hint = rm._no_data()
    for fn in (rm._summary, rm._year_table, rm._recent, rm._all, rm._monthly_chart):
        assert fn({}) == hint


def test_load_data_non_dict_yaml_returns_empty(tmp_path):
    """running_macros._load_data: a hand-edited list/scalar yaml -> {} not a crash."""
    data_dir = tmp_path / "notes" / "health" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "running.yml").write_text("- just a list\n", encoding="utf-8")

    env = type("Env", (), {"conf": {"docs_dir": str(tmp_path)}})()
    assert rm._load_data(env) == {}


def test_synced_note_missing_timestamp_does_not_claim_no_data():
    """running_macros._synced_note: missing synced_at -> sync hint, not the no-data hint."""
    note = rm._synced_note({"activities": [{"name": "a"}]})
    assert note != rm._no_data()
    assert "sync-running" in note

    with_timestamp = rm._synced_note({"synced_at": "2026-08-03T00:00:00+08:00"})
    assert "Data synced at" in with_timestamp


def test_health_macros_registers_running_macros():
    """health_macros loader wires running_macros into the macros plugin env."""

    class Env:
        def __init__(self):
            self.registered = {}

        def macro(self, fn):
            self.registered[fn.__name__] = fn
            return fn

    env = Env()
    health_macros.define_env(env)
    for name in (
        "running_summary",
        "running_year_table",
        "running_monthly_chart",
        "running_recent",
        "running_all",
        "running_synced_at",
    ):
        assert name in env.registered


def test_activity_table_escapes_name_special_chars():
    """running_macros._activity_table: pipe/newline in names must not break the table."""
    runs = [
        {
            "name": "Night | Race\nSprint",
            "distance": 5000,
            "moving_time": "0:25:00",
            "average_heartrate": 120,
            "start_date_local": "2026-08-02 22:06:45",
        }
    ]
    out = rm._activity_table(runs)
    row = out.splitlines()[-1]
    # exact row: pipe escaped, newline flattened, 5 columns intact
    assert row == "| 2026-08-02 22:06 \u00b7 25m | Night \\| Race Sprint | 5.00 | 5:00 | 120 |"


def test_find_asset_url_rejects_external_origin():
    """sync_running.find_asset_url: absolute URLs from other origins are refused."""
    html = '<script src="https://evil.example/assets/activities-hack.js"></script>'
    assert find_asset_url(html) is None
    # same-origin absolute URL still accepted
    ok = '<script src="https://xiongjia.github.io/running_page/assets/activities-A1.js"></script>'
    assert find_asset_url(ok) == "https://xiongjia.github.io/running_page/assets/activities-A1.js"
    # protocol-relative URL is refused outright
    proto_rel = '<script src="//evil.example/assets/activities-hack.js"></script>'
    assert find_asset_url(proto_rel) is None
