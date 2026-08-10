"""Unit tests for shared/bucket.py — prefix rewrite, config parsing, env overrides.

These tests are pure logic and never touch a real bucket (R2 credentials are
developer-local; end-to-end verification steps live in internal/bucket-design.md).
"""

import pytest

from shared.bucket import (
    MKDOCS_BUCKET_BASE_URL_ENV,
    MKDOCS_BUCKET_ENABLED_ENV,
    is_enabled,
    load_mappings,
    rewrite_html,
    rewrite_url,
)

MAPPINGS = [
    {"prefix": "assets/bucket/", "base_url": "http://xxx.r2.dev/web-assets/img"},
    {"prefix": "assets/files/", "base_url": "https://files.example.com"},
]


def _normalized():
    return load_mappings({"mappings": MAPPINGS})


class TestRewriteUrl:
    def test_relative_md_form(self):
        # `../../` md-relative form (as seen on_page_content)
        url = "../../assets/bucket/food-004.webp"
        assert rewrite_url(url, _normalized()) == "http://xxx.r2.dev/web-assets/img/food-004.webp"

    def test_site_root_form(self):
        url = "/assets/bucket/food-004.webp"
        assert rewrite_url(url, _normalized()) == "http://xxx.r2.dev/web-assets/img/food-004.webp"

    def test_plain_prefix_form(self):
        url = "assets/bucket/food-004.webp"
        assert rewrite_url(url, _normalized()) == "http://xxx.r2.dev/web-assets/img/food-004.webp"

    def test_second_mapping(self):
        url = "../../assets/files/report.pdf"
        assert rewrite_url(url, _normalized()) == "https://files.example.com/report.pdf"

    def test_not_matched_left_untouched(self):
        # existing local images / site links must not change
        for url in (
            "../../moments/2026-08/food-001.webp",
            "./food-004.webp",
            "https://example.com/other/img.webp",
            "https://bucket.example.com/assets/bucket/x.webp",  # absolute: never rewritten
        ):
            assert rewrite_url(url, _normalized()) == url

    def test_query_and_anchor_preserved(self):
        url = "../../assets/bucket/img.webp?w=800#thumb"
        out = rewrite_url(url, _normalized())
        assert out == "http://xxx.r2.dev/web-assets/img/img.webp?w=800#thumb"

    def test_prefix_boundary(self):
        # `myassets/bucket/` must not match `assets/bucket/`
        url = "../../myassets/bucket/x.webp"
        assert rewrite_url(url, _normalized()) == url

    def test_empty_key_not_rewritten(self):
        assert rewrite_url("../../assets/bucket/", _normalized()) == "../../assets/bucket/"

    def test_no_mappings(self):
        assert rewrite_url("../../assets/bucket/x.webp", []) == "../../assets/bucket/x.webp"


class TestRewriteHtml:
    def test_double_quoted_src(self):
        html = '<img src="../../assets/bucket/food.webp" alt="x">'
        assert rewrite_html(html, _normalized()) == (
            '<img src="http://xxx.r2.dev/web-assets/img/food.webp" alt="x">'
        )

    def test_single_quoted_src(self):
        html = "<img src='../../assets/bucket/food.webp'>"
        assert rewrite_html(html, _normalized()) == (
            "<img src='http://xxx.r2.dev/web-assets/img/food.webp'>"
        )

    def test_href_rewritten(self):
        html = '<a href="../../assets/bucket/report.pdf">x</a>'
        assert rewrite_html(html, _normalized()) == (
            '<a href="http://xxx.r2.dev/web-assets/img/report.pdf">x</a>'
        )

    def test_unmatched_left_untouched(self):
        html = '<img src="../../moments/2026-08/food.webp"><img src="https://x/y.webp">'
        assert rewrite_html(html, _normalized()) == html

    def test_empty_html(self):
        assert rewrite_html("", _normalized()) == ""


class TestLoadMappings:
    def test_none_config(self):
        assert load_mappings(None) == []
        assert load_mappings({}) == []

    def test_prefix_normalized_with_trailing_slash(self):
        out = load_mappings({"mappings": [{"prefix": "assets/bucket", "base_url": "http://x/"}]})
        assert out == [{"prefix": "assets/bucket/", "base_url": "http://x"}]

    def test_drops_incomplete_mappings(self):
        out = load_mappings(
            {"mappings": [{"prefix": "assets/bucket/", "base_url": "http://x"}, {"prefix": ""}]}
        )
        assert out == [{"prefix": "assets/bucket/", "base_url": "http://x"}]

    def test_env_base_url_enables_empty_config_url(self, monkeypatch):
        # config has no base_url yet; env override must still produce a mapping
        monkeypatch.setenv(MKDOCS_BUCKET_BASE_URL_ENV, "http://test.example.com")
        out = load_mappings({"mappings": [{"prefix": "assets/bucket/", "base_url": ""}]})
        assert out == [{"prefix": "assets/bucket/", "base_url": "http://test.example.com"}]


class TestIsEnabled:
    def test_disabled_by_default(self):
        assert is_enabled(None) is False
        assert is_enabled({}) is False

    def test_config_enabled(self):
        assert is_enabled({"enabled": True}) is True
        assert is_enabled({"enabled": False}) is False

    @pytest.mark.parametrize("value", ["true", "1", "yes", "TRUE", "Yes"])
    def test_env_overrides_config(self, value, monkeypatch):
        monkeypatch.setenv(MKDOCS_BUCKET_ENABLED_ENV, value)
        assert is_enabled({"enabled": False}) is True

    def test_env_empty_falls_back_to_config(self, monkeypatch):
        monkeypatch.delenv(MKDOCS_BUCKET_ENABLED_ENV, raising=False)
        assert is_enabled({"enabled": True}) is True
        assert is_enabled({"enabled": False}) is False


class TestEnvBaseUrl:
    def test_env_overrides_base_url(self, monkeypatch):
        monkeypatch.setenv(MKDOCS_BUCKET_BASE_URL_ENV, "https://test.example.com")
        mappings = load_mappings(
            {"mappings": [{"prefix": "assets/bucket/", "base_url": "http://x"}]}
        )
        assert (
            rewrite_url("../../assets/bucket/a.webp", mappings) == "https://test.example.com/a.webp"
        )
        monkeypatch.delenv(MKDOCS_BUCKET_BASE_URL_ENV)
