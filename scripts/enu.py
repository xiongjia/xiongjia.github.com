"""English Scraps: add scraps to the inbox / export archived cards to Anki.

Usage:
    uv run poe enu add "cumbersome"
    uv run poe enu add "cumbersome" --date 2026-08-08
    uv run poe enu export                    # .apkg for all status:new cards
    uv run poe enu export --format csv       # CSV fallback (UTF-8 BOM, one file per type)
    uv run poe enu export --type word --tag technical
    uv run poe enu export --all --dry-run    # generate without status rewrite
    uv run python scripts/enu.py add "cumbersome" --dir /tmp/docs     # testing
    uv run python scripts/enu.py export --dir /tmp/docs --out /tmp/.anki --dry-run

``add`` appends one line ``YYYY-MM-DD <content>`` to
``docs/notes/research/topics/english/scraps/inbox.md`` (creates the file with
``draft: true`` frontmatter on first use).

``export`` parses all ``scraps/archive/<YYYY-www>.md`` week files into cards
(``### <title>`` blocks with ``- **field**: value`` bullets), filters them
(default: ``status: new``, unless ``--all`` / ``--type`` / ``--tag``), builds
one Anki note type per card type with 2 card templates (识别卡 + 产出卡), and
writes ``.anki/english-scraps-<date>.apkg`` (or CSV fallback) — then rewrites
the exported cards' ``status: new`` → ``status: learning`` in the week files
(unless ``--dry-run``). Pure scripts — no AI dependency. Import is manual
(double-click the apkg in Anki desktop / open it with AnkiDroid, then sync via
AnkiWeb); no AnkiConnect automation.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.date import parse_date_strict  # noqa: E402

DOCS_DIR = "docs"
SCRAPS_REL = Path("notes/research/topics/english/scraps")
INBOX_REL = SCRAPS_REL / "inbox.md"
ARCHIVE_GLOB = SCRAPS_REL / "archive" / "*.md"

_INBOX_TEMPLATE = """\
---
draft: true
title: English Scraps Inbox
---

<!--
追加即记；一行一条，日期前缀便于排序；AI 自动分类，无需写类型前缀。

推荐用命令追加（自动带日期）：uv run poe enu add "内容"
或 pi 里 /skill:enu-organize add <内容>。手动编辑示例：
2026-08-08 cumbersome
2026-08-08 The implementation is cumbersome to maintain.
-->
"""

# Anki note-type field list per card type (field order = note field order)
_ANKI_FIELDS = {
    "word": [
        "term",
        "ipa",
        "meaning_cn",
        "meaning_en",
        "memory",
        "context",
        "original",
        "own_sentence",
        "synonyms",
    ],
    "phrasal-verb": ["term", "meaning_cn", "example", "replacement", "contrast", "source"],
    "collocation": ["term", "meaning_cn", "example", "replacement", "contrast", "source"],
    "idiom": ["term", "meaning_cn", "example", "replacement", "contrast", "source"],
    "grammar": ["example", "rule", "pitfall", "contrast"],
    "sentence": ["original", "translation", "breakdown", "imitation"],
}

# shared read-only mapping reused by the three phrase types (do not mutate)
_PHRASE_ALIASES = {
    "含义": "meaning_cn",
    "例句": "example",
    "替换": "replacement",
    "易混": "contrast",
    "对比": "contrast",
}

# archive md field key → Anki field name (per card type; `term` comes from the ### title)
_ALIASES = {
    "word": {
        "发音": "ipa",
        "含义": "meaning_cn",
        "英义": "meaning_en",
        "记忆": "memory",
        "语境": "context",
        "原句": "original",
        "造句": "own_sentence",
        "同义/反义": "synonyms",
    },
    "phrasal-verb": _PHRASE_ALIASES,
    "collocation": _PHRASE_ALIASES,
    "idiom": _PHRASE_ALIASES,
    "grammar": {"例句": "example", "规则": "rule", "易错点": "pitfall", "对比": "contrast"},
    "sentence": {
        "原句": "original",
        "翻译": "translation",
        "结构拆解": "breakdown",
        "仿写": "imitation",
    },
}

_CSS = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Microsoft YaHei', sans-serif;
  font-size: 1.05em;
  line-height: 1.55;
}
.mobile .card { font-size: 1em; }
"""


def _sec(label: str, field_name: str) -> str:
    """Conditional back-section ``{{#field}}<b>label</b>: {{field}}<br>{{/field}}``."""
    return (
        "{{#" + field_name + "}}<b>" + label + "</b>: {{" + field_name + "}}"
        "<br>{{/" + field_name + "}}"
    )


_AFMT_WORD = (
    "{{#meaning_cn}}<b>含义</b>: {{meaning_cn}}<br>{{/meaning_cn}}"
    + _sec("英义", "meaning_en")
    + _sec("记忆", "memory")
    + _sec("语境", "context")
    + _sec("原句", "original")
    + _sec("造句", "own_sentence")
    + _sec("同义/反义", "synonyms")
)
_AFMT_PHRASE = (
    "{{#meaning_cn}}<b>含义</b>: {{meaning_cn}}<br>{{/meaning_cn}}"
    + _sec("例句", "example")
    + _sec("替换", "replacement")
    + _sec("易混/对比", "contrast")
    + _sec("来源", "source")
)
_AFMT_GRAMMAR = (
    "{{#rule}}<b>规则</b>: {{rule}}<br>{{/rule}}"
    + _sec("易错点", "pitfall")
    + _sec("对比", "contrast")
)
_AFMT_SENTENCE = (
    "{{#translation}}<b>翻译</b>: {{translation}}<br>{{/translation}}"
    + _sec("结构拆解", "breakdown")
    + _sec("仿写", "imitation")
)

_FRONT_TERM_IPA = "{{term}}{{#ipa}}<br><span style='color:#888'>{{ipa}}</span>{{/ipa}}"
_BACK_WORD_PROD = _FRONT_TERM_IPA + "{{#memory}}<br><i>{{memory}}</i>{{/memory}}"
_BACK_PHRASE_PROD = (
    "{{term}}{{#example}}<br><b>例句</b>: {{example}}{{/example}}"
    "{{#replacement}}<br><b>替换</b>: {{replacement}}{{/replacement}}"
)
_BACK_COLLOC_PROD = (
    "{{term}}{{#example}}<br><b>例句</b>: {{example}}{{/example}}"
    "{{#contrast}}<br><b>易混/对比</b>: {{contrast}}{{/contrast}}"
)
_BACK_IDIOM_PROD = (
    "{{term}}{{#example}}<br><b>例句</b>: {{example}}{{/example}}"
    "{{#source}}<br><b>来源</b>: {{source}}{{/source}}"
)
_BACK_GRAMMAR_PROD = "{{example}}{{#pitfall}}<br><b>易错点</b>: {{pitfall}}{{/pitfall}}"
_BACK_SENTENCE_PROD = "{{original}}{{#breakdown}}<br><b>结构拆解</b>: {{breakdown}}{{/breakdown}}"

_TEMPLATES = {
    "word": {
        "recog": {"front": _FRONT_TERM_IPA, "back": _AFMT_WORD},
        "prod": {"front": "{{meaning_cn}}", "back": _BACK_WORD_PROD},
    },
    "phrasal-verb": {
        "recog": {"front": "{{term}}", "back": _AFMT_PHRASE},
        "prod": {"front": "{{meaning_cn}}", "back": _BACK_PHRASE_PROD},
    },
    "collocation": {
        "recog": {"front": "{{term}}", "back": _AFMT_PHRASE},
        "prod": {"front": "{{meaning_cn}}", "back": _BACK_COLLOC_PROD},
    },
    "idiom": {
        "recog": {"front": "{{term}}", "back": _AFMT_PHRASE},
        "prod": {"front": "{{meaning_cn}}", "back": _BACK_IDIOM_PROD},
    },
    "grammar": {
        "recog": {"front": "{{#example}}{{example}}{{/example}}", "back": _AFMT_GRAMMAR},
        "prod": {"front": "{{#rule}}{{rule}}{{/rule}}", "back": _BACK_GRAMMAR_PROD},
    },
    "sentence": {
        "recog": {"front": "{{original}}", "back": _AFMT_SENTENCE},
        "prod": {
            "front": "{{#translation}}{{translation}}{{/translation}}",
            "back": _BACK_SENTENCE_PROD,
        },
    },
}

_BULLET_RE = re.compile(r"^- \*\*(.+?)\*\*\s*[:：]\s?(.*)$")


@dataclass
class Card:
    """One archived card (a ``### <title>`` block in a week file)."""

    title: str
    block_type: str = ""
    date: str = ""
    source: str = ""
    status: str = "new"
    tags: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    source_file: Path | None = None
    start_line: int = 0  # index of the ``### `` line
    end_line: int = 0  # index of the next ``### `` line (or EOF)
    last_key: str = ""  # current bullet key, for continuation lines


def parse_archive_files(docs_root: Path) -> tuple[list[Card], list[tuple[Path, str]]]:
    """Parse every ``scraps/archive/*.md`` week file → (cards, warnings)."""
    cards: list[Card] = []
    warnings: list[tuple[Path, str]] = []
    for path in sorted(docs_root.glob(str(ARCHIVE_GLOB))):
        if path.name == "index.md":  # archive index page is not a week file
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        current: Card | None = None
        for idx, line in enumerate(lines):
            if line.startswith("### "):
                if current is not None:
                    current.end_line = idx
                    _finalize(current, path, cards, warnings)
                current = Card(title=line[4:].strip(), source_file=path, start_line=idx)
            elif current is not None:
                m = _BULLET_RE.match(line)
                if m:
                    key = m.group(1).strip()
                    current.fields[key] = m.group(2).strip()
                    current.last_key = key
                elif line.strip() and current.last_key:
                    current.fields[current.last_key] += "\n" + line.strip()
        if current is not None:
            current.end_line = len(lines)
            _finalize(current, path, cards, warnings)
    return cards, warnings


def _finalize(card: Card, path: Path, cards: list[Card], warnings: list[tuple[Path, str]]) -> None:
    card.block_type = card.fields.pop("type", "").strip().lower()
    card.date = card.fields.pop("date", "").strip()
    card.source = card.fields.pop("source", "").strip()
    card.status = card.fields.pop("status", "new").strip().lower()
    raw_tags = card.fields.pop("tags", "")
    card.tags = [t.strip().lower() for t in re.findall(r"[^\[\],\s]+", raw_tags)]
    if not card.block_type:
        warnings.append((path, f"card without type, skipped: {card.title[:40]}"))
    elif card.block_type not in _ANKI_FIELDS and card.block_type != "misc":
        warnings.append((path, f"unknown type {card.block_type!r}, skipped: {card.title[:40]}"))
    else:
        cards.append(card)


def select_cards(cards: list[Card], args) -> tuple[list[Card], int]:
    """Apply status / type / tag filters; misc is never exportable."""
    selected: list[Card] = []
    skipped_misc = 0
    for c in cards:
        if c.block_type == "misc":
            skipped_misc += 1
            continue
        if args.type and c.block_type != args.type:
            continue
        if args.tag and args.tag.lower() not in c.tags:
            continue
        if not args.all and c.status != "new":
            continue
        selected.append(c)
    return selected, skipped_misc


def dedup_key(card: Card) -> str:
    """``type:normalized-key`` (sentence cards key on the full original sentence)."""
    if card.block_type == "sentence":
        raw = card.fields.get("原句") or card.title
    else:
        raw = card.title
    norm = re.sub(r"\s+", "-", raw.strip().lower())
    return f"{card.block_type}:{norm}"


def stable_guid(key: str) -> str:
    """Deterministic Anki note guid (alphanumeric, stable across exports)."""
    digest = hashlib.sha1(key.encode("utf-8")).digest()
    return base64.b32encode(digest[:8]).decode().rstrip("=").lower()[:10]


def stable_id(seed: str) -> int:
    """Deterministic positive int (used for Anki deck / model ids)."""
    return int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8], 16)


def _note_fields(card: Card) -> list[str]:
    """Map a card's md fields onto its Anki note-type field list (in order)."""
    aliases = _ALIASES.get(card.block_type, {})
    out: list[str] = []
    for f in _ANKI_FIELDS[card.block_type]:
        if f == "term":
            out.append(card.title)
        else:
            val = ""
            for k, v in aliases.items():
                if v == f and k in card.fields:
                    val = card.fields[k]
                    break
            out.append(val)
    return out


def _make_model(block_type: str):
    import genanki

    t = _TEMPLATES[block_type]
    return genanki.Model(
        stable_id(f"enu-model-{block_type}"),
        f"English Scraps: {block_type}",
        fields=[{"name": f} for f in _ANKI_FIELDS[block_type]],
        templates=[
            {"name": "识别卡", "qfmt": t["recog"]["front"], "afmt": t["recog"]["back"]},
            {"name": "产出卡", "qfmt": t["prod"]["front"], "afmt": t["prod"]["back"]},
        ],
        css=_CSS,
    )


def build_apkg(cards: list[Card], out_path: Path) -> None:
    import genanki

    deck = genanki.Deck(stable_id("enu-scraps-deck"), "English Scraps")
    for c in cards:
        deck.add_note(
            genanki.Note(
                model=_make_model(c.block_type),
                fields=_note_fields(c),
                tags=c.tags,
                guid=stable_guid(dedup_key(c)),
            )
        )
    genanki.Package(deck).write_to_file(str(out_path))


def write_csv(out_dir: Path, cards: list[Card]) -> list[Path]:
    """CSV fallback: one UTF-8-BOM file per type, first field = dedup key."""
    by_type: dict[str, list[Card]] = {}
    for c in cards:
        by_type.setdefault(c.block_type, []).append(c)
    written: list[Path] = []
    for t, cs in sorted(by_type.items()):
        path = out_dir / f"{t}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["key"] + _ANKI_FIELDS[t])
            for c in cs:
                w.writerow([dedup_key(c)] + _note_fields(c))
        written.append(path)
    return written


def rewrite_status(path: Path, cards: list[Card]) -> int:
    """Rewrite exported cards' ``status: new`` → ``status: learning`` in the file."""
    # newline="" keeps original line endings (CRLF vs LF) so we can preserve them
    lines = path.read_text(encoding="utf-8", newline="").splitlines(keepends=True)
    changed = 0
    for c in cards:
        if c.status != "new":
            continue
        for idx in range(c.start_line, min(c.end_line, len(lines))):
            if re.match(r"^- \*\*status\*\*:\s*new\s*$", lines[idx]):
                if lines[idx].endswith("\r\n"):
                    nl = "\r\n"
                elif lines[idx].endswith("\n"):
                    nl = "\n"
                else:
                    nl = ""
                lines[idx] = f"- **status**: learning{nl}"
                changed += 1
                break
    if changed:
        path.write_text("".join(lines), encoding="utf-8", newline="")
    return changed


def cmd_add(parser: argparse.ArgumentParser, args) -> int:
    content = " ".join((args.content or "").split())
    if not content:
        parser.error("content must not be empty")
    if args.date:
        dt = parse_date_strict(args.date)
        if dt is None:
            parser.error(f"invalid --date {args.date!r} (expected YYYY-MM-DD)")
    else:
        dt = datetime.now()

    inbox = Path(args.dir) / INBOX_REL
    if not inbox.exists():
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(_INBOX_TEMPLATE, encoding="utf-8")
    else:
        existing = inbox.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            with inbox.open("a", encoding="utf-8") as f:
                f.write("\n")

    line = f"{dt.strftime('%Y-%m-%d')} {content}\n"
    with inbox.open("a", encoding="utf-8") as f:
        f.write(line)

    print(f"Added: {inbox}")
    print(f"Line:  {line.strip()}")
    return 0


def cmd_export(args) -> int:
    cards, warnings = parse_archive_files(Path(args.dir))
    selected, skipped_misc = select_cards(cards, args)
    if not selected:
        if args.type == "misc":
            print("misc cards have no Anki template — nothing to export.")
        else:
            print("No cards to export.")
        return 0

    out_dir = Path(args.out) if args.out else Path(".anki")
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    if args.format == "csv":
        written = write_csv(out_dir, selected)
        print(f"CSV written: {len(written)} file(s) in {out_dir}")
    else:
        apkg_path = out_dir / f"english-scraps-{today}.apkg"
        try:
            build_apkg(selected, apkg_path)
        except ImportError:
            print("genanki not installed — run `uv add genanki`", file=sys.stderr)
            return 1
        print(f"APKG written: {apkg_path}")

    counts = Counter(c.block_type for c in selected)
    detail = ", ".join(f"{t} × {n}" for t, n in counts.items())
    print(f"Exported {len(selected)} card(s): {detail}")
    if skipped_misc:
        print(f"Skipped: {skipped_misc} misc (no Anki template)")

    if args.dry_run:
        print("Dry run — status not rewritten.")
    else:
        by_file: dict[Path, list[Card]] = {}
        for c in selected:
            by_file.setdefault(c.source_file, []).append(c)
        updated = sum(rewrite_status(path, cs) for path, cs in sorted(by_file.items()))
        print(f"Status updated: {updated} card(s) new → learning")

    for wpath, msg in warnings:
        print(f"WARN {wpath.name}: {msg}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="enu",
        description="English Scraps: add a scrap to the inbox, or export archived cards to Anki.",
    )
    parser.add_argument(
        "action",
        choices=("add", "export"),
        help="add = append to inbox; export = build Anki cards from archive",
    )
    parser.add_argument("content", nargs="?", default=None, help="scrap text (add only)")
    parser.add_argument(
        "--date",
        default=None,
        help="capture date, YYYY-MM-DD (add; default: today)",
    )
    parser.add_argument(
        "--dir",
        default=DOCS_DIR,
        help=f"docs root (default: {DOCS_DIR})",
    )
    parser.add_argument(
        "--format",
        choices=("apkg", "csv"),
        default="apkg",
        dest="format",
        help="export format (default: apkg)",
    )
    parser.add_argument(
        "--type",
        default=None,
        help="export only this card type "
        "(word / phrasal-verb / collocation / idiom / grammar / sentence)",
    )
    parser.add_argument("--tag", default=None, help="export only cards with this tag")
    parser.add_argument(
        "--all",
        action="store_true",
        help="export cards of any status (default: only status:new)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="generate files but do not rewrite status",
    )
    parser.add_argument("--out", default=None, help="export output dir (default: .anki)")
    args = parser.parse_args()

    if args.action == "add":
        return cmd_add(parser, args)
    return cmd_export(args)


if __name__ == "__main__":
    raise SystemExit(main())
