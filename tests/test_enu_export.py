"""Tests for scripts/enu.py export (English Scraps → Anki apkg / CSV)."""

import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRAPS_REL = Path("notes/research/topics/english/scraps")
ARCHIVE_REL = SCRAPS_REL / "archive" / "2026-w33.md"

FIXTURE = """---
hide:
  - navigation
title: English Scraps Archive 2026-w33
tags: [english, archive]
categories: [dev]
---

# English Scraps Archive — 2026-w33

## 卡片

### cumbersome

- **type**: word
- **date**: 2026-08-08
- **source**: 技术文档（Kubernetes 官方文档）
- **status**: new
- **tags**: [technical, adjective]
- **发音**: /ˈkʌmbəsəm/
- **含义**: 笨重的；繁琐的
- **英义**: difficult to handle or deal with because of complexity or size
- **记忆**: 词根 cumber-（阻碍）+ -some
- **语境**: 指代码实现难以维护
- **原句**: The implementation is cumbersome to maintain.
- **造句**: The API is intuitive to use.
- **同义/反义**: unwieldy / handy

### come up with

- **type**: phrasal-verb
- **date**: 2026-08-09
- **source**: 未知来源
- **status**: new
- **tags**: [informal, idea]
- **含义**: 想出（主意/方案）
- **例句**: We came up with a plan.
- **替换**: think of

### would have done

- **type**: grammar
- **date**: 2026-08-09
- **source**: 未知来源
- **status**: new
- **tags**: [conditional]
- **例句**: I would have helped if you had asked.
- **规则**: 表与过去事实相反的虚拟语气
- **易错点**: 与 would do 的区别

### The implementation is cumbersome to maintain

- **type**: sentence
- **date**: 2026-08-08
- **source**: 未知来源
- **status**: new
- **tags**: [technical]
- **原句**: The implementation is cumbersome to maintain.
- **结构拆解**: 主语 + 系动词 + 表语 + 不定式
- **翻译**: 这个实现方式维护起来很繁琐。

### some unknown thing

- **type**: misc
- **date**: 2026-08-10
- **status**: new
- **tags**: []
- **备注**: 无法判定

### something odd

- **date**: 2026-08-10
- **status**: new
"""


def _run_enu(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/enu.py"), *args, "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )


def _write_fixture(tmp_path: Path, crlf: bool = False) -> Path:
    path = tmp_path / ARCHIVE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    text = FIXTURE.replace("\n", "\r\n") if crlf else FIXTURE
    path.write_text(text, encoding="utf-8")
    return path


def _apkg_notes(apkg: Path, tmp_path: Path) -> list[tuple[str, str, str]]:
    """Return (guid, fields, tags) rows from an apkg's collection.anki2."""
    with zipfile.ZipFile(apkg) as z:
        z.extract("collection.anki2", tmp_path)
    con = sqlite3.connect(tmp_path / "collection.anki2")
    try:
        return con.execute("SELECT guid, flds, tags FROM notes").fetchall()
    finally:
        con.close()


def test_export_apkg_creates_valid_package(tmp_path):
    _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--dry-run", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "4 card(s)" in proc.stdout

    apkg = next(out.glob("english-scraps-*.apkg"))
    notes = _apkg_notes(apkg, tmp_path)
    # 4 exportable cards (word / phrasal-verb / grammar / sentence);
    # the misc card and the type-less block are skipped
    assert len(notes) == 4, [n[1] for n in notes]

    fields_by_key = {}
    for guid, fields, tags in notes:
        note_fields = fields.split("\x1f")
        fields_by_key[guid] = note_fields
        if note_fields[0] == "cumbersome":
            assert "technical" in tags and "adjective" in tags
    # deterministic, unique guids
    guids = sorted(fields_by_key)
    assert len(set(guids)) == 4
    # spot-check a word note: term + ipa present
    for fields in fields_by_key.values():
        if fields[0] == "cumbersome":
            assert fields[1] == "/ˈkʌmbəsəm/"
            assert "笨重的" in fields[2]
            break
    else:
        raise AssertionError("cumbersome note not found")


def test_export_apkg_guid_stable_across_runs(tmp_path):
    _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    assert _run_enu(tmp_path, "export", "--dry-run", "--out", str(out)).returncode == 0
    apkg1 = next(out.glob("english-scraps-*.apkg"))
    guids1 = sorted(g for g, _f, _t in _apkg_notes(apkg1, tmp_path))
    assert _run_enu(tmp_path, "export", "--dry-run", "--out", str(out)).returncode == 0
    apkg2 = next(out.glob("english-scraps-*.apkg"))
    guids2 = sorted(g for g, _f, _t in _apkg_notes(apkg2, tmp_path))
    assert guids1 == guids2


def test_export_csv_utf8_bom_and_key_column(tmp_path):
    _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--format", "csv", "--dry-run", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "CSV written" in proc.stdout

    word_csv = out / "word.csv"
    assert word_csv.exists()
    raw = word_csv.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    lines = raw.decode("utf-8-sig").strip().splitlines()
    assert lines[0].split(",")[0] == "key"
    assert lines[1].startswith("word:cumbersome,cumbersome,/ˈkʌmbəsəm/,")
    assert "come-up-with" not in raw.decode("utf-8-sig")  # different type file
    assert (out / "phrasal-verb.csv").exists()
    pv = (out / "phrasal-verb.csv").read_text(encoding="utf-8-sig").splitlines()
    assert pv[1].startswith("phrasal-verb:come-up-with,")


def test_export_sentence_dedup_key_uses_original(tmp_path):
    _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--format", "csv", "--dry-run", "--out", str(out))
    assert proc.returncode == 0, proc.stderr

    sent = (out / "sentence.csv").read_text(encoding="utf-8-sig").splitlines()
    # key derives from the full 原句 (not the truncated ### title)
    assert sent[1].startswith("sentence:the-implementation-is-cumbersome-to-maintain.,")


def test_export_status_rewrite_new_to_learning(tmp_path):
    path = _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "Status updated: 4 card(s) new → learning" in proc.stdout

    text = path.read_text(encoding="utf-8")
    assert text.count("- **status**: learning") == 4
    # the misc card and the type-less block are not exportable — their status stays new
    assert text.count("- **status**: new") == 2

    # second export: nothing left to export
    proc2 = _run_enu(tmp_path, "export", "--out", str(out))
    assert proc2.returncode == 0, proc2.stderr
    assert "No cards to export." in proc2.stdout


def test_export_all_re_exports_learning_cards(tmp_path):
    _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    assert _run_enu(tmp_path, "export", "--out", str(out)).returncode == 0
    proc = _run_enu(tmp_path, "export", "--all", "--dry-run", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "4 card(s)" in proc.stdout


def test_export_misc_type_prints_hint(tmp_path):
    _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--type", "misc", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "misc cards have no Anki template" in proc.stdout


def test_export_dry_run_keeps_status(tmp_path):
    path = _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--dry-run", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "Dry run" in proc.stdout
    assert "- **status**: new" in path.read_text(encoding="utf-8")


def test_export_filter_type_and_tag(tmp_path):
    _write_fixture(tmp_path)
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--type", "word", "--dry-run", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "word × 1" in proc.stdout
    notes = _apkg_notes(next(out.glob("english-scraps-*.apkg")), tmp_path)
    assert len(notes) == 1

    proc = _run_enu(tmp_path, "export", "--tag", "technical", "--dry-run", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "word × 1" in proc.stdout and "sentence × 1" in proc.stdout


def test_export_no_cards_when_empty_archive(tmp_path):
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "No cards to export." in proc.stdout
    assert not out.exists()


def test_export_ignores_archive_index_page(tmp_path):
    _write_fixture(tmp_path)
    index = tmp_path / SCRAPS_REL / "archive" / "index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        "---\n"
        "title: English Scraps Archive\n"
        "---\n\n## 字段说明\n\n### helper heading\n\nnot a card\n",
        encoding="utf-8",
    )
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--dry-run", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    # index.md's ### heading must not be parsed as a card
    assert "4 card(s)" in proc.stdout


def test_export_status_rewrite_preserves_crlf(tmp_path):
    path = _write_fixture(tmp_path, crlf=True)
    out = tmp_path / ".anki"
    proc = _run_enu(tmp_path, "export", "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    # newline="" read keeps original endings: assert the whole file stays uniformly
    # CRLF (the rewrite must not introduce LF-only status lines)
    lines = path.read_text(encoding="utf-8", newline="").splitlines(keepends=True)
    assert all(line.endswith("\r\n") for line in lines)
    assert any("- **status**: learning\r\n" in line for line in lines)
