"""Mermaid xychart x-axis label helpers.

``xychart-beta`` draws one fixed-width label per data point and never rotates
or wraps them, so labels wider than the tick spacing overlap and become
unreadable. Series that can grow unbounded (weekly weight, monthly moment
counts) use :func:`thin_labels` to keep only every ``step``-th label.

A dropped label still has to occupy its slot, otherwise Mermaid shifts the
remaining labels away from their data points. Mermaid 10.9 — the version
pinned in ``mkdocs.yml`` — rejects ``""`` as an axis label but accepts a single
space, hence :data:`BLANK_LABEL` as an invisible placeholder. Consumers emit the
chart inside a preformatted block (``<pre class="mermaid">`` for fenced
diagrams, ``<div class="mermaid" pre>`` for generated pages), which the site's
HTML minifier preserves verbatim — placeholders included. The version pin plus
the self-hosted bundle keep that parser guarantee; Material's own mermaid-11
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
BLANK_LABEL = " "


def label_budget(labels: Sequence[str]) -> int:
    """How many of ``labels`` fit side by side without touching.

    Sizing uses the widest label, the same one Mermaid reserves space for, so
    a wide format (``YY-MM-DD``) thins sooner than a narrow one (``MM-DD``).

    Expects a raw, single-format label list: placeholders are one character
    wide, so a list whose widest label was already blanked out would size
    differently (and thinning is only idempotent while the format is uniform —
    which holds for every caller here, as the format is chosen per chart, not
    per point).
    """
    if not labels:
        return 2
    needed = max(len(label) for label in labels) * CHAR_WIDTH_PX + LABEL_GAP_PX
    return max(2, PLOT_WIDTH_PX // needed)


def thin_labels(labels: Sequence[str]) -> list[str]:
    """Blank every label that would otherwise overlap its neighbour.

    The newest (last) label is always kept — the most recent data point is the
    one a reader looks for — and earlier ones every ``step``-th position going
    back from it. Dropped positions become :data:`BLANK_LABEL`, so the returned
    list stays index-aligned with the data points.
    """
    labels = list(labels)
    if not labels:
        return []
    step = max(1, math.ceil(len(labels) / label_budget(labels)))
    last = len(labels) - 1
    return [
        label if (last - index) % step == 0 else BLANK_LABEL for index, label in enumerate(labels)
    ]


def format_x_axis(labels: Sequence[str]) -> str:
    """Render ``labels`` as a Mermaid ``x-axis [...]`` payload (quoted, joined)."""
    return ", ".join(f'"{label}"' for label in thin_labels(labels))
