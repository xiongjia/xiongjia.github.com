"""Unit tests for shared/strings.py — slugify_title and slug_from_filename."""

from shared.strings import slug_from_filename, slugify_title


def test_slugify_title_basic():
    assert slugify_title("My Post") == "my-post"
    assert slugify_title("Hello, World!") == "hello-world"
    assert slugify_title("Go   with   spaces") == "go-with-spaces"


def test_slugify_title_chinese_falls_back():
    """Chinese titles strip to empty → fallback (never a Chinese slug)."""
    assert slugify_title("补发测试", fallback="bits") == "bits"
    assert slugify_title("纯中文标题") == "post"  # default fallback
    assert slugify_title("补发 测试 42", fallback="bits") == "42"


def test_slugify_title_empty():
    assert slugify_title("") == "post"
    assert slugify_title("   ") == "post"


def test_slug_from_filename():
    assert slug_from_filename("30-1430-home-lab") == "home-lab"
    assert slug_from_filename("30-1430") == "1430"
    assert slug_from_filename("30") == "30"  # no match → unchanged
    assert slug_from_filename("not-a-date") == "not-a-date"
