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

    filepath = os.path.join(os.getcwd(), DATA_PATH)
    if not os.path.isfile(filepath):
        print(f"Error: {filepath} not found!", file=sys.stderr)
        sys.exit(1)

    # Read raw content for text-level manipulation (preserves comments)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse YAML to get start_date (robust against comment-only matches)
    data = yaml.safe_load(content)
    start_str = data.get("start_date") if isinstance(data, dict) else None

    # Count existing weeks
    existing = content.count("- days:")

    # Build new week entries
    new_entries = []
    for offset in range(1, args.count + 1):
        week_num = existing + offset
        if start_str:
            start = parse_date_strict(str(start_str))
            if start is None:
                print(
                    f"Error: unparseable start_date {start_str!r} in {DATA_PATH}",
                    file=sys.stderr,
                )
                sys.exit(1)
            start = start - timedelta(days=start.weekday())  # align to Monday
            week_start = start + timedelta(weeks=existing + offset - 1)
            date_label = week_start.strftime("%Y-%m-%d")
            new_entries.append(
                f"  # Week {week_num} — Mon {date_label}\n"
                f"  - days: [null, null, null, null, null, null, null]"
            )
        else:
            new_entries.append(
                f"  # Week {week_num}\n  - days: [null, null, null, null, null, null, null]"
            )

    # Insert before the labels: section (if it exists) or append at end
    labels_marker = "\n# Display labels (i18n)"
    if labels_marker in content:
        content = content.replace(
            labels_marker,
            "\n".join(new_entries) + "\n" + labels_marker,
            1,
        )
    else:
        content = content.rstrip("\n") + "\n" + "\n".join(new_entries) + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    total = existing + args.count
    print(f"✅ Added {args.count} week(s) — now {total} week(s) in {DATA_PATH}")
    print("   Run `uv run poe server` to preview")


if __name__ == "__main__":
    main()
