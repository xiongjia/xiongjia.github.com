"""Unit tests for the weight tracking macros.

Covers the i18n label defaults/overrides and the week-row rendering in the
weekly details table (`第N周` prefix/suffix style).
"""

import sys
from pathlib import Path

# the macros live under docs/notes/health/macros/ (loaded by the mkdocs macros
# plugin at build time); tests must add the dir explicitly
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "docs" / "notes" / "health" / "macros"),
)

from weight_macros import _chart, _get_labels, _table  # noqa: E402

from shared.chart_labels import label_budget  # noqa: E402


def _data(**overrides) -> dict:
    """Minimal dataset: one week starting Monday 2026-07-27."""
    base = {
        "cm": 180,
        "start_date": "2026-07-27",
        "weeks": [{"days": [82.0, 81.5, None, None, None, None, None]}],
    }
    base.update(overrides)
    return base


def test_labels_defaults():
    labels = _get_labels({})
    assert labels["table_row_prefix"] == "W"
    assert labels["table_row_suffix"] == ""


def test_labels_override_merges_with_defaults():
    labels = _get_labels({"labels": {"table_row_prefix": "第", "table_row_suffix": "周"}})
    assert labels["table_row_prefix"] == "第"
    assert labels["table_row_suffix"] == "周"
    # untouched defaults are still present
    assert labels["table_col_week"] == "Week"


def test_table_english_defaults():
    out = _table(_data())
    assert "W1 (07-27-08-02)" in out
    assert "| W1 | 07-27-08-02 |" in out


def test_table_chinese_week_label():
    out = _table(_data(labels={"table_row_prefix": "第", "table_row_suffix": "周"}))
    assert "第1周 (07-27-08-02)" in out
    assert "| 第1周 | 07-27-08-02 |" in out


def _weeks(n: int) -> list[dict]:
    """n weeks of daily weights."""
    return [{"days": [82.0, 81.5, 82.0, 81.5, 82.0, 81.5, 82.0]} for _ in range(n)]


def _x_labels(out: str) -> list[str]:
    """Extract the x-axis labels from the rendered chart source.

    Blanked slots come back as empty strings (the placeholder is a single
    space, which is stripped here).
    """
    raw = out.split("x-axis [", 1)[1].split("]", 1)[0]
    return [part.strip().strip('"').strip() for part in raw.split(",")]


def _line_values(out: str) -> list[str]:
    """Extract the plotted line values from the rendered chart source."""
    raw = out.split("line [", 1)[1].split("]", 1)[0]
    return [part.strip() for part in raw.split(",")]


def test_chart_labels_use_short_dates():
    out = _chart(_data(weeks=_weeks(3)))
    assert _x_labels(out) == ["07-27", "08-03", "08-10"]
    assert "2026-07-27" not in out


def test_chart_labels_span_years_with_year_prefix():
    # 30 weeks from 2026-07-27 crosses into 2027: MM-DD alone would be ambiguous
    labels = _x_labels(_chart(_data(weeks=_weeks(30))))
    kept = [label for label in labels if label]
    assert kept[-1] == "27-02-15"  # the latest week keeps its label
    assert all(len(label) == 8 for label in kept)


def test_chart_labels_stay_aligned_with_data_points():
    for weeks in (3, 13, 30, 60):
        out = _chart(_data(weeks=_weeks(weeks)))
        # mermaid maps x labels to points positionally — a short label list
        # would shift every date, so lengths must match exactly
        assert len(_x_labels(out)) == len(_line_values(out)) == weeks


def test_chart_thins_labels_when_weeks_grow():
    labels = _x_labels(_chart(_data(weeks=_weeks(30))))
    kept = [label for label in labels if label]
    assert 1 < len(kept) <= label_budget(["26-07-27"])
    assert all(len(label) == 8 for label in kept)  # YY-MM-DD once years are spanned


def test_chart_keeps_latest_week_labeled():
    for weeks in (3, 13, 14, 30, 60):
        labels = _x_labels(_chart(_data(weeks=_weeks(weeks))))
        assert labels[-1], f"latest week label missing for {weeks} weeks"
