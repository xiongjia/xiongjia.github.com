"""Reading Assistant CLI — manual, run-on-demand entrypoint.

Selects the next actionable entry in ``internal/plans/reading-items.md``
(``## Reading Items``), validates its source, and hands the full reading
workflow to the local pi CLI (which reads ``.pi/skills/reading-assist/SKILL.md``
and runs it with tools: extract text → write ``docs/notes/reading/<slug>/`` →
self-review ≤ 10 rounds → mdformat). On success the items-file entry is marked
``organized`` (organizing done — progress, not "user finished reading") and a
``done`` record is appended to ``internal/plans/reading-items.md``'s Log
section.

There is deliberately NO scheduling: analysis quality needs the user to
review and adjust the notes by hand, so this is a manual workflow — the user
runs ``poe reading-assist run`` when they want to, edits the produced pages,
and decides themselves when to commit. Extracted/pre-fetched sources stay in
the local cache (``$READING_CACHE_DIR/<slug>/``, git-ignored, never deleted
by the script) so re-reading or re-extracting a pdf/epub is easy.

Abort paths — silent, exit 0, **no pages**; an idle no-item skip appends
**no** record:
- no ``## Reading Items`` / no active (not-started or reading) item
- invalid slug (must match ``[a-z0-9-]+``)
- local source file missing / empty
- source unparseable (pymupdf/pypdf unavailable, epub not a zip, file corrupt)
- URL unreachable (curl check via READING_PROXY / env proxy)

Failed/aborted runs against a real item DO append one Log record line
(done → the 完成 section; fail/abort → the 失败 / 放弃 section) — one line
per (slug, result), refreshed on rerun, so outcomes stay traceable in the
items file.

Plan item keys use the Chinese display names (类型 / 状态 / 原材料 / 输出 / 出处);
they are mapped to canonical English keys internally (see ``KEY_MAP``), so the
script logic never depends on the display language.

Usage:
    uv run --with pymupdf --with pypdf python scripts/reading_assist.py list
    uv run --with pymupdf --with pypdf python scripts/reading_assist.py cache [slug]
    uv run --with pymupdf --with pypdf python scripts/reading_assist.py \
        read [slug] [--dry-run] [--timeout 1800] [--model <pattern>]
    uv run --with pymupdf --with pypdf python scripts/reading_assist.py \
        run [slug] [--dry-run] [--timeout 1800] [--model <pattern>]
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # make `shared` importable regardless of cwd

from shared.env import load_env_files  # noqa: E402

# Load .env before module constants so READING_CACHE_DIR etc. take effect
load_env_files(REPO_ROOT)

ITEMS_FILE = REPO_ROOT / "internal" / "plans" / "reading-items.md"
SKILL = REPO_ROOT / ".pi" / "skills" / "reading-assist" / "SKILL.md"
READING_DIR = REPO_ROOT / "docs" / "notes" / "reading"
# Cache dir is env-controlled (default: system temp, never in-repo):
#   READING_CACHE_DIR set → use it; otherwise → {tempfile}/reading-assist
CACHE_DIR = Path(
    os.environ.get("READING_CACHE_DIR") or Path(tempfile.gettempdir()) / "reading-assist"
)
ITEMS_SECTION = "## Reading Items"

# canonical (English) internal item keys; plan file uses Chinese display keys
K_SLUG = "slug"
K_TYPE = "type"
K_STATE = "state"
K_SOURCE = "source"
K_OUTPUT = "output"
K_REF = "ref"

KEY_MAP = {
    "slug": K_SLUG,
    "类型": K_TYPE,
    "状态": K_STATE,
    "原材料": K_SOURCE,
    "输出": K_OUTPUT,
    "出处": K_REF,
}

SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# Plain-text cap per fetched page (override via READING_TEXT_CAP env). A
# page whose plain text is empty (JS-rendered / link-only) or exceeds the cap
# is treated as too complex to reliably summarize — the item aborts and the
# user is asked to provide a local pdf instead. No custom parser is attempted
# for complex pages.
_TEXT_CAP = int(os.environ.get("READING_TEXT_CAP") or 400_000)

# Browser UA for fetching: the default curl UA is often blocked outright by
# anti-robot rules, so we present as a regular browser.
_FETCH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

Item = dict[str, str]


# ---------------------------------------------------------------------------
#  plan parsing
# ---------------------------------------------------------------------------


def parse_items() -> list[Item]:
    """Parse ``## Reading Items`` entries from the items file.

    Line-scan with code-fence / comment awareness: the ``## Reading Items``
    heading only starts the section when NOT inside a ``` fence (the format
    may be documented inside a markdown code block) nor an HTML comment (the
    template example is commented out). Parsing stops at the next ``## ``
    heading, so the ``记录 (Log)`` sections are never treated as items.
    Display keys are mapped to canonical English keys.
    """
    if not ITEMS_FILE.exists():
        return []
    items: list[Item] = []
    cur: Item | None = None
    in_fence = False
    in_comment = False
    in_section = False
    for line in ITEMS_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if s.startswith("<!--"):
            in_comment = "-->" not in line
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if s.startswith("## "):
            title = s[3:].strip()
            if title == "Reading Items" and not in_section:
                in_section = True
                continue
            if in_section:
                break
            continue
        if not in_section:
            continue
        if s.startswith("### "):
            if cur is not None:
                items.append(cur)
            cur = {
                K_SLUG: "",
                K_TYPE: "",
                K_STATE: "not-started",
                K_SOURCE: "",
                K_OUTPUT: "",
                K_REF: "",
            }
            continue
        if cur is not None:
            m = re.match(r"-\s*\*\*([^*]+)\*\*:\s*(.*)", s)
            if m:
                key = KEY_MAP.get(m.group(1).strip(), m.group(1).strip())
                cur[key] = m.group(2).strip()
    if cur is not None:
        items.append(cur)
    return items


def pick(slug: str | None, items: list[Item]) -> Item | None:
    """Explicit slug wins; otherwise first not-started, then first reading."""
    if slug:
        for it in items:
            if it.get(K_SLUG) == slug:
                return it
        return None
    for state in ("not-started", "reading"):
        for it in items:
            if it.get(K_STATE, "not-started") == state:
                return it
    return None


LOG_DONE = "### 完成（Organized）"
LOG_FAIL = "### 失败 / 放弃（Failed / Aborted）"


def mark_organized(slug: str) -> bool:
    """Rewrite the item block's ``- **状态**`` line to ``organized``.

    Locates the block by its ``- **slug**: <slug>`` field, not the ``###``
    heading (a free-form title, e.g. `### Hands-On Data Visualization`), and
    stays scoped to the ``## Reading Items`` section so a same-slug example
    elsewhere in the file is never touched. Returns False when the item or a
    状态 line cannot be found (nothing is written then).
    """
    text = ITEMS_FILE.read_text(encoding="utf-8")
    start = text.find(ITEMS_SECTION)
    if start < 0:
        return False
    section = text[start:]
    lines = section.splitlines(keepends=True)
    slug_re = re.compile(r"^- \*\*slug\*\*:\s*" + re.escape(slug) + r"\s*$")
    slug_i = next((i for i, ln in enumerate(lines) if slug_re.match(ln.strip())), None)
    if slug_i is None:
        return False
    # block start = nearest `### ` heading at/before the slug line
    bstart = next(
        (i for i in range(slug_i, -1, -1) if lines[i].lstrip().startswith("### ")),
        slug_i,
    )
    # block end = next `### ` / `## ` heading after the slug line
    bend = next(
        (i for i in range(slug_i + 1, len(lines)) if lines[i].lstrip().startswith(("### ", "## "))),
        len(lines),
    )
    bstart_off = sum(len(ln) for ln in lines[:bstart])
    bend_off = sum(len(ln) for ln in lines[:bend])
    block = section[bstart_off:bend_off]
    new_block = re.sub(r"(?m)^- \*\*状态\*\*:.*$", "- **状态**: organized", block)
    if new_block == block:
        return False
    new_section = section[:bstart_off] + new_block + section[bend_off:]
    ITEMS_FILE.write_text(text[:start] + new_section, encoding="utf-8")
    return True


# Record lines written to the Log look like `- YYYY-MM-DD → slug` or
# `- YYYY-MM-DD → slug（reason）` (tool writes fullwidth parens; hand-edited
# halfwidth `(reason)` is tolerated when matching). Shared by the refresh and
# clear paths so they can never drift apart.
_REC_DATE = r"- \d{4}-\d{2}-\d{2} → "
_REC_REASON = r"(?:[（(][^\n]*)?"


def _strip_record(text: str, heading: str, slug: str) -> str:
    """Remove the dated outcome line for `slug` from the `heading` section.

    Used so a later success supersedes an earlier failure record of the same
    slug (the Log keeps per-section latest only; a done must also clear a
    prior fail). Collapses blank runs left by the removal so the section stays
    tidy. Returns the text unchanged when the section or record is absent.
    """
    start = text.find(heading)
    if start < 0:
        return text
    tail = text[start + len(heading) :]
    nxt = re.search(r"^#{2,3} ", tail, re.M)
    end = start + len(heading) + (nxt.start() if nxt else len(tail))
    section = text[start:end]
    # After the slug require an opening-paren reason or end-of-line so a
    # hyphen-continued sibling slug (e.g. `paper-2024` when targeting
    # `paper`) never matches — neither as a full line nor as a mangling
    # prefix.
    pat = re.compile(r"(?m)^" + _REC_DATE + re.escape(slug) + _REC_REASON + r"(?:\n|$)")
    new = pat.sub("", section)
    if new == section:
        return text
    new = re.sub(r"\n{3,}", "\n\n", new)
    if end == len(text):  # last section in the file: no dangling blank lines at EOF
        new = new.rstrip("\n") + "\n"
    return text.replace(section, new)


def _append_record(slug: str, kind: str, why: str = "") -> bool:
    """Write (append or refresh) a one-line outcome record in the items Log.

    kind "done" → ``### 完成（Organized）``; anything else →
    ``### 失败 / 放弃（Failed / Aborted）``. Each (slug, kind) keeps only the
    LATEST line: an existing record for the same slug in the same section is
    replaced (date + reason refreshed), otherwise a new line is appended at
    the end of that section — the Log never grows unboundedly with repeated
    nightly runs. Never raises: returns False when the section is missing
    (e.g. tests use a minimal fixture without a Log section). Invalid slugs
    are skipped.
    """
    if not SLUG_RE.fullmatch(slug or ""):
        return False
    if not ITEMS_FILE.exists():
        return False
    head = LOG_DONE if kind == "done" else LOG_FAIL
    text = ITEMS_FILE.read_text(encoding="utf-8")
    if kind == "done":
        # a later success supersedes any earlier failure record of the slug
        # (a stale fail line next to a done line would misreport the item)
        text = _strip_record(text, LOG_FAIL, slug)
    start = text.find(head)
    if start < 0:
        return False
    # section = this heading up to the next `### ` / `## ` heading (or EOF)
    tail = text[start + len(head) :]
    nxt = re.search(r"^#{2,3} ", tail, re.M)
    end = start + len(head) + (nxt.start() if nxt else len(tail))
    section = text[start:end]
    today = date.today().isoformat()
    reason = f"（{why}）" if why else ""
    line = f"- {today} → {slug}{reason}"
    pat = re.compile(r"^" + _REC_DATE + re.escape(slug) + _REC_REASON + r"(?=\n|$)", re.M)
    m = pat.search(section)
    if m:
        new_section = section[: m.start()] + line + section[m.end() :]
    else:
        new_section = section.rstrip() + "\n\n" + line + "\n"
    ITEMS_FILE.write_text(text.replace(section, new_section), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
#  source validation
# ---------------------------------------------------------------------------


def _proxy_args() -> list[str]:
    proxy = (
        os.environ.get("READING_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
    )
    return ["-x", proxy] if proxy else []


def _url_reachable(url: str, timeout: int = 20, attempts: int = 2) -> bool:
    """Cheap reachability probe with one quick retry (transient blips).

    Deliberately muted: max 2 tries with a short backoff, so a site that is
    briefly flaky or protective (ant robot) is not hammered.
    """
    cmd = [
        "curl",
        "-s",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "-m",
        str(timeout),
        "-A",
        _FETCH_UA,
        *_proxy_args(),
        url,
    ]
    for i in range(attempts):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
            code = proc.stdout.strip()
            if code.isdigit() and 200 <= int(code) < 400:
                return True
        except Exception:
            pass
        if i < attempts - 1:
            time.sleep(2 * (i + 1))
    return False


def _import_pdf_reader():
    try:
        import pymupdf  # noqa: F401

        return "pymupdf"
    except ImportError:
        pass
    try:
        import fitz  # noqa: F401

        return "fitz"
    except ImportError:
        pass
    try:
        import pypdf  # noqa: F401

        return "pypdf"
    except ImportError:
        return None


def _pdf_readable(path: Path) -> bool:
    reader = _import_pdf_reader()
    if reader is None:
        return False
    try:
        if reader == "pymupdf":
            import pymupdf

            doc = pymupdf.open(path)
            doc.close()
        elif reader == "fitz":
            import fitz

            doc = fitz.open(path)
            doc.close()
        else:
            from pypdf import PdfReader

            PdfReader(str(path))
        return True
    except Exception:
        return False


def _file_parseable(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "file missing"
    if path.suffix.lower() == ".epub":
        try:
            if not zipfile.is_zipfile(path):
                return False, "epub not a zip"
            return True, "epub ok"
        except Exception:
            return False, "epub unreadable"
    if _pdf_readable(path):
        return True, "pdf ok"
    reader = _import_pdf_reader()
    if reader is None:
        return False, "no pdf extractor (pymupdf/fitz/pypdf unavailable)"
    return False, "pdf unreadable"


class _TextExtractor(HTMLParser):
    """Visible-text collector: skips script/style/head content."""

    _SKIP = {"script", "style", "noscript", "head", "template"}
    _BLOCK = {"br", "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "tr", "table"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP:
            self.skip_depth += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth == 0 and data.strip():
            self.parts.append(data)


def _html_to_text(src_html: Path, dest_txt: Path, cap: int = _TEXT_CAP) -> int:
    """Strip tags/script/style to plain text for the AI (lighter to parse).

    Returns the RAW plain-text length (before any truncation); the written
    copy is capped at `cap` with a notice. Callers use the raw length for the
    oversize guard, so a page beyond the cap aborts instead of being silently
    truncated.
    """
    parser = _TextExtractor()
    parser.feed(src_html.read_text(encoding="utf-8", errors="replace"))
    text = "".join(parser.parts)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    raw_len = len(text)
    if len(text) > cap:
        text = text[:cap] + "\n\n[truncated: page text exceeds cap; js-rendered or huge page]"
    dest_txt.parent.mkdir(parents=True, exist_ok=True)
    dest_txt.write_text(text, encoding="utf-8")
    return raw_len


def _extract_epub_chapters(path: Path, dest_dir: Path, start: int = 1) -> tuple[bool, str, int]:
    """Extract epub chapters (by spine/toc) to source-NN.txt files.

    Returns (ok, reason, count written). Uses stdlib zipfile + ElementTree:
    META-INF/container.xml → OPF manifest/spine → chapter html files →
    plain text via _TextExtractor.
    """
    try:
        import zipfile
        from xml.etree import ElementTree as ET

        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            try:
                container = ET.fromstring(z.read("META-INF/container.xml"))
            except KeyError:
                return False, "epub has no META-INF/container.xml", 0
            ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            rootfile = container.find(".//c:rootfile", ns)
            if rootfile is None:
                return False, "epub container: no rootfile", 0
            opf_path = rootfile.get("full-path", "content.opf")
            opf = ET.fromstring(z.read(opf_path))
            opf_ns = {"o": "http://www.idpf.org/2007/opf"}
            # dirname of the OPF; empty when the OPF sits at the zip root
            # (flat epub). rsplit()[0] would return the whole path for a
            # slash-free value, so use dirname instead.
            base = posixpath.dirname(opf_path)
            manifest: dict[str, str] = {}
            for item in opf.findall(".//o:manifest/o:item", opf_ns):
                manifest[item.get("id", "")] = item.get("href", "")
            spine = [s.get("idref", "") for s in opf.findall(".//o:spine/o:itemref", opf_ns)]
            hrefs = [manifest[i] for i in spine if i in manifest]
            if not hrefs:
                return False, "epub spine is empty", 0
            dest_dir.mkdir(parents=True, exist_ok=True)
            written = 0
            for i, href in enumerate(hrefs, start=start):
                p = (base + "/" + href) if base else href
                # normalize `./` and `../` segments (valid EPUB hrefs may be
                # relative to the OPF dir); zip members always use `/`
                p = posixpath.normpath(p.lstrip("/"))
                if p not in names:
                    continue
                raw = z.read(p)
                head = raw[:2000].lower()
                is_html = p.endswith((".html", ".xhtml")) or b"<html" in head or b"<body" in head
                if is_html:
                    parser = _TextExtractor()
                    parser.feed(raw.decode("utf-8", errors="replace"))
                    text = re.sub(r" *\n *", "\n", "".join(parser.parts))
                    text = re.sub(r"\n{3,}", "\n\n", text).strip()
                    if text:
                        (dest_dir / f"source-{i:02d}.txt").write_text(text, encoding="utf-8")
                        written += 1
            return True, "", written
    except zipfile.BadZipFile:
        return False, "epub not a zip", 0
    except Exception as exc:  # noqa: BLE001 — report any structural error
        return False, f"epub parse error: {exc}", 0


def _extract_pdf_chapters(path: Path, dest_dir: Path, start: int = 1) -> tuple[bool, str, int]:
    """Extract pdf text grouped by bookmarks (TOC) into source-NN.txt files.

    Uses pymupdf when available (bookmark-aware); falls back to pypdf with a
    fixed page-group chunk (no bookmarks). Returns (ok, reason, count).
    """
    try:
        import pymupdf  # type: ignore
    except ImportError:  # pragma: no cover - fallback path
        return _extract_pdf_pypdf(path, dest_dir, start)
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001
        return False, f"pdf open error: {exc}", 0
    try:
        toc = doc.get_toc(simple=True) or []
        dest_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        entries = [(lvl, pageno) for lvl, _title, pageno in toc if lvl == 1]
        if entries:
            # clamp bookmark page numbers to [1, page_count] (pymupdf uses
            # negative indexing for the last page, so an out-of-range bookmark
            # would otherwise silently map to the wrong group)
            bounds = [max(1, min(p, doc.page_count)) for _lvl, p in entries]
            bounds.append(doc.page_count + 1)
            for i in range(len(entries)):
                s, e = bounds[i] - 1, bounds[i + 1] - 1
                text = "".join(
                    doc.load_page(p).get_text() for p in range(s, min(e, doc.page_count))
                ).strip()
                if text:
                    (dest_dir / f"source-{start + i:02d}.txt").write_text(text, encoding="utf-8")
                    written += 1
            return True, "", written
        # no usable bookmarks → fixed page groups (20 pages each)
        step = 20
        groups = [range(i, min(i + step, doc.page_count)) for i in range(0, doc.page_count, step)]
        for i, pages in enumerate(groups):
            text = "".join(doc.load_page(p).get_text() for p in pages).strip()
            if text:
                (dest_dir / f"source-{start + i:02d}.txt").write_text(text, encoding="utf-8")
                written += 1
        return True, "", written
    except Exception as exc:  # noqa: BLE001 — malformed bookmarks/pages must not crash
        return False, f"pdf extract error: {exc}", 0
    finally:
        doc.close()


def _extract_pdf_pypdf(path: Path, dest_dir: Path, start: int = 1) -> tuple[bool, str, int]:
    """pypdf fallback: fixed page-group extraction (no bookmarks)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return False, "no pdf extractor (pymupdf/fitz/pypdf unavailable)", 0
    try:
        reader = PdfReader(str(path))
        dest_dir.mkdir(parents=True, exist_ok=True)
        pages = list(reader.pages)
        written = 0
        step = 20
        for i in range(0, len(pages), step):
            text = "".join(p.extract_text() or "" for p in pages[i : i + step]).strip()
            if text:
                (dest_dir / f"source-{start + i // step:02d}.txt").write_text(
                    text, encoding="utf-8"
                )
                written += 1
        return True, "", written
    except Exception as exc:  # noqa: BLE001
        return False, f"pdf extract error: {exc}", 0


def _extract_to_cache(path: Path, dest_dir: Path, start: int = 1) -> tuple[bool, str, int]:
    """Extract a local pdf/epub into chapter-grouped source-NN.txt files."""
    if path.suffix.lower() == ".epub":
        return _extract_epub_chapters(path, dest_dir, start)
    return _extract_pdf_chapters(path, dest_dir, start)


def _fetch_article(url: str, dest: Path, attempts: int = 3, backoff: float = 2.0) -> bool:
    """Pre-fetch the article into the local cache: bounded curl + muted retries.

    Fetching happens in the script (not inside the pi run) so a hanging
    network call cannot stall the whole pipeline; pi then reads the local
    text and never needs the network.

    Retry policy is deliberately conservative for anti-bot (ant robot)
    courtesy: max `attempts` tries (default 3) with growing backoff
    (2s, 4s), sequential — never parallel, never hammering. Uses a browser
    user-agent so default-curl-UA blocking is avoided.
    """
    cmd = [
        "curl",
        "-sS",
        "-L",
        "-m",
        "20",
        "-A",
        _FETCH_UA,
        *_proxy_args(),
        url,
    ]
    for i in range(attempts):
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with dest.open("wb") as fh:
                proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.DEVNULL, timeout=30)
            if proc.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
                return True
        except Exception:
            pass
        if i < attempts - 1:
            time.sleep(backoff * (i + 1))
    return dest.exists() and dest.stat().st_size > 0


def _resolve_local_path(raw: str) -> Path:
    """Resolve a user-written local-file reference to a real path.

    A ``{projectRoot}`` placeholder is first replaced with the repo root, so
    `{projectRoot}/external/book/1.pdf` works regardless of where the repo is
    checked out. After replacement, absolute paths pass through unchanged.
    Relative paths are tried in order:
    1. repo root (e.g. the user writes `external/book/x.pdf` verbatim)
    2. `external/<path>` (e.g. `book/x.pdf`)
    3. `external/book/<path>` (e.g. just `x.pdf`)
    First existing candidate wins; if none exists the first candidate is
    returned so the error message names the canonical location.
    """
    cand = Path(raw.replace("{projectRoot}", str(REPO_ROOT))).expanduser()
    if cand.is_absolute():
        return cand
    candidates = [
        REPO_ROOT / cand,
        REPO_ROOT / "external" / cand,
        REPO_ROOT / "external" / "book" / cand,
    ]
    return next((c for c in candidates if c.exists()), candidates[0])


def _cache_matches(cache_dir: Path, sources: list[str]) -> bool:
    """True when the cache already holds source-*.txt for exactly `sources`.

    A manifest.txt records the space-separated source list (URLs or local file
    paths) that produced the cache; reuse only when the manifest matches the
    current 原材料, so editing sources re-fetches/re-extracts.
    """
    manifest = cache_dir / "manifest.txt"
    if not manifest.exists():
        return False
    cached = [ln.strip() for ln in manifest.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if cached != sources:
        return False
    # manifest matches, but only reuse if the source files actually exist
    # (a partially deleted cache would otherwise be silently reused)
    return len(sorted(cache_dir.glob("source-*.txt"))) >= len(sources)


def _write_manifest(cache_dir: Path, sources: list[str]) -> None:
    """Record which sources the cache was built from (one per line)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "manifest.txt").write_text("\n".join(sources) + "\n", encoding="utf-8")


def _purge_cache_sources(cache_dir: Path) -> None:
    """Remove stale extracted source-*.txt before a full re-extraction.

    Only invoked when the cache manifest no longer matches the current source
    list (slug re-used for a different source set, or the input mode switched
    between URL and local file), so leftover chapter text from an earlier
    source set is never picked up later by build_prompt's glob. Fetched
    source-*.html need no purge: they are always rewritten per URL.
    """
    if not cache_dir.exists():
        return
    for p in cache_dir.glob("source-*.txt"):
        # missing_ok: a concurrent `cache`/bot run may have removed the file
        # between glob and unlink; ignore rather than crash the pipeline
        p.unlink(missing_ok=True)


def _sources_are_urls(raw: str) -> bool:
    """True when every space-separated source is an http(s) URL.

    Decides the input mode for article/paper sources: all-URLs → web
    (pre-fetch each URL); anything else (typically a local pdf/epub path the
    user downloaded) → local-file mode, the same as book/novel.
    """
    parts = raw.split()
    return bool(parts) and all(u.startswith(("http://", "https://")) for u in parts)


def _prepare_cache(item: Item) -> tuple[bool, str]:
    """Ensure the item's raw material is usable and locally cached.

    Idempotent: for web sources (article/paper with all-URL 原材料), if
    ``CACHE_DIR/<slug>/`` already holds the expected number of ``source-*.txt``
    files the cache is reused (no re-fetch); otherwise each URL is checked,
    fetched (with retries + UA) and stripped to plain text, with a complexity
    guard that aborts and asks for a local pdf for JS-rendered/oversize pages.
    For local-file sources (book/novel, or paper/article given a downloaded
    pdf/epub), the local files are validated and chapter text pre-extracted
    into the cache. Returns (ok, reason).
    """
    slug = (item.get(K_SLUG) or "").strip()
    if not SLUG_RE.fullmatch(slug):
        return False, "invalid slug (must match [a-z0-9-]+)"
    typ = (item.get(K_TYPE) or "").strip().lower()
    # Tolerate parenthetical annotations appended to the value (e.g.
    # `article (online book)`): take the first segment so an annotated type
    # does not accidentally fall into the local-file branch.
    for _sep in ("（", "("):
        if _sep in typ:
            typ = typ.split(_sep, 1)[0].strip()
            break
    raw = (item.get(K_SOURCE) or "").strip()
    if not raw:
        return False, "source is empty"
    # A single source value may hold several space-separated sources:
    # all-URLs → web mode (article/paper, each URL its own file); local
    # files → local-file mode (book/novel, or paper/article with a downloaded
    # pdf/epub; each file a volume). Any source unusable → the whole item
    # aborts.
    sources = raw.split()
    is_web = _sources_are_urls(raw)
    if (
        typ in ("article", "paper")
        and sources
        and not is_web
        and any(s.startswith(("http://", "https://")) for s in sources)
    ):
        return False, "mixed sources (URL + local file) are unsupported for article/paper"
    if typ in ("article", "paper") and is_web:
        urls = sources
        cache_dir = CACHE_DIR / slug
        if _cache_matches(cache_dir, urls):
            return True, ""
        _purge_cache_sources(cache_dir)
        for url in urls:
            if not _url_reachable(url):
                return False, f"URL unreachable: {url}"
        for i, url in enumerate(urls, start=1):
            dest = cache_dir / f"source-{i:02d}.html"
            if not _fetch_article(url, dest):
                return False, f"URL fetch failed: {url}"
            if not dest.exists():
                return False, f"fetch produced no file: {url}"
            size = _html_to_text(dest, cache_dir / f"source-{i:02d}.txt")
            # Complexity guard, no custom parser: empty plain text (JS-rendered
            # / link-only page) or oversize text ⇒ abort and ask for a pdf.
            if size == 0:
                return (
                    False,
                    "no readable text (JS-rendered or link-only page): "
                    f"{url} — provide a local pdf",
                )
            if size > _TEXT_CAP:
                return (
                    False,
                    f"page too large/complex ({size} chars): {url} — abort, provide a local pdf",
                )
        _write_manifest(cache_dir, urls)
        return True, ""
    # local-file mode (book/novel by design; paper/article when the user
    # supplies a local pdf/epub): validate each local file AND pre-extract
    # chapter text into the cache (idempotent — a manifest-matching cache is
    # reused, so `read` after `cache` does not re-extract; changing 原材料
    # re-extracts).
    cache_dir = CACHE_DIR / slug
    files = sources
    if _cache_matches(cache_dir, files):
        return True, ""
    _purge_cache_sources(cache_dir)
    idx = 0
    for f in files:
        path = _resolve_local_path(f)
        ok, why = _file_parseable(path)
        if not ok:
            return False, f"{f}: {why}"
        ok2, why2, n = _extract_to_cache(path, cache_dir, start=idx + 1)
        if not ok2:
            return False, f"{f}: {why2}"
        if n == 0:
            return False, f"{f}: no extractable text (scanned pdf?) — provide a text-based pdf"
        idx += n
    _write_manifest(cache_dir, files)
    return True, ""


def validate(item: Item) -> tuple[bool, str]:
    """Backwards-compatible alias for _prepare_cache."""
    return _prepare_cache(item)


def item_index(item: Item) -> Path:
    """Index path the pages must be written to (honors the output field, falls back to slug)."""
    slug = item.get(K_SLUG) or "?"
    out = (item.get(K_OUTPUT) or "").strip().rstrip("/")
    if not out:
        out = f"docs/notes/reading/{slug}"
    return (REPO_ROOT / out) / "index.md"


def _cleanup_cache(slug: str) -> None:
    """Remove the item's cache dir; best-effort also prunes empty CACHE_DIR.

    Not called by the CLI — cache sources are kept for the user to re-read /
    re-extract. Available as a manual cleanup helper. Never touches paths for
    invalid slugs (path-traversal guard).
    """
    if not SLUG_RE.fullmatch(slug):
        return
    shutil.rmtree(CACHE_DIR / slug, ignore_errors=True)
    try:
        CACHE_DIR.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
#  pi invocation
# ---------------------------------------------------------------------------


def build_prompt(item: Item) -> str:
    typ = item.get(K_TYPE) or ""
    slug = item.get(K_SLUG) or "?"
    raw = item.get(K_SOURCE) or ""
    out = item.get(K_OUTPUT) or f"docs/notes/reading/{slug}/"
    if typ in ("article", "paper") and _sources_are_urls(raw):
        urls = raw.split()
        txts = [str(CACHE_DIR / slug / f"source-{i:02d}.txt") for i in range(1, len(urls) + 1)]
        if len(urls) == 1:
            source = (
                "pre-fetched text (fetched + stripped to plain text by the script, no network): "
                f"{txts[0]}"
            )
        else:
            source = (
                "pre-fetched text (article series, one plain-text file each, in order):\n"
                + "\n".join(f"  - {p}" for p in txts)
            )
    else:
        # local-file mode (book/novel; paper/article with a local pdf/epub):
        # chapter text was pre-extracted into the cache by `cache`
        # (source-NN.txt per chapter / volume group)
        cache_dir = CACHE_DIR / slug
        txts = sorted(str(p) for p in cache_dir.glob("source-*.txt")) if cache_dir.exists() else []
        if txts:
            source = (
                "pre-extracted chapter text (pdf/epub split into chapters by the "
                "script, one file per chapter/volume, in order):\n"
                + "\n".join(f"  - {p}" for p in txts)
            )
        else:
            paths = [_resolve_local_path(f) for f in raw.split()]
            joined = ", ".join(str(p) for p in paths)
            source = f"local files (not yet cached, run `cache` first): {joined}"
    prompt = f"""You are the Reading Assistant. First read {SKILL} (the skill spec),
then strictly follow its 「read」 main workflow for the item below.

Item:
- slug: {slug}
- type (类型): {typ}
- source note (出处): {item.get(K_REF, "")}
- state (状态): {item.get(K_STATE, "not-started")}
- raw material (原材料): {source}
- output dir (输出): {out}

1. Raw material is a local pdf/epub file (book/novel, or paper/article with
   a downloaded file): the script already extracted chapter text into
   source-NN.txt files under {CACHE_DIR}/{slug}/ (epub split by spine/toc;
   pdf by bookmarks, else page groups). Directly read every source-*.txt —
   **each file → one page (ch-0001… or part-0001…, in file order)**. Do NOT
   re-extract the pdf/epub yourself. If a file has no readable text (scanned
   pdf), say so and stop — the user must provide a text-based pdf.
2. Raw material is pre-fetched web text (article/paper from URL(s)): directly
   read every source-*.txt in {CACHE_DIR}/{slug}/ (the script already fetched
   and stripped tags to plain text; no network needed; JS-rendered pages may
   leave very short text — that is expected, summarize the readable content).
   **One page per file → part-0001… (in file order); cross-file concepts and
   the series storyline go into notes.md and index.md**. Long articles may be
   split further. **If a file's plain text is empty or too short (JS-rendered
   or link-only page), say so, stop, and recommend the user provide a local
   pdf — do not attempt a custom parser for complex pages.**
   (If future fetching is ever needed, curl must use
   `-m 20` timeout to avoid hanging; proxy fallback chain:
   $READING_PROXY → $https_proxy → default local proxy http://127.0.0.1:1095.)
3. Write the full page set under {out}: index.md (entry: type / state
   (reading ↔ organized) / author / provenance (出处) + whole-work
   storyline + **organizing-done date** (reading-done date is NOT auto-filled)
   + reading-notes entry first + chapter entries) + ch-0001…/part-0001… +
   notes.md (reading notes); novel/narrative types additionally get
   characters.md (character names kept in the original language) +
   storyline.md (mermaid timeline/flowchart); sub-pages add
   `hide: [navigation]` to frontmatter.
   **The whole-book storyline (全书主线) is a concise LIST by default — no
   mermaid.** Use mermaid only when there is a real flow/branching relation,
   and keep every node label short (≤ 10 chars); put details in the list
   below the diagram, never in long node labels (they render cramped).
4. Keep docs/notes/reading/index.md overview in sync (sections by type:
   dev/tech books, novels, articles, papers).
5. Forced self-review loop (≤10 rounds, fresh context): sensitive info
   cleared / logic & completeness / consistency (slug, links, English terms)
   / format & CI (frontmatter complete, mdformat, mermaid build-time render).
6. After the output, run mdformat on it
   (uv run mdformat docs/notes/reading internal/plans/reading-items.md).

Hard constraints (violating any fails self-review):
- Never git commit / git push; do not modify unrelated files.
- Book source never lands in the repo; output pages contain only summaries +
  short excerpts (≤10 lines each).
- File/dir names only [a-z0-9-]; every page has title/tags/categories in
  frontmatter; use relative links between pages.
- Keep original-language concepts/terms/character names untranslated; body
  text defaults to Chinese.
- If the raw material is unusable or self-review cannot be fixed, stop and
  explain why (the script will not archive the item).
"""
    return prompt


def run_pi(prompt: str, timeout: int, model: str | None) -> str:
    """Run the local pi CLI with a visible heartbeat (no silent waiting).

    The pi phase can take minutes (extract → write pages → self-review up to
    10 rounds); previously it printed nothing until done or timed out. Stream
    the subprocess output into buffers, print a heartbeat every 60s, and
    enforce the timeout by killing the process — so the caller always sees
    that the pipeline is alive.
    """
    pi_bin = shutil.which("pi")
    if not pi_bin:
        raise RuntimeError("pi CLI not found on PATH — install pi-coding-agent")
    cmd = [pi_bin, "-p", "--no-session", "--mode", "json"]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    print(
        f"→ calling local pi (may take minutes; heartbeat every 60s, timeout {timeout}s)",
        flush=True,
    )
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out: list[str] = []
    err: list[str] = []

    def _pump(stream, sink):
        for line in iter(stream.readline, ""):
            sink.append(line)

    t_out = threading.Thread(target=_pump, args=(proc.stdout, out), daemon=True)
    t_err = threading.Thread(target=_pump, args=(proc.stderr, err), daemon=True)
    t_out.start()
    t_err.start()
    start = time.monotonic()
    last_beat = start
    timed_out = False
    while proc.poll() is None:
        now = time.monotonic()
        if now - start > timeout:
            proc.kill()
            timed_out = True
            break
        if now - last_beat >= 60:
            print(f"⏳ pi still running… ({int(now - start)}s / {timeout}s timeout)", flush=True)
            last_beat = now
        time.sleep(1)
    t_out.join(timeout=5)
    t_err.join(timeout=5)
    elapsed = int(time.monotonic() - start)
    if timed_out:
        raise RuntimeError(f"pi timed out after {timeout}s")
    if proc.returncode != 0:
        detail = ("".join(err) or "".join(out)).strip()[-500:]
        raise RuntimeError(f"pi exited with code {proc.returncode} after {elapsed}s: {detail}")
    print(f"✓ pi analysis done ({elapsed}s)", flush=True)
    return ("".join(out)).strip()[-800:]


# ---------------------------------------------------------------------------
#  post-processing
# ---------------------------------------------------------------------------


def run_mdformat() -> int:
    """Normalize produced markdown (matches `poe fmt` mdformat paths).

    Returns the subprocess exit code so callers can fail loudly when
    formatting fails instead of silently reporting success.
    """
    targets = [
        "docs/notes/reading",
        "internal/plans/reading-items.md",
    ]
    # Nested `uv run` inherits an outer uv-managed VIRTUAL_ENV (e.g. the
    # `--with pymupdf --with pypdf` temp build env) which does not match
    # `.venv`, producing a warning. Drop it so the inner uv targets .venv.
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    proc = subprocess.run(
        ["uv", "run", "mdformat", *targets],
        cwd=REPO_ROOT,
        env=env,
    )
    return proc.returncode


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------


def _print_items(items: list[Item]) -> None:
    if not items:
        print("(no Reading Items entries)")
        return
    for it in items:
        print(
            "- {slug} | {typ} | {state} | {source}".format(
                slug=it.get(K_SLUG) or "?",
                typ=it.get(K_TYPE) or "?",
                state=it.get(K_STATE) or "?",
                source=it.get(K_SOURCE) or "",
            )
        )


def _read_flow(args, item: Item) -> int:
    """AI analysis + archive for an already-prepared item.

    Used by both `read` (sources assumed ready) and `run` (cache + read).
    Includes the dry-run preview. Returns the process exit code.
    """
    slug = item.get(K_SLUG) or "?"
    if args.dry_run:
        # Preview only: no AI call, no writes
        print(f"== item ==\n{slug} | {item.get(K_TYPE)} | {item.get(K_STATE)}")
        print(f"source: {item.get(K_SOURCE)}")
        print(f"output: {item.get(K_OUTPUT)}")
        print("== prompt ==")
        print(build_prompt(item))
        return 0
    prompt = build_prompt(item)
    try:
        run_pi(prompt, timeout=args.timeout, model=args.model)
    except RuntimeError as exc:
        _append_record(slug, "fail", str(exc).splitlines()[0][:120])
        print(f"✗ {exc}")
        return 1
    index = item_index(item)
    if not index.exists():
        _append_record(slug, "fail", "no index.md produced")
        print(f"✗ {slug}: no index.md produced — item stays {item.get(K_STATE) or 'not-started'}")
        return 1
    # Format before marking: a mdformat failure must not leave the entry
    # marked organized while the output is not format-clean.
    rc = run_mdformat()
    if rc != 0:
        _append_record(slug, "fail", f"mdformat failed (rc={rc})")
        print(f"✗ {slug}: mdformat failed (rc={rc}) — item not marked organized")
        return 1
    if not mark_organized(slug):
        # Pages exist but the item was not marked organized (missing item
        # block / no state line — an authoring error in the items file). Record
        # as fail and return 1 so the bot reports a failure instead of nightly
        # retries; the entry staying not-started would otherwise be re-picked
        # by cron, and rc=1 stops it masquerading as a successful PR.
        _append_record(slug, "fail", "pages written but entry not marked organized")
        print(f"✗ {slug}: pages written but entry not marked — fix the reading-items entry, rc=1")
        return 1
    _append_record(slug, "done")
    # Cache sources under $READING_CACHE_DIR/<slug>/ are intentionally KEPT:
    # the user may re-open them while reading (edit summaries, re-extract a
    # pdf/epub), so nothing is deleted on any path. For local-file sources the
    # source itself is the cache, so point at it instead.
    raw = (item.get(K_SOURCE) or "").strip()
    is_url = _sources_are_urls(raw)
    print(f"✓ {slug} organized; pages under {index.parent}")
    if is_url:
        print(f"  (raw sources kept in {CACHE_DIR / slug}/ — delete manually when done)")
    else:
        print(f"  (source: {raw})")
    return 0


def _pick_or_skip(args) -> Item | None:
    """Load items and pick one; prints the skip message when none is actionable."""
    load_env_files(REPO_ROOT)
    items = parse_items()
    item = pick(args.slug, items)
    if item is None:
        print("⏭ no actionable Reading Items entry (none or all organized)")
        return None
    return item


def _cmd_cache(args) -> int:
    """Step 1: fetch/extract the raw material into the local cache only."""
    item = _pick_or_skip(args)
    if item is None:
        return 0
    slug = item.get(K_SLUG) or "?"
    raw = (item.get(K_SOURCE) or "").strip()
    is_url = _sources_are_urls(raw)
    print(f"cache {slug}: preparing sources…", flush=True)
    ok, why = _prepare_cache(item)
    if not ok:
        _append_record(slug, "abort", why)
        print(f"⏭ skip {slug}: {why}")
        return 0
    cache_dir = CACHE_DIR / slug
    txts = sorted(cache_dir.glob("source-*.txt")) if cache_dir.exists() else []
    if is_url or txts:
        print(f"✓ cache {slug} ready; sources in {cache_dir}/")
        if not is_url and txts:
            print(f"  ({len(txts)} chapter files extracted from the local pdf/epub)")
    else:
        files = [_resolve_local_path(f) for f in raw.split()]
        print(f"✓ cache {slug} ready (local source, no cache copy): {', '.join(map(str, files))}")
    return 0


def _cmd_read(args) -> int:
    """Step 2: AI analysis on the cached sources (cache must be ready)."""
    item = _pick_or_skip(args)
    if item is None:
        return 0
    slug = item.get(K_SLUG) or "?"
    print(f"① {slug}: ensuring sources ready…", flush=True)
    ok, why = _prepare_cache(item)
    if not ok:
        _append_record(slug, "abort", why)
        print(f"⏭ skip {slug}: {why}")
        return 0
    print(f"② {slug}: sources OK…", flush=True)
    return _read_flow(args, item)


def _cmd_run(args) -> int:
    """cache + read in one go (backwards compatible)."""
    item = _pick_or_skip(args)
    if item is None:
        return 0
    slug = item.get(K_SLUG) or "?"
    print(f"① {slug}: preparing sources…", flush=True)
    ok, why = _prepare_cache(item)
    if not ok:
        _append_record(slug, "abort", why)
        print(f"⏭ skip {slug}: {why}")
        return 0
    print(f"② {slug}: sources ready…", flush=True)
    return _read_flow(args, item)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reading-assist",
        description="Reading Assistant: process Reading Items entries via local pi.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List Reading Items entries (slug / type / state / source)")
    cache_p = sub.add_parser(
        "cache",
        help="Step 1: fetch/extract the raw material into the local cache only (no AI)",
    )
    read_p = sub.add_parser(
        "read",
        help="Step 2: run the AI analysis (auto-prepares sources if not cached)",
    )
    run_p = sub.add_parser(
        "run",
        help="cache + read in one go (default first not-started/reading)",
    )
    for p in (cache_p, read_p, run_p):
        p.add_argument("slug", nargs="?", default=None, help="Target item slug")
    for p in (read_p, run_p):
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the selected item + prompt, no AI call",
        )
        p.add_argument(
            "--timeout", type=int, default=1800, help="pi timeout in seconds (default 1800)"
        )
        p.add_argument("--model", default=None, help="pi model pattern (default: local config)")
    args = parser.parse_args(argv)
    if args.cmd == "list":
        load_env_files(REPO_ROOT)
        _print_items(parse_items())
        return 0
    if args.cmd == "cache":
        return _cmd_cache(args)
    if args.cmd == "read":
        return _cmd_read(args)
    return _cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
