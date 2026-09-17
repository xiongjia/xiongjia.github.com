"""Unit tests for shared/chart_labels.py (Mermaid x-axis label thinning)."""

import re
from pathlib import Path

from shared.chart_labels import (
    BLANK_LABEL,
    CHAR_WIDTH_PX,
    PLOT_WIDTH_PX,
    format_x_axis,
    label_budget,
    thin_labels,
)

MKDOCS_YML = Path(__file__).resolve().parent.parent / "mkdocs.yml"
# the geometry and the blank-label trick were measured/validated here
MERMAID_VERSION_VALIDATED = "10.9.0"
# character width on the BUILT page (theme font + Material CSS), wider than the
# bare-sans-serif estimate CHAR_WIDTH_PX uses — see shared/chart_labels.py
THEME_FONT_CHAR_WIDTH_PX = 7.8


def test_geometry_tied_to_pinned_mermaid_version():
    """Tripwire, not a functional test: a Mermaid upgrade invalidates both the
    measured geometry and the assumption that a single-space label parses."""
    # block-style pin (`mermaid2:` then `version:`); the assert below catches a
    # reformatting that would silently make this test vacuous
    pinned = re.search(r"mermaid2:\s*\n\s*version:\s*([0-9.]+)", MKDOCS_YML.read_text("utf-8"))
    assert pinned, "mermaid2 version pin not found in mkdocs.yml"
    assert pinned.group(1) == MERMAID_VERSION_VALIDATED, (
        f"mermaid is pinned to {pinned.group(1)} but the label geometry was measured on "
        f"{MERMAID_VERSION_VALIDATED} — re-measure PLOT_WIDTH_PX / CHAR_WIDTH_PX and re-check "
        "that a single-space x-axis label still parses, then update this constant"
    )


def _dates(count: int, *, chars: int = 5) -> list[str]:
    """``count`` synthetic labels (5-char ``MM-DD`` by default, 8-char ``YY-MM-DD``)."""
    return [f"{index:0{chars}d}" for index in range(count)]


def test_budget_empty_labels():
    assert label_budget([]) == 2


def test_budget_scales_with_label_width():
    # a wider label format leaves room for fewer of them
    assert label_budget(["07-27"]) > label_budget(["26-07-27"])


def test_budget_matches_measured_geometry():
    # measured on mermaid 10.9's default xychart (12 five-char labels / 8
    # eight-char labels); re-measure and update both when that changes
    assert label_budget(["07-27"]) == 12
    assert label_budget(["26-07-27"]) == 8


def test_budget_unchanged_by_thinning():
    # placeholders are one character wide, so they can never widen the
    # widest-label estimate — re-thinning a uniform-format list is stable
    labels = _dates(60)
    assert label_budget(thin_labels(labels)) == label_budget(labels)


def test_thin_labels_is_idempotent():
    for count, chars in ((30, 5), (30, 8), (60, 5), (104, 8)):
        once = thin_labels(_dates(count, chars=chars))
        assert thin_labels(once) == once


def test_thin_labels_empty_input():
    assert thin_labels([]) == []


def test_thin_labels_keeps_short_series_intact():
    labels = _dates(8)
    assert thin_labels(labels) == labels


def test_thin_labels_preserves_length_and_alignment():
    labels = _dates(60)
    thinned = thin_labels(labels)
    assert len(thinned) == len(labels)
    kept = [index for index, label in enumerate(thinned) if label != BLANK_LABEL]
    # kept positions are evenly spaced and keep their original labels
    assert all(labels[index] == thinned[index] for index in kept)
    assert {b - a for a, b in zip(kept, kept[1:])} == {kept[1] - kept[0]}


def test_thin_labels_bounded_by_budget():
    labels = _dates(60)
    kept = [label for label in thin_labels(labels) if label != BLANK_LABEL]
    assert len(kept) <= label_budget(labels)


def test_thin_labels_always_keeps_latest():
    for count in (1, 2, 3, 12, 13, 24, 60, 500):
        thinned = thin_labels(_dates(count))
        assert thinned[-1] == _dates(count)[-1]


def test_thin_labels_placeholder_is_single_space():
    # mermaid 10.9 rejects "" as a label but accepts a space
    thinned = thin_labels(_dates(60))
    assert set(thinned) - set(_dates(60)) == {BLANK_LABEL}


def test_thinned_spacing_exceeds_label_width():
    """Browser-free proxy for the headless-DOM check: kept labels end up spaced
    wider than the labels themselves, so they cannot touch.

    Guards the thinning math against both the harness font estimate and the
    wider theme font measured on the built page (see THEME_FONT_CHAR_WIDTH_PX).
    It reuses PLOT_WIDTH_PX, so it still cannot tell whether that constant
    matches a (possibly upgraded) Mermaid.
    """
    for count, chars in ((13, 5), (30, 8), (60, 5), (60, 8), (500, 5)):
        thinned = thin_labels(_dates(count, chars=chars))
        kept = [index for index, label in enumerate(thinned) if label != BLANK_LABEL]
        step = kept[1] - kept[0] if len(kept) > 1 else 1
        spacing = PLOT_WIDTH_PX / max(1, count - 1) * step
        assert spacing > chars * CHAR_WIDTH_PX, f"{count} labels of {chars} chars would overlap"
        assert spacing > chars * THEME_FONT_CHAR_WIDTH_PX, (
            f"{count} labels of {chars} chars would overlap in the theme font"
        )


def test_format_x_axis_quotes_and_joins():
    assert format_x_axis(["07-27", "08-03"]) == '"07-27", "08-03"'


def test_format_x_axis_keeps_blank_slots():
    labels = _dates(60)
    blanks = [label for label in thin_labels(labels) if label == BLANK_LABEL]
    assert format_x_axis(labels).count(f'"{BLANK_LABEL}"') == len(blanks)
