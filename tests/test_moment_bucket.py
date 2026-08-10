"""Moment plugin × bucket rewrite integration tests.

Covers the moment plugin's bucket-aware image handling: relative image paths
matching a configured bucket prefix resolve to absolute URLs (popup_image /
OG chain) only when the bucket feature is enabled; everything else keeps the
historical behaviour. No MkDocs build required.
"""

import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
# mkdocs_moment is imported as a top-level package (the MkDocs hook loader
# puts plugins/ on sys.path), so mirror that here
sys.path.insert(0, str(REPO_ROOT / "plugins"))

from mkdocs_moment.models import Moment  # noqa: E402
from mkdocs_moment.plugin import MomentPlugin  # noqa: E402

MAPPINGS = [{"prefix": "assets/bucket/", "base_url": "http://xxx.r2.dev/web-assets/img"}]


def _moment(html: str) -> Moment:
    return Moment(
        id="test-001",
        date=datetime(2026, 8, 10, 10, 0),
        slug="test-001",
        source_path="moments/test-001.md",
        permalink="/moments/2026-08/test-001/",
        content="",
        html=html,
    )


class TestFirstImageBucket:
    def test_bucket_relative_path_rewritten(self):
        plugin = MomentPlugin()
        plugin._bucket = {"enabled": True, "mappings": MAPPINGS}
        moment = _moment('<img src="../../assets/bucket/food.webp">')
        assert plugin._first_image(moment) == "http://xxx.r2.dev/web-assets/img/food.webp"

    def test_bucket_disabled_ignores_relative(self):
        plugin = MomentPlugin()
        plugin._bucket = {"enabled": False, "mappings": []}
        moment = _moment('<img src="../../assets/bucket/food.webp">')
        assert plugin._first_image(moment) is None

    def test_unmatched_relative_ignored(self):
        plugin = MomentPlugin()
        plugin._bucket = {"enabled": True, "mappings": MAPPINGS}
        moment = _moment('<img src="./food.webp">')
        assert plugin._first_image(moment) is None

    def test_absolute_and_remote_untouched(self):
        plugin = MomentPlugin()
        plugin._bucket = {"enabled": True, "mappings": MAPPINGS}
        assert plugin._first_image(_moment('<img src="/moments/t/food.webp">')) == (
            "/moments/t/food.webp"
        )
        assert plugin._first_image(_moment('<img src="https://cdn.example/x.webp">')) == (
            "https://cdn.example/x.webp"
        )


class TestLazyBucketDefault:
    def test_class_default_before_on_config(self):
        assert MomentPlugin()._bucket == {"enabled": False, "mappings": []}
