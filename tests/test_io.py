"""Unit tests for shared/io.py — safe_read and resolve_within."""

from shared.io import resolve_within, safe_read


def test_safe_read_ok(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    assert safe_read(f) == "hello"


def test_safe_read_limit(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    assert safe_read(f, limit=5) == "hello"


def test_safe_read_missing_returns_none(tmp_path):
    assert safe_read(tmp_path / "nope.txt") is None


def test_safe_read_directory_returns_none(tmp_path):
    assert safe_read(tmp_path) is None  # IsADirectoryError → None


def test_resolve_within_ok(tmp_path):
    docs = tmp_path / "docs"
    inner = docs / "sub"
    inner.mkdir(parents=True)
    assert resolve_within(str(docs), "sub/a.md") == str(inner / "a.md")


def test_resolve_within_traversal_blocked(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    assert resolve_within(str(docs), "../secret") is None
    assert resolve_within(str(docs), "../../etc/passwd") is None


def test_resolve_within_encoded_separator_is_literal(tmp_path):
    """URL-encoded separators are literal filename chars, not traversal.

    `..%2Fsecret` stays inside docs (file would be missing at read time);
    decoding happens at the URL layer, never at the filesystem layer.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    assert resolve_within(str(docs), "..%2Fsecret") == str(docs / "..%2Fsecret")


def test_resolve_within_prefix_attack_blocked(tmp_path):
    """/docs-extra must not be treated as inside /docs (trailing-sep guard)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "docs-extra").mkdir()
    assert resolve_within(str(docs), "../docs-extra/x") is None


def test_resolve_within_root_base_dir(tmp_path):
    """base_dir="/" must allow files, not reject everything ('' + sep = '/')."""
    assert resolve_within("/", "etc/hosts") == "/etc/hosts"
    assert resolve_within("/", "../etc/hosts") == "/etc/hosts"  # already at root, no escape
