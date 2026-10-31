"""Mermaid xychart x-axis label helpers.

``xychart-beta`` draws one fixed-width label per data point and never rotates
or wraps them, so labels wider than the tick spacing overlap and become
unreadable. Series that can grow unbounded (weekly weight, monthly moment
counts) use :func:`thin_labels` to keep only every ``step``-th label.

A dropped label still has to occupy its slot, otherwise Mermaid shifts the
remaining labels away from their data points. Mermaid 10.9 — the version
pinned in ``mkdocs.yml`` — rejects ``""`` as an axis label (parser error),
hence :func:`blank_label` as an invisible placeholder.

The placeholder must be **unique per slot**, not one shared string. ``xychart``
plots the data points on a ``d3.scaleBand`` keyed by the label text, and a band
scale interns its domain: repeated identical labels collapse into one band and
those points are then drawn at ``scale(label) || range[0]`` — the left edge of
the plot area. A single-space placeholder (the previous approach) therefore
zigzagged every dropped point back to the left edge; it only stayed invisible
while a series fit the label budget, because ``step`` is 1 and nothing is
dropped until it does not. :data:`BLANK_CHAR` is a zero-width space: 0px wide
(so the axis label padding is unaffected) and unique when repeated
``index + 1`` times.

Consumers emit the chart inside a preformatted block (``<pre class="mermaid">``
for fenced diagrams, ``<div class="mermaid" pre>`` for generated pages), which
the site's HTML minifier preserves verbatim — placeholders included (U+200B is
not HTML whitespace, so it is never collapsed). The version pin plus the
self-hosted bundle keep that parser guarantee; Material's own mermaid-11
fallback (unpkg) is only reached when the pinned bundle and its CDN are both
unavailable, and is not covered by it.

The geometry constants are in pixels, measured from that same version's default
``xychart``: a 700×500 canvas with ~592px of plot area and a 14px label font.
Mermaid renders that canvas at its natural 700px on desktop and scales it down
uniformly on narrow screens, so label-width/spacing ratios — and therefore
these constants — hold at any viewport width. Character width differs by font —
6.9px/char measured with a bare sans-serif, 7.8px/char on the built page with
the theme font — so :data:`CHAR_WIDTH_PX` stays at the lower, harness-measured
estimate: :func:`label_budget` counts label intervals conservatively and
:data:`LABEL_GAP_PX` absorbs the rest (a 12-label ``MM-DD`` axis keeps ~15px of
slack in the theme font). Re-measure them when the Mermaid version is bumped
*or* when ``mermaidConfig`` gains an ``xychart`` override (``width``,
``labelFontSize``, …) — ``tests/test_chart_labels.py`` pins the validated
version as a tripwire.
"""

import math
from collections.abc import Sequence

PLOT_WIDTH_PX = 590
CHAR_WIDTH_PX = 7
LABEL_GAP_PX = 13
# U+200B ZERO WIDTH SPACE: renders nothing, is not HTML whitespace (so the
# minifier keeps it) and survives mermaid's label handling
BLANK_CHAR = "\u200b"


def blank_label(index: int) -> str:
    """Invisible placeholder for the label dropped at ``index``.

    The repeat count makes it unique per slot — a shared placeholder would
    collapse every dropped slot onto one band and drag those data points to the
    left edge of the plot (see the module docstring). Zero-width, so the axis
    label padding measures it as 0px however long it gets.
    """
    return BLANK_CHAR * (index + 1)


def is_blank(label: str) -> bool:
    """Whether ``label`` is a placeholder (from :func:`blank_label`) or empty."""
    return not label.strip(BLANK_CHAR)


def label_budget(labels: Sequence[str]) -> int:
    """How many of ``labels`` fit side by side without touching.

    Sizing uses the widest label, the same one Mermaid reserves space for, so
    a wide format (``YY-MM-DD``) thins sooner than a narrow one (``MM-DD``).

    Placeholders are skipped (they render 0px wide), so the budget of an
    already-thinned list matches its raw one — that is what makes
    :func:`thin_labels` idempotent. The caller's label format is expected to be
    uniform, which holds for every caller here (the format is chosen per
    chart, not per point).
    """
    real = [label for label in labels if not is_blank(label)]
    if not real:
        return 2
    needed = max(len(label) for label in real) * CHAR_WIDTH_PX + LABEL_GAP_PX
    return max(2, PLOT_WIDTH_PX // needed)


def thin_labels(labels: Sequence[str]) -> list[str]:
    """Blank every label that would otherwise overlap its neighbour.

    The newest (last) label is always kept — the most recent data point is the
    one a reader looks for — and earlier ones every ``step``-th position going
    back from it. Dropped positions become :func:`blank_label` placeholders, so
    the returned list stays index-aligned with the data points while every
    entry remains a unique band-scale key.
    """
    labels = list(labels)
    if not labels:
        return []
    step = max(1, math.ceil(len(labels) / label_budget(labels)))
    last = len(labels) - 1
    return [
        label if (last - index) % step == 0 else blank_label(index)
        for index, label in enumerate(labels)
    ]


def format_x_axis(labels: Sequence[str]) -> str:
    """Render ``labels`` as a Mermaid ``x-axis [...]`` payload (quoted, joined)."""
    return ", ".join(f'"{label}"' for label in thin_labels(labels))
