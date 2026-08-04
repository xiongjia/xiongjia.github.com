"""Guard for the tracked copy of Material's toc.html partial.

overrides/partials/toc.html is a copy of Material's
templates/partials/toc.html with (a) our own leading Jinja comment and
(b) a trailing include of the back-link partial. On a Material upgrade the
theme template can change silently while our override keeps rendering the
old markup — this test fails loudly instead, so the copy is re-synced (or
the test updated) when the theme version changes.
"""

import re
from pathlib import Path

import material

REPO_ROOT = Path(__file__).resolve().parent.parent
OVERRIDE = REPO_ROOT / "overrides" / "partials" / "toc.html"
THEME = Path(material.__file__).resolve().parent / "templates" / "partials" / "toc.html"


def _strip_leading_jinja_comment(text: str) -> str:
    # both files start with a {#- ... -#} header comment (theme's is
    # "This file was automatically generated"; ours describes the override)
    return re.sub(r"^{#-.*?-#}", "", text, count=1, flags=re.S)


def _strip_trailing_back_link_include(text: str) -> str:
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()  # tolerate trailing blank lines
    while lines and "back-link.html" in lines[-1]:
        lines.pop()
    return "\n".join(lines)


def test_toc_override_matches_theme():
    raw = OVERRIDE.read_text(encoding="utf-8")
    # the whole point of the override is appending the back-link include —
    # its absence would silently drop the sidebar link while the body still
    # matches the theme, so assert it explicitly
    assert '{% include "partials/back-link.html" %}' in raw, (
        "back-link include removed from overrides/partials/toc.html"
    )
    assert THEME.is_file(), (
        f"Material template not found: {THEME} — update the guard path "
        "if the theme changed its layout"
    )
    theme_body = _strip_leading_jinja_comment(THEME.read_text(encoding="utf-8")).strip()
    override_body = _strip_trailing_back_link_include(_strip_leading_jinja_comment(raw)).strip()
    assert override_body == theme_body, (
        f"Material {material.__version__}: overrides/partials/toc.html drifted "
        "from the installed theme's toc.html. Re-sync the tracked copy with the "
        "theme template (or update this test if the divergence is intentional)."
    )
