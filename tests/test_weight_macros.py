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

from weight_macros import _get_labels, _table  # noqa: E402


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
