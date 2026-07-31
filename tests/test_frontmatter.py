"""Unit tests for shared/frontmatter.py — has_draft_flag and parse_frontmatter."""

import datetime

import pytest

from shared.frontmatter import has_draft_flag, parse_frontmatter

# --- has_draft_flag (fast scan) ---


def test_draft_flag_true_variants():
    assert has_draft_flag("---\ndraft: true\n---\nbody")
    assert has_draft_flag("---\ndraft: yes\n---\n")
    assert has_draft_flag("---\ndraft: 1\n---\n")
    assert has_draft_flag("---\ndraft : true\n---\n")  # spacing before colon
    assert has_draft_flag("---\ndraft: TRUE\n---\n")  # case-insensitive


def test_draft_flag_false_variants():
    assert not has_draft_flag("---\ndraft: false\n---\n")
    assert not has_draft_flag("---\ndraft: no\n---\n")
    assert not has_draft_flag("---\ndraft: 0\n---\n")
    assert not has_draft_flag("---\ntags: [draft]\n---\n")  # different field
    assert not has_draft_flag("---\ntitle: x\n---\n")  # no draft key


def test_draft_flag_no_or_broken_frontmatter():
    assert not has_draft_flag("plain text, no frontmatter")
    assert not has_draft_flag("---\ndraft: true")  # unclosed
    assert not has_draft_flag("")  # empty


# --- parse_frontmatter (full YAML parse) ---


def test_parse_frontmatter_ok():
    text = "---\ntitle: Hello\ndate: 2026-07-30\ntags: [a, b]\n---\n\nbody text"
    meta, body = parse_frontmatter(text)
    assert meta == {
        "title": "Hello",
        "date": datetime.date(2026, 7, 30),  # YAML parses ISO dates to date objects
        "tags": ["a", "b"],
    }
    assert body == "body text"


def test_parse_frontmatter_no_frontmatter():
    assert parse_frontmatter("just body") is None


def test_parse_frontmatter_unclosed():
    assert parse_frontmatter("---\ntitle: x") is None


def test_parse_frontmatter_invalid_yaml():
    assert parse_frontmatter("---\n: bad yaml [\n---\n") is None


def test_parse_frontmatter_empty_or_non_dict():
    assert parse_frontmatter("---\n---\nbody") is None  # empty
    assert parse_frontmatter("---\n- a\n- b\n---\n") is None  # list, not dict


def test_parse_frontmatter_none_input():
    with pytest.raises(AttributeError):
        parse_frontmatter(None)  # type: ignore[arg-type] — API expects str
