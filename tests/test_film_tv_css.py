"""Regression locks for the film & TV dialog layout (film-tv.css / film-tv.js).

Everything pinned here was measured in a real browser (headless Edge over CDP)
after it had already shipped broken at least once: the site ships plain CSS/JS, so
each of these mistakes is *silent* — no error, just a spilling number or a value
column that sits ~29px off the label grid. The committed suite has no browser, so
what it can hold on to is the structure the measurements depend on: an anchor
selector, a rule order, a markup choice. Each test names the failure it prevents
and the measured number behind it.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSS = REPO / "docs" / "assets" / "stylesheets" / "film-tv.css"
DIALOG_JS = REPO / "docs" / "assets" / "javascripts" / "film-tv.js"


def _css() -> str:
    return CSS.read_text(encoding="utf-8")


def _require(text: str, marker: str, path: Path) -> None:
    """Fail with a clear message when a structural anchor is missing."""
    if marker not in text:
        raise AssertionError(
            f"anchor {marker!r} not found in {path.name} — the layout structure "
            "changed; re-measure in a browser before updating this test"
        )


def _rule_body(text: str, selector: str) -> str:
    """Body of the first rule whose selector contains *selector*."""
    match = re.search(rf"[^{{}}]*{re.escape(selector)}\s*\{{([^}}]*)\}}", text)
    if not match:
        raise AssertionError(f"no rule matching {selector!r} in {CSS.name}")
    return match.group(1)


def test_stat_number_keeps_a_plain_font_size_fallback():
    """A container-query-less browser must still get a usable number.

    `font-size: min(1.3rem, 17.5cqw)` is dropped whole when `cqw` is unsupported,
    and `white-space: nowrap` (universally supported) would then let a long value
    spill out of the card instead of wrapping — measured as an 0.8rem number
    hanging over its neighbour. So the plain rule stays outside `@supports` and
    only the sizing enhancement goes inside.
    """
    css = _css()
    _require(css, "@supports (container-type: inline-size)", CSS)
    plain, enhanced = css.split("@supports (container-type: inline-size)", 1)
    base = _rule_body(plain, ".film-tv-stat__number")
    assert "font-size: 1.3rem" in base, (
        "the plain `font-size: 1.3rem` fallback left the unguarded rule — without "
        "container-query support the number would inherit .md-typeset's 0.8rem"
    )
    assert "nowrap" not in base, (
        "`white-space: nowrap` moved into the fallback: a cqw-less browser would "
        "spill a long value out of its card instead of wrapping it"
    )
    cqw = _rule_body(enhanced, ".film-tv-stat__number")
    assert "min(1.3rem, 17.5cqw)" in cqw, "the container-query sizing lost its 1.3rem cap"
    assert "white-space: nowrap" in cqw, "the single-line number lost its nowrap"


def test_dialog_spacing_overrides_outrank_the_theme():
    """The dialog's own margins must out-specify Material's prose typography.

    All three of these were dead in the browser until the `[dir] .md-typeset`
    prefix was added, and each failure is silent:

    - `.md-typeset h3 { margin: 1.6em 0 .8em }` (0,1,1) beats
      `.film-tv-dialog__title` (0,1,0) — measured +32px above the title, which
      knocked it out of line with the cover.
    - `.md-typeset dl { margin: 1em 0 }` (0,1,1) beats `.film-tv-dialog__facts`
      (0,1,0) — measured +16px above the fact list.
    - `[dir=ltr] .md-typeset dd { margin-left: 1.875em }` (0,2,1) beats
      `.film-tv-dialog__fact dd` (0,1,1) — measured +29.25px left of every
      value, costing the long casts that much line width.
    """
    overrides = dict(re.findall(r"([^{}]*\[dir\][^{}]*\.md-typeset[^{}]*)\{([^}]*)\}", _css()))
    assert overrides, (
        "the [dir]-qualified dialog margin overrides are gone — Material's prose "
        "rules would take the dialog's spacing back"
    )
    for fragment, declaration in (
        (".film-tv-dialog__title", "margin: 0 0 0.15rem"),
        (".film-tv-dialog__facts", "margin: 0 0 0.8rem"),
        (".film-tv-dialog__fact dd", "margin: 0"),
    ):
        matching = {sel: body for sel, body in overrides.items() if fragment in sel}
        assert matching, f"no `[dir] .md-typeset ...{fragment}` override left"
        assert any(declaration in body for body in matching.values()), (
            f"the override for {fragment} no longer sets {declaration!r}"
        )


def test_narrow_dialog_stacks_the_label_and_value():
    """Under 30rem the 4.5em label column leaves the value too little room.

    Measured at a 480px viewport: 164px of value line inside a 240px column, so
    the pair stacks and the value gets the full row.
    """
    css = _css()
    _require(css, "@media (max-width: 30rem)", CSS)
    narrow = css.split("@media (max-width: 30rem)", 1)[1]
    assert "display: block" in _rule_body(narrow, ".film-tv-dialog__fact"), (
        "the narrow-dialog stacking rule is gone: below 30rem the label column "
        "would squeeze the value back into a third of the row"
    )
    assert "min-width: 0" in _rule_body(narrow, ".film-tv-dialog__fact dt"), (
        "the stacked label kept its 4.5em min-width, which no longer buys alignment"
    )


def test_credit_rows_are_block_buttons_not_a_list():
    """One person per line comes from the block buttons, not from `<ul>` markup.

    Material's prose typography restyles any list inside `.md-typeset`
    ([dir=ltr] .md-typeset ul li { margin-left: 1.25em } plus a disc marker) and
    measured the names +29px off the value column they belong to; the same
    applies to any `ul` this renderer creates, so the guard is on the renderer.
    """
    assert "display: block" in _rule_body(_css(), ".film-tv-dialog__person"), (
        "the credit names are no longer block buttons — one name per line is what "
        "keeps them aligned in the value column"
    )
    js = DIALOG_JS.read_text(encoding="utf-8")
    for markup in ('el("ul"', 'el("li"', 'el("ol"'):
        assert markup not in js, (
            f"{markup} reappeared in {DIALOG_JS.name}: list markup inside "
            "`.md-typeset` gets the theme's bullet + indent styling"
        )
