"""Unit tests for scripts/sync_running.py (no network) and the running macros.

Covers the offline-testable pieces of the Garmin-direct sync: polyline
encoding, pace formatting, Garmin→yml activity conversion, the incremental
cursor, splits-cache repair, and the running_macros rendering functions.
"""

import json

import health_macros
import pytest
from sync_running import (
    _encode_polyline,
    _garmin_to_activity,
    _pace_from_speed,
)

# ---------------------------------------------------------------------------
#  sync_running: pure helpers
# ---------------------------------------------------------------------------


def _decode(encoded: str) -> list[tuple[float, float]]:
    """Reference Google Polyline decoder for round-trip assertions."""
    coords = []
    index = 0
    lat = lng = 0
    while index < len(encoded):
        result = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lat += ~(result >> 1) if (result & 1) else (result >> 1)
        result = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lng += ~(result >> 1) if (result & 1) else (result >> 1)
        coords.append((lat / 1e5, lng / 1e5))
    return coords


def test_encode_polyline_roundtrip():
    coords = [(31.19077, 121.51594), (31.19137, 121.51568), (31.19168, 121.51532)]
    encoded = _encode_polyline(coords)
    assert _decode(encoded) == coords


def test_encode_polyline_negative_deltas_roundtrip():
    coords = [(31.2, 121.5), (31.19, 121.51), (31.21, 121.49)]
    assert _decode(_encode_polyline(coords)) == coords


def test_pace_from_speed():
    # 1000 m / 5:00 = 3.333 m/s
    assert _pace_from_speed(3.3333) == "5:00"
    assert _pace_from_speed(0) == "—"
    assert _pace_from_speed(-1) == "—"


def test_garmin_to_activity_fields():
    ga = {
        "activityId": 630166908,
        "activityName": "Pudong Running",
        "startTimeGMT": "2026-08-20T14:04:12.0",
        "startTimeLocal": "2026-08-20T22:04:12.0",
        "distance": 3200.0,
        "movingDuration": 844.0,
        "duration": 1093.82,
        "averageHR": 104.0,
        "averageSpeed": 0.913,
        "elevationGain": 5.0,
        "activityType": {"typeKey": "running"},
        "locationName": "Shanghai",
    }
    out = _garmin_to_activity(ga)
    assert out["run_id"] == 630166908
    assert out["distance"] == 3200.0
    assert out["moving_time"] == "14:04"  # 844s -> 14m 4s (no hour part)
    assert out["start_date"] == "2026-08-20 14:04:12"
    assert out["start_date_local"] == "2026-08-20 22:04:12"
    assert out["average_heartrate"] == 104.0
    assert out["source"] == "garmin_cn"
    assert out["type"] == "Run"


def test_garmin_to_activity_hour_moving_time():
    ga = {"activityId": 1, "movingDuration": 3661.0, "distance": 10000.0}
    assert _garmin_to_activity(ga)["moving_time"] == "1:01:01"


def test_garmin_to_activity_missing_hr_is_none():
    ga = {"activityId": 2, "distance": 1000.0}
    out = _garmin_to_activity(ga)
    assert out["average_heartrate"] is None


def test_save_splits_appends_new(tmp_path, monkeypatch):
    import sync_running as sr

    cache = tmp_path / "splits.json"
    monkeypatch.setattr(sr, "CACHE_FILE", cache)
    monkeypatch.setattr(sr, "CACHE_DIR", tmp_path)

    acts = [{"run_id": 100}]
    details = {100: {"splits": [{"km": 1.0}], "summary_polyline": "abc"}}
    sr._save_splits(acts, details)

    saved = json.loads(cache.read_text())
    assert saved["activities"][0]["run_id"] == 100
    assert saved["activities"][0]["summary_polyline"] == "abc"


def test_save_splits_repairs_partial_entry(tmp_path, monkeypatch):
    """An existing entry missing polyline is repaired in place, not duplicated."""
    import sync_running as sr

    cache = tmp_path / "splits.json"
    cache.write_text(
        json.dumps(
            {"version": 1, "activities": [{"run_id": 100, "splits": [], "summary_polyline": ""}]}
        )
    )
    monkeypatch.setattr(sr, "CACHE_FILE", cache)
    monkeypatch.setattr(sr, "CACHE_DIR", tmp_path)

    acts = [{"run_id": 100}]
    details = {100: {"splits": [{"km": 1.0}], "summary_polyline": "fixed"}}
    sr._save_splits(acts, details)

    saved = json.loads(cache.read_text())
    assert len(saved["activities"]) == 1  # no duplicate
    assert saved["activities"][0]["summary_polyline"] == "fixed"
    assert saved["activities"][0]["splits"] == [{"km": 1.0}]


def test_save_splits_skips_missing_details(tmp_path, monkeypatch):
    import sync_running as sr

    cache = tmp_path / "splits.json"
    monkeypatch.setattr(sr, "CACHE_FILE", cache)
    monkeypatch.setattr(sr, "CACHE_DIR", tmp_path)

    # details_map empty for this activity -> not written
    sr._save_splits([{"run_id": 200}], {})
    saved = json.loads(cache.read_text())
    assert saved["activities"] == []


def test_migrate_old_running_page_ids():
    """running_page-era run_ids are remapped to Garmin IDs by start date."""
    import sync_running as sr

    # two old-id entries (epoch-ms ids), one already garmin-id
    yml = [
        {"run_id": 1760538106000, "start_date": "2025-10-15 14:21:46"},
        {"run_id": 1760624263000, "start_date": "2025-10-16 14:17:43"},
        {"run_id": 630166908, "start_date": "2026-08-20 14:04:12"},
    ]
    splits = [{"run_id": 1760538106000, "start_date": "2025-10-15 14:21:46"}]
    runs = [
        {"activityId": 1001, "startTimeGMT": "2025-10-15T14:21:46"},
        {"activityId": 1002, "startTimeGMT": "2025-10-16T14:17:43"},
        {"activityId": 630166908, "startTimeGMT": "2026-08-20T14:04:12"},
    ]
    remap = sr._migrate_old_running_page_ids(yml, splits, runs)
    assert remap == {1760538106000: 1001, 1760624263000: 1002}
    assert yml[0]["run_id"] == 1001
    assert yml[1]["run_id"] == 1002
    assert yml[2]["run_id"] == 630166908  # already garmin, untouched
    assert splits[0]["run_id"] == 1001


def test_migrate_skips_ambiguous_multi_run_day():
    """A date with 2+ Garmin activities is not guessed."""
    import sync_running as sr

    yml = [{"run_id": 1760538106000, "start_date": "2025-10-15 14:21:46"}]
    runs = [
        {"activityId": 1001, "startTimeGMT": "2025-10-15T08:00:00"},
        {"activityId": 1002, "startTimeGMT": "2025-10-15T18:00:00"},
    ]
    remap = sr._migrate_old_running_page_ids(yml, [], runs)
    assert remap == {}
    assert yml[0]["run_id"] == 1760538106000  # untouched


def test_cached_detail_ids_requires_real_details():
    """Entries with only empty/partial data are not treated as cached."""
    import sync_running as sr

    acts = [
        {"run_id": 1, "summary_polyline": "abc", "splits": []},
        {"run_id": 2, "summary_polyline": "", "splits": []},
        {"run_id": 3},
    ]
    assert sr._cached_detail_ids(acts) == {1}


def _bucket_cfg() -> dict:
    return {
        "mappings": [
            {
                "prefix": "assets/bucket/running/",
                "bucket": "web-assets",
                "remote_prefix": "data/metadata/running",
            }
        ],
        "running": {"data_key": "splits.json"},
    }


def test_seed_cache_skips_when_warm(tmp_path, monkeypatch):
    """A non-empty local cache means no bucket round-trip."""
    import sync_running as sr

    cache = tmp_path / "splits.json"
    cache.write_text('{"activities": []}', encoding="utf-8")
    monkeypatch.setattr(sr, "CACHE_FILE", cache)
    monkeypatch.setattr(sr, "CACHE_DIR", tmp_path)

    called = []
    monkeypatch.setattr(sr.subprocess, "call", lambda *a, **k: called.append(a) or 0)
    sr._seed_cache_from_bucket()
    assert called == []


def test_seed_cache_pulls_bucket_when_missing(tmp_path, monkeypatch):
    """Cold start: rclone copyto bucket -> local cache."""
    import sync_running as sr

    cache = tmp_path / "splits.json"
    monkeypatch.setattr(sr, "CACHE_FILE", cache)
    monkeypatch.setattr(sr, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(sr, "load_extra", lambda *a, **k: _bucket_cfg())
    monkeypatch.setattr(sr, "resolve_remote", lambda *a, **k: "r2")

    cmds = []
    monkeypatch.setattr(sr.subprocess, "call", lambda *a, **k: cmds.append(a[0]) or 0)
    sr._seed_cache_from_bucket()

    assert cmds == [
        [
            "rclone",
            "copyto",
            "r2:web-assets/data/metadata/running/splits.json",
            str(cache),
            "--s3-no-check-bucket",
            "--quiet",
        ],
    ]


def test_seed_cache_rclone_failure_does_not_raise(tmp_path, monkeypatch, capsys):
    """A failed seed (e.g. no bucket creds) falls back to a full sync."""
    import sync_running as sr

    cache = tmp_path / "splits.json"
    monkeypatch.setattr(sr, "CACHE_FILE", cache)
    monkeypatch.setattr(sr, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(sr, "load_extra", lambda *a, **k: _bucket_cfg())
    monkeypatch.setattr(sr, "resolve_remote", lambda *a, **k: "r2")
    monkeypatch.setattr(sr.subprocess, "call", lambda *a, **k: 1)  # rclone fails

    sr._seed_cache_from_bucket()  # must not raise
    assert "full sync" in capsys.readouterr().err


def test_seed_cache_missing_mapping_skips(tmp_path, monkeypatch):
    """No running mapping configured -> no rclone call."""
    import sync_running as sr

    cache = tmp_path / "splits.json"
    monkeypatch.setattr(sr, "CACHE_FILE", cache)
    monkeypatch.setattr(sr, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(sr, "load_extra", lambda *a, **k: {"mappings": []})

    called = []
    monkeypatch.setattr(sr.subprocess, "call", lambda *a, **k: called.append(a) or 0)
    sr._seed_cache_from_bucket()
    assert called == []


def test_seed_cache_timeout_falls_back(tmp_path, monkeypatch, capsys):
    """A hung rclone (subprocess.TimeoutExpired) falls back to a full sync."""
    import subprocess as _subprocess

    import sync_running as sr

    cache = tmp_path / "splits.json"
    monkeypatch.setattr(sr, "CACHE_FILE", cache)
    monkeypatch.setattr(sr, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(sr, "load_extra", lambda *a, **k: _bucket_cfg())
    monkeypatch.setattr(sr, "resolve_remote", lambda *a, **k: "r2")

    def _hang(*a, **k):
        raise _subprocess.TimeoutExpired(cmd=a[0], timeout=k.get("timeout"))

    monkeypatch.setattr(sr.subprocess, "call", _hang)
    sr._seed_cache_from_bucket()  # must not raise
    assert "falling back to full sync" in capsys.readouterr().err


# ---------------------------------------------------------------------------
#  running_macros: data helpers + rendering
# ---------------------------------------------------------------------------

import running_macros as rm  # noqa: E402


def _activity(name, stamp, km=5.0, hr=130, sec=1500, elev=10):
    m, s = divmod(sec, 60)
    return {
        "name": name,
        "distance": km * 1000,
        "moving_time": f"{m}:{s:02d}",
        "elevation_gain": elev,
        "average_heartrate": hr,
        "start_date": stamp,
        "start_date_local": stamp,
    }


def test_runs_sorted_newest_first():
    data = {
        "activities": [
            _activity("old", "2025-10-15 14:21:46"),
            _activity("new", "2026-08-02 14:06:45"),
        ]
    }
    assert [a["name"] for a in rm._runs(data)] == ["new", "old"]


def test_recent_returns_last_five():
    """_recent shows the last 5 activities regardless of age."""
    data = {"activities": [_activity(f"a{i}", f"2026-01-0{i} 10:00:00") for i in range(1, 7)]}
    out = rm._recent(data)
    # 5 data rows in the HTML table
    assert out.count("<tr>") == 5 + 1  # 5 data + 1 header
    assert "2026-01-06" in out  # newest included
    assert "2026-01-01" not in out  # 6th oldest dropped


def test_activity_table_html_and_escaping():
    """_activity_table: HTML table; no raw name is ever rendered (no name column)."""
    runs = [
        {
            "name": "<img src=x onerror=alert(1)>",
            "distance": 5000,
            "moving_time": "0:25:00",
            "average_heartrate": 123,
            "start_date_local": "2026-08-02 22:06:45",
        }
    ]
    out = rm._activity_table(runs)
    assert "<table>" in out
    assert "名称" not in out  # name column removed
    assert "<img" not in out  # never a raw name rendered
    # 4 header cells + 1 row of 4 cells
    assert out.count("</th>") == 4
    assert out.count("<td") == 4


def test_activity_table_uses_elapsed_pace_and_exposes_run_data():
    """No build-time splits: pace = running.yml elapsed; rows carry data attrs
    so client-side JS can correct pace from the R2 splits copy."""
    runs = [
        {
            "run_id": 1,
            "name": "Pudong",
            "distance": 5000,
            "moving_time": "0:50:00",  # 3000s elapsed / 5km = 10:00
            "average_heartrate": 120,
            "start_date_local": "2026-08-02 22:06:45",
        }
    ]
    out = rm._activity_table(runs, splits_url="https://bucket/splits.json")
    assert "10:00" in out
    assert "data-run-id='1'" in out
    assert "data-name='Pudong'" in out
    assert "data-splits-url='https://bucket/splits.json'" in out
    assert "openPaceDialog" not in out
    assert "openRouteMap" not in out


def test_activity_table_no_dialog_nodes_or_buttons():
    """Buttons/dialogs are created lazily by JS — the macro emits neither."""
    runs = [
        {
            "run_id": 1,
            "name": "Pudong",
            "distance": 5000,
            "moving_time": "0:25:00",
            "average_heartrate": 123,
            "start_date_local": "2026-08-02 22:06:45",
        }
    ]
    out = rm._activity_table(runs, splits_url="https://bucket/splits.json")
    assert "<dialog" not in out
    assert "data-pace=" not in out
    assert "data-route-id=" not in out
    assert "data-run-id='1'" in out
    assert "data-km='5.00'" in out
    assert "data-pace-cell" in out


def test_activity_table_data_name_escaped_in_attribute():
    """Names land only in escaped data attributes — never raw HTML."""
    runs = [
        {
            "run_id": 9,
            "name": "O'Brien's \"Night\" Run",
            "distance": 3000,
            "moving_time": "0:20:00",
            "average_heartrate": 120,
            "start_date_local": "2026-08-20 22:00:00",
        }
    ]
    out = rm._activity_table(runs)
    assert "<img" not in out
    assert "data-name='O&#x27;Brien&#x27;s &quot;Night&quot; Run'" in out


def test_running_recent_routes_uses_last_n_not_build_window():
    """running_recent_routes picks the last N routes; no datetime.now() window."""
    import inspect

    captured = {}

    class Env:
        def macro(self, fn):
            captured[fn.__name__] = fn
            return fn

    health_macros.define_env(Env())
    src = inspect.getsource(captured["running_recent_routes"])
    assert "datetime.now" not in src
    assert "days=" not in src
    assert "max_routes" in src


def test_all_collapsed_details():
    data = {
        "activities": [
            _activity("a", "2026-08-02 14:06:45"),
            _activity("b", "2026-08-01 14:06:45"),
        ]
    }
    out = rm._all(data)
    assert out.startswith('??? "')
    assert "All Activities (2)" in out
    assert "a" in out and "b" in out


def test_year_table_html():
    data = {
        "activities": [
            _activity("y2025", "2025-10-15 22:21:46"),
            _activity("y2026", "2026-08-02 22:06:45"),
        ]
    }
    out = rm._year_table(data)
    assert "<table>" in out
    assert "2026" in out and "2025" in out
    # newest year row first
    assert out.index("2026") < out.index("2025")


def test_monthly_chart_merges_distance_bar_and_hr_line():
    data = {
        "activities": [
            _activity("a", "2026-08-02 14:06:45", km=5.0, hr=140),
            _activity("b", "2026-07-15 14:06:45", km=8.0, hr=150),
        ]
    }
    out = rm._monthly_chart(data)
    assert 'title "Monthly Distance (km) & Avg HR (bpm) — 2026"' in out
    assert 'x-axis ["Jul", "Aug"]' in out
    assert "bar [8.0, 5.0]" in out
    assert "line [150, 140]" in out


def test_parse_moving_time_and_formatters():
    assert rm._parse_moving_time("0:19:42.196000") == pytest.approx(1182.196)
    assert rm._parse_moving_time("") is None
    assert rm._parse_moving_time(None) is None

    assert rm._fmt_hours_minutes(45240) == "12h 34m"
    assert rm._fmt_hours_minutes(3000) == "50m"
    assert rm._fmt_pace(332) == "5:32"
    assert rm._fmt_pace(0) == "—"


def test_load_data_empty_comment_only_file_returns_empty(tmp_path):
    data_dir = tmp_path / "notes" / "health" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "running.yml").write_text("# only a comment\n", encoding="utf-8")
    env = type("Env", (), {"conf": {"docs_dir": str(tmp_path)}})()
    assert rm._load_data(env) == {}


def test_recent_routes_embeds_runs_and_config(tmp_path):
    """running_recent_routes ships the container with recent runs + config;
    the map itself is rendered client-side from the R2 splits copy."""
    data_dir = tmp_path / "notes" / "health" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "running.yml").write_text(
        "activities:\n"
        "  - name: a\n    run_id: 1\n    distance: 5000\n    moving_time: '0:25:00'\n"
        "    average_heartrate: 120\n    start_date_local: '2026-08-02 22:06:45'\n"
        "  - name: b\n    run_id: 2\n    distance: 3000\n    moving_time: '0:20:00'\n"
        "    average_heartrate: 110\n    start_date_local: '2026-08-01 20:00:00'\n",
        encoding="utf-8",
    )

    class Env:
        def __init__(self, conf):
            self.conf = conf
            self.registered = {}

        def macro(self, fn):
            self.registered[fn.__name__] = fn
            return fn

    env = Env(
        {
            "docs_dir": str(tmp_path),
            "extra": {
                "moment": {
                    "map": {
                        "pmtiles_prefix": "https://x/pmtiles/",
                        "glyphs_url": "https://x/glyphs/",
                        "regions": {"shanghai": {"bbox": [120.8, 30.6, 122.2, 31.8]}},
                    }
                }
            },
        }
    )
    health_macros.define_env(env)
    out = env.registered["running_recent_routes"](max_routes=10)
    assert 'id="inline-routes-map"' in out
    assert "data-runs=" in out
    assert "data-splits-url=" in out
    assert "data-pmtiles='https://x/pmtiles/'" in out
    assert "data-glyphs='https://x/glyphs/'" in out
    assert "data-regions=" in out
    assert "data-routes=" not in out  # polylines are no longer embedded at build


def test_macros_render_no_data_hint_when_empty():
    hint = rm._no_data()
    for fn in (rm._year_table, rm._recent, rm._all, rm._monthly_chart):
        assert fn({}) == hint


def test_synced_note_variants():
    note = rm._synced_note({"activities": [{"name": "a"}]})
    assert note != rm._no_data()
    assert "sync-running" in note
    with_timestamp = rm._synced_note({"synced_at": "2026-08-03T00:00:00+08:00"})
    assert "数据同步于" in with_timestamp


def test_health_macros_registers_running_macros():
    class Env:
        def __init__(self):
            self.registered = {}

        def macro(self, fn):
            self.registered[fn.__name__] = fn
            return fn

    env = Env()
    health_macros.define_env(env)
    for name in (
        "running_year_table",
        "running_monthly_chart",
        "running_recent",
        "running_all",
        "running_synced_at",
        "running_calendar_heatmap",
        "running_recent_routes",
    ):
        assert name in env.registered
    # superseded by the lazy pace dialog + heatmap summary line
    assert "running_summary" not in env.registered
    assert "running_pace_section" not in env.registered
