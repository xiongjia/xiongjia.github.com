"""Add a scrap to the English Scraps inbox.

Usage:
    uv run poe enu add "cumbersome"
    uv run poe enu add "The implementation is cumbersome to maintain."
    uv run poe enu add "cumbersome" --date 2026-08-08
    uv run python scripts/enu.py add "cumbersome" --dir /tmp/docs   # testing

Appends one line ``YYYY-MM-DD <content>`` to
``docs/notes/research/topics/english/scraps/inbox.md`` (creates the file with
``draft: true`` frontmatter on first use). Pure script — no AI dependency.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.date import parse_date_strict

DOCS_DIR = "docs"
INBOX_REL = Path("notes/research/topics/english/scraps/inbox.md")

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


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="enu",
        description="English Scraps: add a scrap to the scraps inbox.",
    )
    parser.add_argument(
        "action",
        choices=("add",),
        help="add = append one line to the scraps inbox",
    )
    parser.add_argument("content", help="scrap text (word / sentence / question / …)")
    parser.add_argument(
        "--date",
        default=None,
        help="capture date, YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--dir",
        default=DOCS_DIR,
        help=f"docs root (default: {DOCS_DIR})",
    )
    args = parser.parse_args()

    content = " ".join(args.content.split())
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


if __name__ == "__main__":
    raise SystemExit(main())
