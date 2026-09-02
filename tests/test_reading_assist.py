"""Unit tests for `scripts/reading_assist.py` (Reading Items parse / pick /
validate / organize / path safety / cleanup).

The plan fixture keeps the Chinese display keys (类型 / 状态 / 原材料 / 输出 /
出处) so the tests exercise the KEY_MAP translation to canonical English keys.
"""

import argparse
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import reading_assist as ra  # noqa: E402

PLAN_BODY = """## Reading Items

### ddia — Designing Data-Intensive Applications
- **slug**: ddia
- **类型**: book
- **出处**: Douban / https://example.com/dbia
- **状态**: not-started
- **原材料**: /nonexistent/dbia.epub
- **输出**: docs/notes/reading/ddia/

### some-article — Testing Article
- **slug**: some-article
- **类型**: article
- **状态**: not-started
- **原材料**: http://127.0.0.1:9/unreachable
- **输出**: docs/notes/reading/some-article/

## Notes
x
"""


@pytest.fixture
def plan_file(tmp_path):
    p = tmp_path / "reading-assist.md"
    p.write_text(PLAN_BODY, encoding="utf-8")
    return p


def _namespace(**kw):
    cfg = dict(slug=None, dry_run=False, timeout=1800, model=None)
    cfg.update(kw)
    return argparse.Namespace(**cfg)


# ---------------------------------------------------------------------------
# parse / key mapping
# ---------------------------------------------------------------------------


def test_items_file_default_path():
    # Regression guard: the queue-file path once drifted (constant kept the
    # old pre-move path, so list stayed empty).
    assert ra.ITEMS_FILE == ra.REPO_ROOT / "internal" / "plans" / "reading-items.md"
    assert ra.ITEMS_FILE.exists()


def test_parse_items_maps_chinese_keys(plan_file):
    with mock.patch.object(ra, "ITEMS_FILE", plan_file):
        items = ra.parse_items()
    assert [i[ra.K_SLUG] for i in items] == ["ddia", "some-article"]
    assert items[0][ra.K_TYPE] == "book"
    assert [i[ra.K_STATE] for i in items] == ["not-started", "not-started"]
    assert items[0][ra.K_SOURCE] == "/nonexistent/dbia.epub"
    assert items[0][ra.K_OUTPUT] == "docs/notes/reading/ddia/"
    assert items[0][ra.K_REF] == "Douban / https://example.com/dbia"


def test_key_map_covers_all_display_keys():
    assert ra.KEY_MAP["类型"] == ra.K_TYPE
    assert ra.KEY_MAP["状态"] == ra.K_STATE
    assert ra.KEY_MAP["原材料"] == ra.K_SOURCE
    assert ra.KEY_MAP["输出"] == ra.K_OUTPUT
    assert ra.KEY_MAP["出处"] == ra.K_REF
    assert ra.KEY_MAP["slug"] == ra.K_SLUG


# ---------------------------------------------------------------------------
# pick
# ---------------------------------------------------------------------------


def test_pick_first_not_started(plan_file):
    with mock.patch.object(ra, "ITEMS_FILE", plan_file):
        items = ra.parse_items()
    assert ra.pick(None, items)[ra.K_SLUG] == "ddia"
    assert ra.pick("some-article", items)[ra.K_SLUG] == "some-article"
    assert ra.pick("absent", items) is None


def test_pick_skips_organized(plan_file):
    with mock.patch.object(ra, "ITEMS_FILE", plan_file):
        items = ra.parse_items()
    items[0][ra.K_STATE] = "organized"
    assert ra.pick(None, items)[ra.K_SLUG] == "some-article"
    assert ra.pick("ddia", items)[ra.K_SLUG] == "ddia"  # explicit slug re-runs (even organized)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_missing_file(plan_file):
    with mock.patch.object(ra, "ITEMS_FILE", plan_file):
        items = ra.parse_items()
    ok, why = ra.validate(ra.pick(None, items))
    assert not ok
    assert "file missing" in why


def test_validate_unreachable_url(plan_file):
    with mock.patch.object(ra, "ITEMS_FILE", plan_file):
        items = ra.parse_items()
    ok, why = ra.validate(ra.pick("some-article", items))
    assert not ok
    assert "URL unreachable" in why


def test_validate_type_tolerates_parenthetical_annotation(tmp_path):
    # a parenthetical annotation after the value also lands in the URL branch
    item = {
        ra.K_SLUG: "hdv",
        ra.K_TYPE: "article (online book: source=URL)",
        ra.K_SOURCE: "http://example.com/book",
    }

    def fake_fetch(url, dest, **kw):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("<html><body>content</body></html>", encoding="utf-8")
        return True

    with (
        mock.patch.object(ra, "_url_reachable", return_value=True),
        mock.patch.object(ra, "_fetch_article", side_effect=fake_fetch),
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
    ):
        ok, why = ra.validate(item)
    assert ok, why


def test_fetch_article_retries_then_succeeds(tmp_path):
    dest = tmp_path / "s" / "source-01.html"
    calls = {"n": 0}

    class PFail:
        returncode = 1
        stdout = b""
        stderr = b""

    class POk:
        returncode = 0

    def fake_run(cmd, stdout=None, stderr=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            return PFail()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"<html>x</html>")
        return POk()

    with (
        mock.patch.object(ra.subprocess, "run", side_effect=fake_run),
        mock.patch.object(ra.time, "sleep"),
    ):
        assert ra._fetch_article("http://x", dest) is True
    assert calls["n"] == 3  # two failures, then the third attempt succeeds


def test_fetch_article_all_attempts_fail(tmp_path):
    dest = tmp_path / "s" / "source-01.html"

    class PFail:
        returncode = 1

    with (
        mock.patch.object(ra.subprocess, "run", return_value=PFail()),
        mock.patch.object(ra.time, "sleep"),
    ):
        assert ra._fetch_article("http://x", dest) is False


def test_url_reachable_retries_once(tmp_path):
    calls = {"n": 0}

    def fake_run(cmd, **kw):
        calls["n"] += 1
        out = "000" if calls["n"] == 1 else "200"
        return type("P", (), {"stdout": out})()

    with (
        mock.patch.object(ra.subprocess, "run", side_effect=fake_run),
        mock.patch.object(ra.time, "sleep"),
    ):
        assert ra._url_reachable("http://x") is True
    assert calls["n"] == 2  # first 000, then one retry


def test_validate_rejects_invalid_slug():
    item = {ra.K_SLUG: "../../evil", ra.K_TYPE: "book", ra.K_SOURCE: "/x.epub"}
    ok, why = ra.validate(item)
    assert not ok
    assert "invalid slug" in why


def test_validate_empty_source():
    item = {ra.K_SLUG: "ddia", ra.K_TYPE: "book", ra.K_SOURCE: ""}
    ok, why = ra.validate(item)
    assert not ok
    assert "source is empty" in why


def test_resolve_local_path_candidates(tmp_path, monkeypatch):
    (tmp_path / "external" / "book").mkdir(parents=True)
    f = tmp_path / "external" / "book" / "x.pdf"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setattr(ra, "REPO_ROOT", tmp_path)

    assert ra._resolve_local_path("x.pdf") == f
    assert ra._resolve_local_path("book/x.pdf") == f
    assert ra._resolve_local_path("external/book/x.pdf") == f
    assert ra._resolve_local_path(str(f)) == f  # absolute passthrough
    # no match → fall back to the first candidate (canonical error location)
    assert ra._resolve_local_path("nope.pdf") == tmp_path / "nope.pdf"


def test_resolve_local_path_project_root_token(tmp_path, monkeypatch):
    monkeypatch.setattr(ra, "REPO_ROOT", tmp_path)
    f = tmp_path / "external" / "book" / "1.pdf"
    f.parent.mkdir(parents=True)
    f.write_text("x", encoding="utf-8")

    # the explicit {projectRoot}/external/book/1.pdf form
    assert ra._resolve_local_path("{projectRoot}/external/book/1.pdf") == f
    # missing file → first candidate (canonical error location)
    assert (
        ra._resolve_local_path("{projectRoot}/external/book/nope.pdf")
        == tmp_path / "external" / "book" / "nope.pdf"
    )


def test_html_to_text_strips_tags_and_script(tmp_path):
    html = tmp_path / "s.html"
    html.write_text(
        "<html><head><script>var x=1;</script><style>.a{}</style></head>"
        "<body><h1>Title</h1><p>Hello <b>world</b>.</p></body></html>",
        encoding="utf-8",
    )
    txt = tmp_path / "s.txt"
    size = ra._html_to_text(html, txt)
    text = txt.read_text(encoding="utf-8")
    assert "Title" in text and "Hello world" in text
    assert "var x" not in text and ".a{}" not in text
    assert size == len(text)


def test_html_to_text_js_only_returns_zero(tmp_path):
    html = tmp_path / "s.html"
    html.write_text(
        "<html><body><div id=app></div><script>render()</script></body></html>",
        encoding="utf-8",
    )
    txt = tmp_path / "s.txt"
    assert ra._html_to_text(html, txt) == 0


def test_extract_epub_chapters(tmp_path):
    import zipfile
    from xml.etree import ElementTree as ET

    epub = tmp_path / "book.epub"
    ns_c = "urn:oasis:names:tc:opendocument:xmlns:container"
    container = ET.Element("container", {"version": "1.0", "xmlns": ns_c})
    rootfiles = ET.SubElement(container, "rootfiles")
    ET.SubElement(
        rootfiles,
        "rootfile",
        {"full-path": "OEBPS/content.opf", "media-type": "application/oebps-package+xml"},
    )
    opf_ns = "http://www.idpf.org/2007/opf"
    opf = ET.Element("package", {"xmlns": opf_ns, "version": "3.0"})
    man = ET.SubElement(opf, "manifest")
    for mid, href in (("c1", "ch1.xhtml"), ("c2", "ch2.xhtml")):
        ET.SubElement(man, "item", {"id": mid, "href": href, "media-type": "application/xhtml+xml"})
    sp = ET.SubElement(opf, "spine")
    ET.SubElement(sp, "itemref", {"idref": "c1"})
    ET.SubElement(sp, "itemref", {"idref": "c2"})
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr("META-INF/container.xml", ET.tostring(container))
        z.writestr("OEBPS/content.opf", ET.tostring(opf))
        z.writestr("OEBPS/ch1.xhtml", "<html><body><h1>Ch1</h1><p>alpha beta</p></body></html>")
        z.writestr("OEBPS/ch2.xhtml", "<html><body><h1>Ch2</h1><p>gamma delta</p></body></html>")

    dest = tmp_path / "out"
    ok, why, n = ra._extract_epub_chapters(epub, dest)
    assert ok, why
    assert n == 2
    assert "alpha beta" in (dest / "source-01.txt").read_text(encoding="utf-8")
    assert "gamma delta" in (dest / "source-02.txt").read_text(encoding="utf-8")


def test_extract_epub_chapters_flat_root_opf(tmp_path):
    # OPF at the zip root (no directory) — dirname must be empty, not the
    # OPF filename; a regression: chapter paths became "content.opf/ch1"
    # and every spine file was skipped ("no extractable text").
    import zipfile
    from xml.etree import ElementTree as ET

    epub = tmp_path / "book.epub"
    ns_c = "urn:oasis:names:tc:opendocument:xmlns:container"
    container = ET.Element("container", {"version": "1.0", "xmlns": ns_c})
    rootfiles = ET.SubElement(container, "rootfiles")
    ET.SubElement(
        rootfiles,
        "rootfile",
        {"full-path": "content.opf", "media-type": "application/oebps-package+xml"},
    )
    opf_ns = "http://www.idpf.org/2007/opf"
    opf = ET.Element("package", {"xmlns": opf_ns, "version": "2.0"})
    man = ET.SubElement(opf, "manifest")
    for mid, href in (("c1", "ch1.xhtml"), ("c2", "ch2.xhtml")):
        ET.SubElement(man, "item", {"id": mid, "href": href, "media-type": "application/xhtml+xml"})
    sp = ET.SubElement(opf, "spine")
    ET.SubElement(sp, "itemref", {"idref": "c1"})
    ET.SubElement(sp, "itemref", {"idref": "c2"})
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr("META-INF/container.xml", ET.tostring(container))
        z.writestr("content.opf", ET.tostring(opf))
        z.writestr("ch1.xhtml", "<html><body><h1>Ch1</h1><p>alpha beta</p></body></html>")
        z.writestr("ch2.xhtml", "<html><body><h1>Ch2</h1><p>gamma delta</p></body></html>")

    dest = tmp_path / "out"
    ok, why, n = ra._extract_epub_chapters(epub, dest)
    assert ok, why
    assert n == 2
    assert "alpha beta" in (dest / "source-01.txt").read_text(encoding="utf-8")
    assert "gamma delta" in (dest / "source-02.txt").read_text(encoding="utf-8")


def test_extract_pdf_chapters_mock(tmp_path):
    # pymupdf not guaranteed in the test env — fake the module and its objects
    class FakePage:
        def __init__(self, text):
            self._t = text

        def get_text(self):
            return self._t

    class FakeDoc:
        page_count = 45

        def __init__(self):
            self.pages = [FakePage(f"page {i}") for i in range(45)]

        def get_toc(self, simple=False):
            return [[1, "ch1", 1], [1, "ch2", 20], [1, "ch3", 40]]

        def load_page(self, i):
            return self.pages[i]

        def close(self):
            pass

    fake = type("Mod", (), {"open": staticmethod(lambda path: FakeDoc())})()
    with mock.patch.dict("sys.modules", {"pymupdf": fake}):
        dest = tmp_path / "out"
        ok, why, n = ra._extract_pdf_chapters(tmp_path / "book.pdf", dest)
    assert ok, why
    assert n == 3
    texts = sorted(p.read_text(encoding="utf-8") for p in dest.glob("source-*.txt"))
    # ch1 = toc page 1-19 → page indices 0..18 (no "page 19")
    assert any("page 0" in t and "page 18" in t and "page 19" not in t for t in texts)
    # ch2 = toc page 20-39 → indices 19..38
    assert any("page 19" in t and "page 38" in t for t in texts)
    # ch3 = toc page 40..end → indices 39..44
    assert any("page 39" in t and "page 44" in t for t in texts)


def test_extract_pdf_chapters_error_returns_false(tmp_path):
    # a malformed bookmark (bad page number) must not crash the pipeline
    class BadDoc:
        page_count = 10

        def get_toc(self, simple=False):
            return [[1, "ch1", 99]]  # out-of-range page → load_page raises

        def load_page(self, i):
            raise ValueError(f"page {i} out of range")

        def close(self):
            pass

    fake = type("Mod", (), {"open": staticmethod(lambda path: BadDoc())})()
    with mock.patch.dict("sys.modules", {"pymupdf": fake}):
        ok, why, n = ra._extract_pdf_chapters(tmp_path / "book.pdf", tmp_path / "out")
    assert not ok
    assert "pdf extract error" in why
    assert n == 0


def test_extract_epub_chapters_normpath_href(tmp_path):
    # hrefs relative to the OPF dir with `../` must still resolve
    import zipfile
    from xml.etree import ElementTree as ET

    epub = tmp_path / "book.epub"
    ns_c = "urn:oasis:names:tc:opendocument:xmlns:container"
    container = ET.Element("container", {"version": "1.0", "xmlns": ns_c})
    rootfiles = ET.SubElement(container, "rootfiles")
    ET.SubElement(
        rootfiles,
        "rootfile",
        {"full-path": "OPS/content.opf", "media-type": "application/oebps-package+xml"},
    )
    opf_ns = "http://www.idpf.org/2007/opf"
    opf = ET.Element("package", {"xmlns": opf_ns, "version": "3.0"})
    man = ET.SubElement(opf, "manifest")
    ET.SubElement(
        man,
        "item",
        {"id": "c1", "href": "../text/ch1.xhtml", "media-type": "application/xhtml+xml"},
    )
    sp = ET.SubElement(opf, "spine")
    ET.SubElement(sp, "itemref", {"idref": "c1"})
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr("META-INF/container.xml", ET.tostring(container))
        z.writestr("OPS/content.opf", ET.tostring(opf))
        z.writestr("text/ch1.xhtml", "<html><body><h1>Ch1</h1><p>alpha</p></body></html>")

    dest = tmp_path / "out"
    ok, why, n = ra._extract_epub_chapters(epub, dest)
    assert ok, why
    assert n == 1
    assert "alpha" in (dest / "source-01.txt").read_text(encoding="utf-8")


def test_validate_article_empty_text_aborts(tmp_path):
    item = {ra.K_SLUG: "app", ra.K_TYPE: "article", ra.K_SOURCE: "http://example.com/app"}
    html = tmp_path / "app" / "source-01.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text(
        "<html><body><div id=app></div><script>render()</script></body></html>",
        encoding="utf-8",
    )
    with (
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_url_reachable", return_value=True),
        mock.patch.object(ra, "_fetch_article", return_value=True),
    ):
        ok, why = ra.validate(item)
    assert not ok
    assert "provide a local pdf" in why


def test_validate_article_oversize_aborts(tmp_path):
    item = {ra.K_SLUG: "big", ra.K_TYPE: "article", ra.K_SOURCE: "http://example.com/big"}
    html = tmp_path / "big" / "source-01.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<html><body>" + "<p>text</p>" * 200_000 + "</body></html>", encoding="utf-8")
    with (
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_url_reachable", return_value=True),
        mock.patch.object(ra, "_fetch_article", return_value=True),
    ):
        ok, why = ra.validate(item)
    assert not ok
    assert "provide a local pdf" in why


def test_validate_article_series(tmp_path):
    item = {
        ra.K_SLUG: "series",
        ra.K_TYPE: "article",
        ra.K_SOURCE: "http://example.com/1 http://example.com/2",
    }

    def fake_fetch(url, dest, **kw):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("<html><body>content</body></html>", encoding="utf-8")
        return True

    with (
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_url_reachable", return_value=True),
        mock.patch.object(ra, "_fetch_article", side_effect=fake_fetch),
    ):
        ok, why = ra.validate(item)
    assert ok, why


def test_validate_article_series_unreachable():
    item = {
        ra.K_SLUG: "series",
        ra.K_TYPE: "article",
        ra.K_SOURCE: "http://ok.example http://bad.example",
    }
    with mock.patch.object(ra, "_url_reachable", side_effect=lambda u: u.startswith("http://ok")):
        ok, why = ra.validate(item)
    assert not ok
    assert "URL unreachable" in why


def test_validate_mixed_url_and_file_aborts(tmp_path):
    # article/paper may be all-URL or all-local; a mix is a config error that
    # must abort with a clear reason instead of a confusing "file missing".
    item = {
        ra.K_SLUG: "mix",
        ra.K_TYPE: "paper",
        ra.K_SOURCE: "https://ok.example/1 local.pdf",
    }
    with mock.patch.object(ra, "CACHE_DIR", tmp_path):
        ok, why = ra.validate(item)
    assert not ok
    assert "mixed sources" in why


def test_prepare_cache_reextract_purges_stale_sources(tmp_path):
    # when the source set changes (or the input mode switches), leftover
    # source files from the earlier set must not survive to be globbed later
    cache = tmp_path / "c" / "vols"
    cache.mkdir(parents=True)
    (cache / "source-01.txt").write_text("stale", encoding="utf-8")
    (cache / "source-02.txt").write_text("stale", encoding="utf-8")
    ra._write_manifest(cache, ["old.pdf"])  # mismatched manifest → forces re-extract

    item = {ra.K_SLUG: "vols", ra.K_TYPE: "book", ra.K_SOURCE: "book/v1.pdf"}

    def fake_extract(path, dest_dir, start=1):
        (dest_dir / f"source-{start:02d}.txt").write_text("fresh", encoding="utf-8")
        return (True, "", 1)

    with (
        mock.patch.object(ra, "_file_parseable", return_value=(True, "ok")),
        mock.patch.object(ra, "_extract_to_cache", side_effect=fake_extract),
        mock.patch.object(ra, "CACHE_DIR", tmp_path / "c"),
    ):
        ok, why = ra.validate(item)
    assert ok, why
    files = sorted(p.name for p in cache.glob("source-*.txt"))
    assert files == ["source-01.txt"]  # stale source-02 dropped
    assert (cache / "source-01.txt").read_text(encoding="utf-8") == "fresh"


def test_validate_multi_local_files(tmp_path):
    item = {ra.K_SLUG: "vols", ra.K_TYPE: "book", ra.K_SOURCE: "book/v1.pdf book/v2.pdf"}
    with (
        mock.patch.object(ra, "_file_parseable", return_value=(True, "ok")),
        mock.patch.object(ra, "_extract_to_cache", return_value=(True, "", 3)),
        mock.patch.object(ra, "CACHE_DIR", tmp_path / "a"),
    ):
        ok, why = ra.validate(item)
    assert ok, why
    # a fresh cache dir (no manifest) exercises the extraction path again,
    # where the first volume is unparseable → abort
    with (
        mock.patch.object(
            ra, "_file_parseable", side_effect=[(False, "file missing"), (True, "ok")]
        ),
        mock.patch.object(ra, "CACHE_DIR", tmp_path / "b"),
    ):
        ok2, why2 = ra.validate(item)
    assert not ok2
    assert "file missing" in why2


def test_build_prompt_series_source(tmp_path):
    item = {
        ra.K_SLUG: "series",
        ra.K_TYPE: "article",
        ra.K_SOURCE: "http://example.com/1 http://example.com/2",
    }
    with mock.patch.object(ra, "CACHE_DIR", tmp_path):
        p = ra.build_prompt(item)
    assert "source-01.txt" in p and "source-02.txt" in p
    assert "article series" in p


def test_validate_paper_with_local_epub(tmp_path):
    # paper/article now also accept a downloaded local pdf/epub (mode decided
    # by the source shape, not the type alone): all-URL → web, else local-file.
    import zipfile
    from xml.etree import ElementTree as ET

    epub = tmp_path / "paper.epub"
    ns_c = "urn:oasis:names:tc:opendocument:xmlns:container"
    container = ET.Element("container", {"version": "1.0", "xmlns": ns_c})
    rootfiles = ET.SubElement(container, "rootfiles")
    ET.SubElement(
        rootfiles,
        "rootfile",
        {"full-path": "OEBPS/content.opf", "media-type": "application/oebps-package+xml"},
    )
    opf_ns = "http://www.idpf.org/2007/opf"
    opf = ET.Element("package", {"xmlns": opf_ns, "version": "3.0"})
    man = ET.SubElement(opf, "manifest")
    ET.SubElement(
        man,
        "item",
        {"id": "c1", "href": "ch1.xhtml", "media-type": "application/xhtml+xml"},
    )
    sp = ET.SubElement(opf, "spine")
    ET.SubElement(sp, "itemref", {"idref": "c1"})
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr("META-INF/container.xml", ET.tostring(container))
        z.writestr("OEBPS/content.opf", ET.tostring(opf))
        z.writestr(
            "OEBPS/ch1.xhtml",
            "<html><body><h1>Abstract</h1><p>paper body text</p></body></html>",
        )

    item = {ra.K_SLUG: "paper", ra.K_TYPE: "paper", ra.K_SOURCE: str(epub)}
    cache = tmp_path / "cache"
    with mock.patch.object(ra, "CACHE_DIR", cache):
        ok, why = ra.validate(item)
    assert ok, why
    txt = cache / "paper" / "source-01.txt"
    assert txt.exists()
    assert "paper body text" in txt.read_text(encoding="utf-8")


def test_validate_paper_with_local_pdf_mock(tmp_path):
    # paper + downloaded pdf goes through the local-file path with the real
    # pymupdf code — faked module (not guaranteed in the test env)
    class FakePage:
        def __init__(self, i):
            self._t = f"page {i}"

        def get_text(self):
            return self._t

    class FakeDoc:
        page_count = 15

        def __init__(self):
            self.pages = [FakePage(i) for i in range(15)]

        def get_toc(self, simple=False):
            return []  # no bookmarks → fixed page-group fallback

        def load_page(self, i):
            return self.pages[i]

        def close(self):
            pass

    fake = type("Mod", (), {"open": staticmethod(lambda path: FakeDoc())})()
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    item = {ra.K_SLUG: "paper", ra.K_TYPE: "paper", ra.K_SOURCE: str(pdf)}
    cache = tmp_path / "cache"
    with (
        mock.patch.dict("sys.modules", {"pymupdf": fake}),
        mock.patch.object(ra, "CACHE_DIR", cache),
    ):
        ok, why = ra.validate(item)
    assert ok, why
    txt = cache / "paper" / "source-01.txt"
    assert txt.exists()
    assert "page 14" in txt.read_text(encoding="utf-8")


def test_build_prompt_paper_local_file(tmp_path):
    # paper with a local file → local-file source description (no "article
    # series" / pre-fetched wording)
    item = {ra.K_SLUG: "paper", ra.K_TYPE: "paper", ra.K_SOURCE: "external/paper.pdf"}
    cache = tmp_path / "paper"
    cache.mkdir(parents=True)
    (cache / "source-01.txt").write_text("x", encoding="utf-8")
    with mock.patch.object(ra, "CACHE_DIR", tmp_path):
        p = ra.build_prompt(item)
    assert "pre-extracted chapter text" in p
    assert "article series" not in p
    assert "source-01.txt" in p


def test_build_prompt_paper_url_still_web(tmp_path):
    # paper with all-URL sources keeps the web (pre-fetched) description
    item = {ra.K_SLUG: "paper", ra.K_TYPE: "paper", ra.K_SOURCE: "http://example.com/p"}
    with mock.patch.object(ra, "CACHE_DIR", tmp_path):
        p = ra.build_prompt(item)
    assert "pre-fetched text" in p
    assert "source-01.txt" in p


def test_sources_are_urls():
    assert ra._sources_are_urls("https://arxiv.org/html/2606.05608v1") is True
    assert ra._sources_are_urls("http://a.example http://b.example") is True
    assert ra._sources_are_urls("external/paper.pdf") is False
    assert ra._sources_are_urls("https://a.example /tmp/local.pdf") is False
    assert ra._sources_are_urls("") is False


def test_validate_resolves_external_book():
    item = {ra.K_SLUG: "ddia", ra.K_TYPE: "book", ra.K_SOURCE: "external/book/ddia.epub"}
    ok, why = ra.validate(item)
    assert not ok
    assert "file missing" in why  # resolution works; the file just doesn't exist


# ---------------------------------------------------------------------------
# item_index (output field honored, fallback to slug)
# ---------------------------------------------------------------------------


def test_item_index_honors_output():
    item = {ra.K_SLUG: "ddia", ra.K_OUTPUT: "docs/notes/reading/ddia/"}
    with mock.patch.object(ra, "REPO_ROOT", Path("/tmp/fake-repo")):
        idx = ra.item_index(item)
    assert str(idx) == "/tmp/fake-repo/docs/notes/reading/ddia/index.md"


def test_item_index_falls_back_to_slug():
    item = {ra.K_SLUG: "ddia", ra.K_OUTPUT: ""}
    with mock.patch.object(ra, "REPO_ROOT", Path("/tmp/fake-repo")):
        idx = ra.item_index(item)
    assert str(idx) == "/tmp/fake-repo/docs/notes/reading/ddia/index.md"


# ---------------------------------------------------------------------------
# mark_organized (scoped to ## Reading Items section)
# ---------------------------------------------------------------------------


def test_mark_organized_only_target(plan_file):
    with mock.patch.object(ra, "ITEMS_FILE", plan_file):
        assert ra.mark_organized("ddia") is True
        text = plan_file.read_text(encoding="utf-8")
    assert "- **状态**: organized" in text
    assert text.count("organized") == 1


def test_mark_organized_scoped_to_reading_section(tmp_path):
    p = tmp_path / "reading-assist.md"
    p.write_text(
        "## Design\n\n```markdown\n### ddia — example only\n- **状态**: not-started\n```\n\n"
        "## Reading Items\n\n### ddia — The Real Item\n- **slug**: ddia\n"
        "- **状态**: not-started\n\n## Notes\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra.mark_organized("ddia") is True
        text = p.read_text(encoding="utf-8")
    assert "### ddia — The Real Item\n- **slug**: ddia\n- **状态**: organized" in text
    assert text.count("organized") == 1  # fenced example is not rewritten


def test_mark_organized_heading_not_slug_prefix(tmp_path):
    # regression: the ### heading is a free-form title (not the slug), the
    # block is located by its `- **slug**` field
    p = tmp_path / "reading-assist.md"
    p.write_text(
        "## Reading Items\n\n### Hands-On Data Visualization\n"
        "- **slug**: hands-on-data-visualization\n- **类型**: book\n"
        "- **状态**: not-started\n\n## Notes\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra.mark_organized("hands-on-data-visualization") is True
        text = p.read_text(encoding="utf-8")
    assert "- **状态**: organized" in text
    assert text.count("organized") == 1


# ---------------------------------------------------------------------------
# _cleanup_cache (slug guard + item-scoped)
# ---------------------------------------------------------------------------


def test_cleanup_cache_guards_invalid_slug(tmp_path):
    sentinel = tmp_path.parent / "SENTINEL-CLEAN"
    sentinel.write_text("keep", encoding="utf-8")
    try:
        with mock.patch.object(ra, "CACHE_DIR", tmp_path):
            ra._cleanup_cache("../../SENTINEL-CLEAN")  # invalid slug → no-op
        assert sentinel.exists()
    finally:
        sentinel.unlink(missing_ok=True)


def test_cleanup_cache_removes_item_dir(tmp_path):
    slug = "ddia"
    (tmp_path / slug).mkdir(parents=True)
    (tmp_path / slug / "source.html").write_text("x", encoding="utf-8")
    marker = tmp_path / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    with mock.patch.object(ra, "CACHE_DIR", tmp_path):
        ra._cleanup_cache(slug)
    assert not (tmp_path / slug).exists()
    assert marker.exists()  # only the item dir is removed, siblings kept


# ---------------------------------------------------------------------------
# _cmd_run
# ---------------------------------------------------------------------------


def test_run_validate_failure_keeps_tmp(plan_file, tmp_path):
    with (
        mock.patch.object(ra, "ITEMS_FILE", plan_file),
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_prepare_cache", return_value=(False, "file missing")),
    ):
        rc = ra._cmd_run(_namespace())
    assert rc == 0
    # temp dirs are deliberately kept (user may inspect/re-extract); the
    # validate failure here never created one, and none is removed
    assert not (tmp_path / "ddia").exists() or (tmp_path / "ddia").is_dir()


def test_run_no_index_failure_no_pages(plan_file, tmp_path):
    with (
        mock.patch.object(ra, "ITEMS_FILE", plan_file),
        mock.patch.object(ra, "REPO_ROOT", tmp_path),
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_prepare_cache", return_value=(True, "")),
        mock.patch.object(ra, "run_pi", return_value=""),
    ):
        rc = ra._cmd_run(_namespace())
    assert rc == 1
    # no output pages were produced → the entry stays not-started (this is
    # about the output dir, not the kept temp dir)
    assert not (tmp_path / "docs/notes/reading/ddia").exists()


def test_run_not_marked_records_fail(plan_file, tmp_path):
    (tmp_path / "docs/notes/reading/ddia").mkdir(parents=True)
    (tmp_path / "docs/notes/reading/ddia/index.md").write_text("# ddia\n", encoding="utf-8")
    with (
        mock.patch.object(ra, "ITEMS_FILE", plan_file),
        mock.patch.object(ra, "REPO_ROOT", tmp_path),
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_prepare_cache", return_value=(True, "")),
        mock.patch.object(ra, "run_pi", return_value=""),
        mock.patch.object(ra, "run_mdformat", return_value=0),
        mock.patch.object(ra, "mark_organized", return_value=False),
    ):
        rc = ra._cmd_run(_namespace())
    assert rc == 1  # not marked → failure exit, not a fake success
    assert (tmp_path / "docs/notes/reading/ddia").exists()  # pages kept
    assert "- **状态**: organized" not in plan_file.read_text(encoding="utf-8")


def test_run_mdformat_failure_unmarks(plan_file, tmp_path):
    (tmp_path / "docs/notes/reading/ddia").mkdir(parents=True)
    (tmp_path / "docs/notes/reading/ddia/index.md").write_text("# ddia\n", encoding="utf-8")
    with (
        mock.patch.object(ra, "ITEMS_FILE", plan_file),
        mock.patch.object(ra, "REPO_ROOT", tmp_path),
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_prepare_cache", return_value=(True, "")),
        mock.patch.object(ra, "run_pi", return_value=""),
        mock.patch.object(ra, "run_mdformat", return_value=2),
    ):
        rc = ra._cmd_run(_namespace())
    assert rc == 1
    text = plan_file.read_text(encoding="utf-8")
    assert "- **状态**: organized" not in text
    assert (
        tmp_path / "docs/notes/reading/ddia"
    ).exists()  # mdformat failure keeps pages for inspection


def test_run_success_marks_and_keeps_tmp(plan_file, tmp_path):
    out = tmp_path / "docs/notes/reading/ddia"
    out.mkdir(parents=True)
    (out / "index.md").write_text("# ddia\n", encoding="utf-8")
    (tmp_path / "ddia").mkdir(parents=True)
    (tmp_path / "ddia" / "source-01.txt").write_text("x", encoding="utf-8")
    with (
        mock.patch.object(ra, "ITEMS_FILE", plan_file),
        mock.patch.object(ra, "REPO_ROOT", tmp_path),
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_prepare_cache", return_value=(True, "")),
        mock.patch.object(ra, "run_pi", return_value=""),
        mock.patch.object(ra, "run_mdformat", return_value=0),
    ):
        rc = ra._cmd_run(_namespace())
    assert rc == 0
    text = plan_file.read_text(encoding="utf-8")
    assert "- **状态**: organized" in text
    assert (tmp_path / "ddia" / "source-01.txt").exists()  # temp dir KEPT
    assert out.exists()  # produced pages kept


def test_cmd_cache_prepares_only(plan_file, tmp_path):
    # cache step: sources prepared, no AI, no page writes, no state change
    def fake_fetch(url, dest, **kw):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("<html><body>content</body></html>", encoding="utf-8")
        return True

    with (
        mock.patch.object(ra, "ITEMS_FILE", plan_file),
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_url_reachable", return_value=True),
        mock.patch.object(ra, "_fetch_article", side_effect=fake_fetch),
    ):
        rc = ra._cmd_cache(_namespace(slug="some-article"))
    assert rc == 0
    assert (tmp_path / "some-article" / "source-01.txt").exists()
    assert "- **状态**: organized" not in plan_file.read_text(encoding="utf-8")
    assert not (tmp_path / "docs/notes/reading").exists()  # no pages


def test_prepare_cache_reuses_existing(tmp_path):
    # read/run on an already-cached item (manifest matches) must not re-fetch
    cache = tmp_path / "some-article"
    cache.mkdir(parents=True)
    (cache / "source-01.txt").write_text("cached", encoding="utf-8")
    (cache / "manifest.txt").write_text("http://example.com/x\n", encoding="utf-8")
    item = {ra.K_SLUG: "some-article", ra.K_TYPE: "article", ra.K_SOURCE: "http://example.com/x"}
    with (
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_url_reachable", side_effect=AssertionError("must not refetch")),
        mock.patch.object(ra, "_fetch_article", side_effect=AssertionError("must not refetch")),
    ):
        ok, why = ra._prepare_cache(item)
    assert ok, why


def test_cache_matches_manifest(tmp_path):
    d = tmp_path / "c"
    d.mkdir(parents=True)
    assert ra._cache_matches(d, ["http://a"]) is False  # no manifest
    (d / "manifest.txt").write_text("http://a\nhttp://b\n", encoding="utf-8")
    assert ra._cache_matches(d, ["http://a", "http://b"]) is False  # no source files yet
    (d / "source-01.txt").write_text("x", encoding="utf-8")
    (d / "source-02.txt").write_text("y", encoding="utf-8")
    assert ra._cache_matches(d, ["http://a", "http://b"]) is True
    assert ra._cache_matches(d, ["http://a"]) is False  # count mismatch
    assert ra._cache_matches(d, ["http://b", "http://a"]) is False  # order mismatch
    (d / "source-02.txt").unlink()
    assert ra._cache_matches(d, ["http://a", "http://b"]) is False  # file missing


def test_cmd_read_needs_cache(plan_file, tmp_path):
    # read without a prepared cache for article → abort (needs cache step)
    with (
        mock.patch.object(ra, "ITEMS_FILE", plan_file),
        mock.patch.object(ra, "CACHE_DIR", tmp_path),
        mock.patch.object(ra, "_url_reachable", return_value=False),
    ):
        rc = ra._cmd_read(_namespace(slug="some-article"))
    assert rc == 0
    assert "- **状态**: organized" not in plan_file.read_text(encoding="utf-8")


def test_run_dry_run_does_not_touch_tmp(plan_file, tmp_path):
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    with (
        mock.patch.object(ra, "ITEMS_FILE", plan_file),
        mock.patch.object(ra, "CACHE_DIR", tmp),
    ):
        rc = ra._cmd_run(_namespace(dry_run=True))
    assert rc == 0
    assert list(tmp.iterdir()) == []


def test_empty_items(tmp_path):
    p = tmp_path / "reading-assist.md"
    p.write_text("## Reading Items\n\n当前无活动条目。\n\n## Notes\n", encoding="utf-8")
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra.parse_items() == []
        assert ra.pick(None, []) is None


def test_append_record_sections(tmp_path):
    p = tmp_path / "reading-items.md"
    p.write_text(
        "## Reading Items\n\n（暂无条目）\n\n## 记录（Log）\n\n"
        "### 完成（Organized）\n\n（暂无）\n\n"
        "### 失败 / 放弃（Failed / Aborted）\n\n（暂无）\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("ddia", "done") is True
        assert ra._append_record("ddia", "fail", "pi error") is True
        assert ra._append_record("../../evil", "done") is False  # invalid slug skipped
    text = p.read_text(encoding="utf-8")
    assert "### 完成（Organized" in text
    done_lines = [ln for ln in text.splitlines() if ln.startswith("- 20") and "ddia" in ln]
    assert len(done_lines) == 2  # one done + one fail, each in its own section
    assert any("pi error" in ln for ln in done_lines)
    # done/fail records land in their own sections
    done_section = text.split("### 完成（Organized）")[1].split("### 失败")[0]
    fail_section = text.split("### 失败 / 放弃（Failed / Aborted）")[1]
    assert done_section.count("→ ddia") == 1
    assert fail_section.count("→ ddia") == 1


def test_append_record_refreshes_instead_of_growing(tmp_path):
    p = tmp_path / "reading-items.md"
    p.write_text(
        "## Reading Items\n\n（暂无条目）\n\n## 记录（Log）\n\n"
        "### 完成（Organized）\n\n（暂无）\n\n"
        "### 失败 / 放弃（Failed / Aborted）\n\n（暂无）\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("ddia", "done") is True
        assert ra._append_record("ddia", "done") is True  # rerun → refresh, not append
        assert ra._append_record("ddia", "fail", "file missing") is True
        assert ra._append_record("ddia", "fail", "pdf broken") is True  # reason refreshed
        assert ra._append_record("other", "done") is True
    text = p.read_text(encoding="utf-8")
    # each (slug, section) keeps only the latest line; other is the 2nd done
    assert text.count("→ ddia") == 2
    assert text.count("→ other") == 1
    assert "pdf broken" in text and "file missing" not in text
    assert text.index("pdf broken") > text.index("→ other")  # fail section follows done


def test_append_record_missing_section(tmp_path):
    p = tmp_path / "reading-items.md"
    p.write_text("## Reading Items\n\n（暂无条目）\n", encoding="utf-8")
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("ddia", "done") is False  # no Log section → not written
    assert "→ ddia" not in p.read_text(encoding="utf-8")


def test_append_record_done_supersedes_prior_fail(tmp_path):
    p = tmp_path / "reading-items.md"
    p.write_text(
        "## Reading Items\n\n（暂无条目）\n\n## 记录（Log）\n\n"
        "### 完成（Organized）\n\n（暂无）\n\n"
        "### 失败 / 放弃（Failed / Aborted）\n\n（暂无）\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("ddia", "fail", "source is not a URL") is True
        assert ra._append_record("ddia", "done") is True
    text = p.read_text(encoding="utf-8")
    done_section = text.split("### 完成（Organized）")[1].split("### 失败")[0]
    fail_section = text.split("### 失败 / 放弃（Failed / Aborted）")[1]
    assert done_section.count("→ ddia") == 1
    assert "ddia" not in fail_section  # later success cleared the earlier failure
    assert fail_section.strip() == "（暂无）"


def test_append_record_done_keeps_other_fails(tmp_path):
    # clearing on success must only touch the successful slug
    p = tmp_path / "reading-items.md"
    p.write_text(
        "## Reading Items\n\n（暂无条目）\n\n## 记录（Log）\n\n"
        "### 完成（Organized）\n\n（暂无）\n\n"
        "### 失败 / 放弃（Failed / Aborted）\n\n（暂无）\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("alpha", "fail", "url dead") is True
        assert ra._append_record("beta", "fail", "file missing") is True
        assert ra._append_record("beta", "done") is True
    text = p.read_text(encoding="utf-8")
    fail_section = text.split("### 失败 / 放弃（Failed / Aborted）")[1]
    assert "alpha" in fail_section
    assert "beta" not in fail_section


def test_strip_record_prefix_sibling_slug(tmp_path):
    # completing `paper` must not delete the fail record of `paper-2024`
    # (a `\b` anchor after the slug would match through the hyphen)
    p = tmp_path / "reading-items.md"
    p.write_text(
        "## Reading Items\n\n（暂无条目）\n\n## 记录（Log）\n\n"
        "### 完成（Organized）\n\n（暂无）\n\n"
        "### 失败 / 放弃（Failed / Aborted）\n\n"
        "- 2026-09-01 → paper（url dead）\n\n"
        "- 2026-09-02 → paper-2024（file missing）\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("paper", "done") is True
    text = p.read_text(encoding="utf-8")
    fail_section = text.split("### 失败 / 放弃（Failed / Aborted）")[1]
    assert "paper（url dead）" not in fail_section
    assert "paper-2024" in fail_section  # sibling fail record survives
    assert "file missing" in fail_section


def test_append_record_refresh_prefix_sibling_slug(tmp_path):
    # refreshing `paper` must replace only `paper`'s line, not `paper-2024`'s
    p = tmp_path / "reading-items.md"
    p.write_text(
        "## Reading Items\n\n（暂无条目）\n\n## 记录（Log）\n\n"
        "### 完成（Organized）\n\n（暂无）\n\n"
        "### 失败 / 放弃（Failed / Aborted）\n\n"
        "- 2026-09-01 → paper（url dead）\n\n"
        "- 2026-09-02 → paper-2024（file missing）\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("paper", "fail", "pdf broken") is True
    text = p.read_text(encoding="utf-8")
    fail_section = text.split("### 失败 / 放弃（Failed / Aborted）")[1]
    assert "pdf broken" in fail_section  # paper's line refreshed with new reason
    assert "paper（url dead）" not in fail_section
    assert "file missing" in fail_section  # paper-2024 untouched
    assert fail_section.count("paper-2024") == 1


def test_append_record_done_clears_midfile_fail_section(tmp_path):
    # removing a fail record from a section that is NOT the last in the file
    # (a following heading exists) must keep the layout and the later section
    p = tmp_path / "reading-items.md"
    p.write_text(
        "## Reading Items\n\n（暂无条目）\n\n## 记录（Log）\n\n"
        "### 完成（Organized）\n\n（暂无）\n\n"
        "### 失败 / 放弃（Failed / Aborted）\n\n"
        "- 2026-09-02 → ddia（file missing）\n\n"
        "## 其他\n\n内容\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("ddia", "done") is True
    text = p.read_text(encoding="utf-8")
    fail_section = text.split("### 失败 / 放弃（Failed / Aborted）")[1].split("## 其他")[0]
    done_section = text.split("### 完成（Organized）")[1].split("### 失败")[0]
    assert "ddia" not in fail_section
    assert done_section.count("→ ddia") == 1
    assert "## 其他" in text  # later section intact


def test_append_record_handwritten_halfwidth_reason(tmp_path):
    # hand-edited fail records may use halfwidth `(reason)` — refresh and the
    # done-clear must still find them (and normalize to the fullwidth form)
    p = tmp_path / "reading-items.md"
    p.write_text(
        "## Reading Items\n\n（暂无条目）\n\n## 记录（Log）\n\n"
        "### 完成（Organized）\n\n（暂无）\n\n"
        "### 失败 / 放弃（Failed / Aborted）\n\n"
        "- 2026-09-01 → ddia(file missing)\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("ddia", "fail", "pdf broken") is True
    text = p.read_text(encoding="utf-8")
    fail_section = text.split("### 失败 / 放弃（Failed / Aborted）")[1]
    assert "（pdf broken）" in fail_section  # refreshed + normalized to fullwidth
    assert fail_section.count("→ ddia") == 1  # no duplicate appended
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra._append_record("ddia", "done") is True
    text = p.read_text(encoding="utf-8")
    fail_section = text.split("### 失败 / 放弃（Failed / Aborted）")[1]
    assert "ddia" not in fail_section  # done cleared the halfwidth-origin record


def test_purge_cache_sources_tolerates_vanished_files(tmp_path):
    # a file removed between glob and unlink (concurrent run) must not crash:
    # Path.unlink(missing_ok=True) swallows the ENOENT from the underlying
    # os.unlink
    d = tmp_path / "c"
    d.mkdir(parents=True)
    (d / "source-01.txt").write_text("x", encoding="utf-8")
    (d / "source-02.txt").write_text("y", encoding="utf-8")
    with mock.patch("os.unlink", side_effect=FileNotFoundError):
        ra._purge_cache_sources(d)  # must not raise
    assert len(list(d.glob("source-*.txt"))) == 2  # os.unlink was faked → nothing deleted


def test_commented_template_skipped(tmp_path):
    p = tmp_path / "reading-assist.md"
    p.write_text(
        "## Reading Items\n\n"
        "<!-- 模板（未启用）\n### placeholder — Example\n- **slug**: placeholder\n"
        "- **状态**: not-started\n-->\n\n当前无活动条目。\n\n## Notes\n",
        encoding="utf-8",
    )
    with mock.patch.object(ra, "ITEMS_FILE", p):
        assert ra.parse_items() == []
