"""Unit tests for the daily weight update script (scripts/update_weight.py)."""

import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml
from update_weight import _resolve_date, apply_update  # conftest adds scripts/ to sys.path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "update_weight.py"


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the CLI script in a subprocess from `cwd`."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


BASE = """\
# Height: set once
cm: 176

start_date: "2026-07-27"

weeks:
  # Week 1 — Mon 2026-07-27
  - days: [null, 82.35, 81.50, 82.90, 82.40, 82.40, 81.90]
  # Week 2 — Mon 2026-08-03
  - days: [81.90, 81.90, 81.60, 81.90, 81.90, null, null]
"""


def test_update_existing_day_overwrites():
    out, info = apply_update(BASE, 82.0, date(2026, 7, 29))  # Wed of week 1
    assert info.week_index == 0
    assert info.day_index == 2
    assert info.appended == 0
    assert info.overwrote == pytest.approx(81.5)
    assert "- days: [null, 82.35, 82.00, 82.90, 82.40, 82.40, 81.90]" in out


def test_update_null_day_keeps_comment_lines():
    out, info = apply_update(BASE, 82.0, date(2026, 8, 8))  # Sat of week 2 (null)
    assert info.week_index == 1
    assert info.day_index == 5
    assert info.overwrote is None
    assert "# Week 1 — Mon 2026-07-27" in out
    assert "# Week 2 — Mon 2026-08-03" in out
    assert "- days: [81.90, 81.90, 81.60, 81.90, 81.90, 82.00, null]" in out


def test_sunday_belongs_to_same_week():
    out, info = apply_update(BASE, 82.0, date(2026, 8, 2))  # Sun of week 1
    assert info.week_index == 0
    assert info.day_index == 6
    assert "- days: [null, 82.35, 81.50, 82.90, 82.40, 82.40, 82.00]" in out


def test_append_single_new_week():
    out, info = apply_update(BASE, 82.0, date(2026, 8, 10))  # Mon of week 3
    assert info.week_index == 2
    assert info.appended == 1
    assert info.overwrote is None
    assert "# Week 3 — Mon 2026-08-10" in out
    assert out.count("- days:") == 3
    assert "- days: [82.00, null, null, null, null, null, null]" in out


def test_append_multiple_new_weeks():
    out, info = apply_update(BASE, 82.0, date(2026, 8, 24))  # Mon of week 5
    assert info.appended == 3
    assert out.count("- days:") == 5
    assert "# Week 3 — Mon 2026-08-10" in out
    assert "# Week 4 — Mon 2026-08-17" in out
    assert "# Week 5 — Mon 2026-08-24" in out


def test_empty_weeks_section_creates_entries():
    empty = 'cm: 176\nstart_date: "2026-07-27"\nweeks:\n'
    out, info = apply_update(empty, 82.0, date(2026, 7, 29))  # Wed of week 1
    assert info.appended == 1
    assert "- days: [null, null, 82.00, null, null, null, null]" in out


def test_no_weeks_key_creates_section():
    no_weeks = 'cm: 176\nstart_date: "2026-07-27"\n'
    out, info = apply_update(no_weeks, 82.0, date(2026, 7, 29))  # Wed of week 1
    assert info.appended == 1
    assert "weeks:" in out
    assert "# 7 days per week; use null for missed days" in out
    assert "- days: [null, null, 82.00, null, null, null, null]" in out


def test_append_then_overwrite_does_not_glue_lines():
    # regression: rewriting a week after appending must keep the following
    # week comment on its own line (splitlines re-merges inserted separators)
    out, _ = apply_update(BASE, 82.0, date(2026, 8, 10))  # append week 3
    out, info = apply_update(out, 83.0, date(2026, 7, 28))  # overwrite Tue w1
    assert info.overwrote == pytest.approx(82.35)
    assert "- days: [null, 83.00, 81.50, 82.90, 82.40, 82.40, 81.90]\n" in out
    assert "- days: [81.90, 81.90, 81.60, 81.90, 81.90, null, null]\n" in out
    assert "# Week 3 — Mon 2026-08-10\n" in out
    # week 3 must still be an intact 7-item list after the overwrite
    assert "- days: [82.00, null, null, null, null, null, null]\n" in out


def test_apply_update_rejects_invalid_weight():
    with pytest.raises(ValueError, match="positive"):
        apply_update(BASE, -5.0, date(2026, 7, 29))
    with pytest.raises(ValueError, match="positive"):
        apply_update(BASE, 0.0, date(2026, 7, 29))


def test_append_matches_existing_indentation():
    content = (
        "cm: 176\n"
        'start_date: "2026-07-27"\n'
        "weeks:\n"
        "    # Week 1 — Mon 2026-07-27\n"
        "    - days: [null, 82.35, 81.50, 82.90, 82.40, 82.40, 81.90]\n"
    )
    out, info = apply_update(content, 82.0, date(2026, 8, 3))  # Mon of week 2
    assert info.appended == 1
    assert "    # Week 2 — Mon 2026-08-03\n" in out
    assert "    - days: [82.00, null, null, null, null, null, null]\n" in out


def test_bool_value_produces_no_overwrite_notice():
    content = BASE.replace("82.35", "true")  # Tue of week 1 becomes a YAML bool
    out, info = apply_update(content, 82.0, date(2026, 7, 28))
    assert info.overwrote is None
    assert "- days: [null, 82.00, 81.50, 82.90, 82.40, 82.40, 81.90]" in out


def test_date_before_start_rejected():
    with pytest.raises(ValueError, match="before the first week"):
        apply_update(BASE, 82.0, date(2026, 7, 20))


def test_invalid_weight_yaml_rejected():
    with pytest.raises(ValueError, match="invalid YAML"):
        apply_update("cm: 176\n  bad-indent: [\n", 82.0, date(2026, 7, 27))


def test_inline_empty_weeks_list_is_reused():
    # `weeks: []` must not produce a second `weeks:` key
    inline = 'cm: 176\nstart_date: "2026-07-27"\nweeks: []\n'
    out, info = apply_update(inline, 82.0, date(2026, 7, 29))  # Wed of week 1
    assert info.appended == 1
    assert out.count("weeks:") == 1
    assert "- days: [null, null, 82.00, null, null, null, null]" in out


def test_untouched_slots_preserve_raw_precision():
    content = BASE.replace(
        "[null, 82.35, 81.50, 82.90, 82.40, 82.40, 81.90]",
        "[null, 82.356, 81.50, 82.90, 82.40, 82.40, 81.90]",
    )
    out, _ = apply_update(content, 82.0, date(2026, 7, 29))  # Wed of week 1
    assert "82.356" in out  # untouched slot keeps its raw precision
    assert "- days: [null, 82.356, 82.00, 82.90, 82.40, 82.40, 81.90]" in out


def test_three_decimal_input_rounds_half_up():
    out, info = apply_update(BASE, 82.005, date(2026, 7, 29))
    assert info.overwrote == pytest.approx(81.5)
    assert "- days: [null, 82.35, 82.01, 82.90, 82.40, 82.40, 81.90]" in out


def test_resolve_date_defaults_to_today():
    now = datetime(2026, 7, 29, 10, 30)
    assert _resolve_date(None, now=now) == date(2026, 7, 29)
    assert _resolve_date("today", now=now) == date(2026, 7, 29)
    assert _resolve_date("今天", now=now) == date(2026, 7, 29)


def test_resolve_date_yesterday_and_iso():
    now = datetime(2026, 7, 29, 10, 30)
    assert _resolve_date("yesterday", now=now) == date(2026, 7, 28)
    assert _resolve_date("2026-08-05", now=now) == date(2026, 8, 5)


def test_resolve_date_unparseable():
    with pytest.raises(ValueError, match="unparseable"):
        _resolve_date("not-a-date")


# ---------------------------------------------------------------------------
#  CLI (main) level tests via subprocess
# ---------------------------------------------------------------------------


def _write_data(tmp_path: Path) -> None:
    data_dir = tmp_path / "docs" / "notes" / "health" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "weight.yml").write_text(BASE, encoding="utf-8")


def test_cli_positional_date(tmp_path):
    _write_data(tmp_path)
    res = _run_cli(["83.2", "2026-08-05"], tmp_path)
    assert res.returncode == 0
    out = (tmp_path / "docs/notes/health/data/weight.yml").read_text(encoding="utf-8")
    assert "- days: [81.90, 81.90, 83.20, 81.90, 81.90, null, null]" in out


def test_cli_date_flag(tmp_path):
    _write_data(tmp_path)
    res = _run_cli(["83.2", "--date", "2026-08-05"], tmp_path)
    assert res.returncode == 0
    out = (tmp_path / "docs/notes/health/data/weight.yml").read_text(encoding="utf-8")
    assert "- days: [81.90, 81.90, 83.20, 81.90, 81.90, null, null]" in out


def test_cli_default_today_succeeds(tmp_path):
    _write_data(tmp_path)
    res = _run_cli(["82.5"], tmp_path)
    assert res.returncode == 0
    assert "Recorded 82.50 kg" in res.stdout
    # the recorded slot depends on today's weekday, and extra weeks may be
    # appended if today falls beyond the fixture's 2-week range — just require
    # valid YAML with the recorded value present somewhere
    data = yaml.safe_load(
        (tmp_path / "docs/notes/health/data/weight.yml").read_text(encoding="utf-8")
    )
    assert len(data["weeks"]) >= 2
    all_days = [d for w in data["weeks"] for d in w["days"]]
    assert 82.5 in all_days


def test_cli_conflicting_dates_error(tmp_path):
    _write_data(tmp_path)
    res = _run_cli(["83.2", "2026-08-05", "--date", "2026-08-06"], tmp_path)
    assert res.returncode == 2
    assert "not both" in res.stderr


def test_cli_invalid_weight_error(tmp_path):
    _write_data(tmp_path)
    res = _run_cli(["-5"], tmp_path)
    assert res.returncode == 2
    assert "positive number" in res.stderr


def test_cli_unreadable_file_error(tmp_path):
    if os.name == "nt":
        pytest.skip("chmod semantics differ on Windows")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("running as root; chmod-based test is unreliable")
    _write_data(tmp_path)
    target = tmp_path / "docs/notes/health/data/weight.yml"
    target.chmod(0)
    try:
        res = _run_cli(["82.0"], tmp_path)
        assert res.returncode == 1
        assert "cannot read" in res.stderr
    finally:
        target.chmod(0o644)
