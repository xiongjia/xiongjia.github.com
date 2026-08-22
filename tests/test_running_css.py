"""Palette parity tests: the Running Track heatmap (running.css) must stay in
sync with the Moment stats heatmap (moment_stats.html).

Both grids share one green ramp (light mode + slate dark overrides); if one
side is edited, the other must follow — this test pins them together so the
drift is caught in CI.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNNING_CSS = REPO / "docs" / "assets" / "stylesheets" / "running.css"
MOMENT_TEMPLATE = REPO / "plugins" / "mkdocs_moment" / "templates" / "moment_stats.html"


def _hexes(text: str) -> list[str]:
    """Hex colors inside `background:` declarations, in declaration order.

    Scoped to background fills so the pin only sees palette colors — unrelated
    colors added to the block (borders, shadows, ...) don't trip the compare.
    """
    return re.findall(r"background:\s*[^;]*?(#[0-9a-fA-F]{6})\b", text)


def _require(text: str, marker: str, path: Path) -> None:
    """Fail with a clear message when a structural anchor is missing."""
    if marker not in text:
        raise AssertionError(
            f"anchor {marker!r} not found in {path.name} — heatmap palette "
            "structure changed; update the slice anchors in this test"
        )


def _moment_cell_block(tpl: str) -> str:
    """Slice of moment_stats.html CSS covering the heatmap cell rules."""
    _require(tpl, ".moment-stats__cell {", MOMENT_TEMPLATE)
    _require(tpl, ".moment-stats__legend", MOMENT_TEMPLATE)
    start = tpl.index(".moment-stats__cell {")
    end = tpl.index(".moment-stats__legend")
    return tpl[start:end]


def _running_cell_block(css: str) -> str:
    """Slice of running.css covering the rh-cell rules (light + slate)."""
    _require(css, ".running-heatmap .rh-cell", RUNNING_CSS)
    return css[css.index(".running-heatmap .rh-cell") :]


def test_heatmap_palette_matches_moment_stats():
    css = RUNNING_CSS.read_text(encoding="utf-8")
    tpl = MOMENT_TEMPLATE.read_text(encoding="utf-8")
    # Ordered compare: both files list light l1–l4 then slate l1–l4, with the
    # lightest base hex (#e0e0e0) first — a reorder or palette edit breaks this.
    assert _hexes(_running_cell_block(css)) == _hexes(_moment_cell_block(tpl))


def test_heatmap_base_cell_colors_match_moment_stats():
    css = RUNNING_CSS.read_text(encoding="utf-8")
    tpl = MOMENT_TEMPLATE.read_text(encoding="utf-8")
    # Base (no-run) cell: theme-adaptive lightest fg in light mode, translucent
    # white in slate mode — same tokens on both sides.
    for token in ("var(--md-default-fg-color--lightest, #e0e0e0)", "rgba(255, 255, 255, 0.12)"):
        assert token in css
        assert token in _moment_cell_block(tpl)
