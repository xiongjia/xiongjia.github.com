"""Collection Scraps: add / todo / idea.

Usage:
    uv run poe collect-add "A neat CLI tool" --url https://...   # inbox → AI arch
    uv run poe collect-todo "看这个视频"                           # direct to plans.md 📋 TODOs
    uv run poe collect-idea "用 MapLibre 做热力图"                 # direct to plans.md 💡 Ideas
    uv run python scripts/collect.py add "content" --dir /tmp/docs     # testing

``add`` appends to ``docs/notes/collection/scraps/inbox.md`` (needs AI arch).
``todo`` and ``idea`` append directly to ``scraps/plans.md`` (no AI needed).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.date import parse_date_strict  # noqa: E402

DOCS_DIR = "docs"
SCRAPS_REL = Path("notes/collection/scraps")
INBOX_REL = SCRAPS_REL / "inbox.md"

_INBOX_TEMPLATE = """\
---
draft: true
title: Collection Scraps Inbox
---

<!--
Resource collection: poe collect-add "content" (needs AI arch)
TODO: poe collect-todo "content" (direct to plans.md)
Idea: poe collect-idea "content" (direct to plans.md)
-->
"""


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

    # Build line with optional metadata
    parts = [f"{dt.strftime('%Y-%m-%d')}"]
    if args.source:
        parts.append(f"[source: {args.source}]")
    if args.url:
        parts.append(f"[url: {args.url}]")
    parts.append(content)
    line = " ".join(parts) + "\n"

    with inbox.open("a", encoding="utf-8") as f:
        f.write(line)

    print(f"Added: {inbox}")
    print(f"Line:  {line.strip()}")
    return 0


def _ensure_trailing_newline(path: Path) -> None:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            with path.open("a", encoding="utf-8") as f:
                f.write("\n")


def _append_to_plans(plans: Path, section: str, line: str) -> None:
    """Append a line under the given section header in plans.md.

    Creates the section header if it doesn't exist.
    """
    if not plans.exists():
        plans.parent.mkdir(parents=True, exist_ok=True)
        plans.write_text("", encoding="utf-8")

    text = plans.read_text(encoding="utf-8")
    marker = f"### {section}"
    if marker not in text:
        # Append section header at the end
        with plans.open("a", encoding="utf-8") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            if text and not text.endswith("\n\n"):
                f.write("\n")
            f.write(f"{marker}\n\n")
            f.write(f"{line}\n")
    else:
        # Find the section marker, then insert before the next `### ` or EOF
        lines = text.splitlines(keepends=True)
        insert_at = None
        for i, ln in enumerate(lines):
            if ln.strip() == marker:
                # Scan forward past the marker line for the next section
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith("### "):
                        insert_at = j
                        break
                if insert_at is None:
                    insert_at = len(lines)  # no next section → append at end
                break
        if insert_at is not None:
            # Separate from previous content with a blank line (if not already)
            if insert_at > 0 and lines[insert_at - 1].strip() != "":
                lines.insert(insert_at, "\n")
                insert_at += 1
            lines.insert(insert_at, f"{line}\n")
        plans.write_text("".join(lines), encoding="utf-8")


def cmd_todo(args) -> int:
    content = " ".join((args.content or "").split())
    if not content:
        print("Usage: poe collect-todo <text>")
        return 1
    dt = datetime.now()
    plans = Path(args.dir) / SCRAPS_REL / "plans.md"
    _ensure_trailing_newline(plans)
    line = f"- {dt.strftime('%Y-%m-%d')} {content}"
    _append_to_plans(plans, "📋 TODOs", line)
    print(f"TODO added to {plans}")
    print(f"Line: {line}")
    return 0


def cmd_idea(args) -> int:
    content = " ".join((args.content or "").split())
    if not content:
        print("Usage: poe collect-idea <text>")
        return 1
    dt = datetime.now()
    plans = Path(args.dir) / SCRAPS_REL / "plans.md"
    _ensure_trailing_newline(plans)
    line = f"- {dt.strftime('%Y-%m-%d')} {content}"
    _append_to_plans(plans, "💡 Ideas", line)
    print(f"Idea added to {plans}")
    print(f"Line: {line}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="collect",
        description="Collection Scraps: add / todo / idea.",
    )
    sub = parser.add_subparsers(
        dest="action", required=True, help="subcommand (try: collect-add --help)"
    )

    # add → inbox
    add_p = sub.add_parser(
        "add",
        help="Collect a resource → inbox (needs AI arch)",
        description="""
Append to inbox.md. Needs AI arch to classify and append to collection pages.

Examples:
  poe collect-add "A neat CLI tool"
  poe collect-add "Book: ..." --source manual
  poe collect-add "Check out Y" --source HN --url https://...
  poe collect-add "TODO read this" --date 2026-08-01
""",
    )
    add_p.add_argument("content", nargs="?", default=None, help="item text")
    add_p.add_argument("--source", default=None, help="source label (HN, manual, etc.)")
    add_p.add_argument("--url", default=None, help="related URL (link type)")
    add_p.add_argument("--date", default=None, help="capture date, YYYY-MM-DD (default: today)")
    add_p.add_argument("--dir", default=DOCS_DIR, help=f"docs root (default: {DOCS_DIR})")

    # todo → plans.md 📋 TODOs
    todo_p = sub.add_parser(
        "todo",
        help="Add a TODO → plans.md (no AI needed)",
        description="""
Append directly to plans.md under 📋 TODOs section.

Examples:
  poe collect-todo "看这个视频"
  poe collect-todo "研究一下 XX 的源码"
""",
    )
    todo_p.add_argument("content", nargs="?", default=None, help="TODO text")
    todo_p.add_argument("--dir", default=DOCS_DIR, help=f"docs root (default: {DOCS_DIR})")

    # idea → plans.md 💡 Ideas
    idea_p = sub.add_parser(
        "idea",
        help="Add an idea → plans.md (no AI needed)",
        description="""
Append directly to plans.md under 💡 Ideas section.

Examples:
  poe collect-idea "用 MapLibre 做热力图"
  poe collect-idea "做一个 CLI 番茄钟"
""",
    )
    idea_p.add_argument("content", nargs="?", default=None, help="idea text")
    idea_p.add_argument("--dir", default=DOCS_DIR, help=f"docs root (default: {DOCS_DIR})")

    args = parser.parse_args()

    if args.action == "add":
        return cmd_add(add_p, args)
    elif args.action == "todo":
        return cmd_todo(args)
    elif args.action == "idea":
        return cmd_idea(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
