"""Add a new (empty) week to docs/notes/health/data/weight.yml.

Usage:
    uv run poe add-weight-week          # add one empty week
    uv run poe add-weight-week -- 3     # add 3 empty weeks at once
"""

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

import yaml

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.date import parse_date_strict

DATA_PATH = "docs/notes/health/data/weight.yml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Add new week(s) to weight.yml")
    parser.add_argument(
        "count",
        nargs="?",
        type=int,
        default=1,
        help="Number of weeks to add (default: 1)",
    )
    args = parser.parse_args()
    if args.count < 1:
        parser.error("count must be a positive integer (default: 1)")

    filepath = os.path.join(os.getcwd(), DATA_PATH)
    if not os.path.isfile(filepath):
        print(f"Error: {filepath} not found!", file=sys.stderr)
        sys.exit(1)

    # Read raw content for text-level manipulation (preserves comments)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse YAML to get start_date (robust against comment-only matches)
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        print(f"Error: {DATA_PATH} has invalid YAML: {exc}", file=sys.stderr)
        sys.exit(1)
    start_str = data.get("start_date") if isinstance(data, dict) else None

    # Count existing weeks from parsed data (text counting would also match
    # orphan/misplaced `- days:` entries and produce wrong week numbers).
    # NB: an empty `weeks:` key parses to None, so coalesce with `or []`.
    existing = len(data.get("weeks") or []) if isinstance(data, dict) else content.count("- days:")

    # Parse + Monday-align the anchor once (reused for every new week)
    anchor = None
    if start_str:
        anchor = parse_date_strict(str(start_str))
        if anchor is None:
            print(
                f"Error: unparseable start_date {start_str!r} in {DATA_PATH}",
                file=sys.stderr,
            )
            sys.exit(1)
        anchor = anchor - timedelta(days=anchor.weekday())  # align to Monday

    # Build new week entries
    new_entries = []
    for offset in range(1, args.count + 1):
        week_num = existing + offset
        if anchor is not None:
            week_start = anchor + timedelta(weeks=existing + offset - 1)
            date_label = week_start.strftime("%Y-%m-%d")
            new_entries.append(
                f"  # Week {week_num} — Mon {date_label}\n"
                f"  - days: [null, null, null, null, null, null, null]"
            )
        else:
            new_entries.append(
                f"  # Week {week_num}\n  - days: [null, null, null, null, null, null, null]"
            )

    # Append new week entries to the END of the `weeks:` list.
    # NB: must NOT insert before the labels: section — that position is
    # top-level, so the indented `- days:` items end up orphaned right after
    # `start_date:` and break the YAML mapping (ParserError on the site page).
    new_block = "\n".join(new_entries)
    # Locate the `weeks:` key — either at the very start of the file or
    # preceded by a newline (e.g. `\nweeks:` after the labels section)
    idx = 0 if content.startswith("weeks:") else content.rfind("\nweeks:")
    if idx != -1:
        # Find the end of the weeks list: last "- days:" entry after `weeks:`
        last_days = content.rfind("- days:")
        if last_days != -1 and last_days > idx:
            nl = content.find("\n", last_days)
            insert_at = (nl + 1) if nl != -1 else len(content)
        else:
            # weeks: exists but has no entries yet — insert after the key line.
            # NB: search from idx+1 — content[idx] is already the newline
            # BEFORE `weeks:`, so starting at idx would insert before the key.
            nl = content.find("\n", idx + 1)
            insert_at = (nl + 1) if nl != -1 else len(content)
        # Keep the first entry on its own line even when the key line has no
        # trailing newline (hand-crafted files that end right after `weeks:`).
        if insert_at > 0 and content[insert_at - 1] == "\n":
            prefix = ""
        else:
            prefix = "\n"
        content = content[:insert_at] + prefix + new_block + "\n" + content[insert_at:]
    else:
        # No weeks: key at all — append a fresh weeks: block at the end
        content = (
            content.rstrip("\n")
            + "\n\n# 7 days per week; use null for missed days\n"
            + "# Week start dates are shown in comments to help identify each week\n"
            + "weeks:\n"
            + new_block
            + "\n"
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    total = existing + args.count
    print(f"✅ Added {args.count} week(s) — now {total} week(s) in {DATA_PATH}")
    print("   Run `uv run poe server` to preview")


if __name__ == "__main__":
    main()
