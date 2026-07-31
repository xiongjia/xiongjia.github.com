"""Create a new Moment entry.

Usage:
    uv run python scripts/create_moment.py "Content text"
    uv run python scripts/create_moment.py "Content text" --image photo.jpg
    uv run python scripts/create_moment.py "Content text" --slug my-slug
    uv run python scripts/create_moment.py "Content text" --time "9am"
    uv run python scripts/create_moment.py "Content text" --time "yesterday 9am"
    uv run python scripts/create_moment.py "Content text" --time "30 9pm"
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.date import parse_datetime_arg

EDITOR = os.environ.get("EDITOR", "vim")


def main():
    parser = argparse.ArgumentParser(description="Create a new Moment")
    parser.add_argument("content", nargs="?", help="Moment content (opens editor if empty)")
    parser.add_argument("--image", help="Reference an existing image path")
    parser.add_argument("--slug", help="Custom slug for the filename")
    parser.add_argument(
        "--time",
        help=(
            "Publish date/time (default: now). Examples: 9am, 21:30, "
            "yesterday 9am, 30 9pm, 2026-07-30 21:36"
        ),
    )
    parser.add_argument(
        "--dir", default="docs/moments", help="Moment data directory (default: docs/moments)"
    )
    args = parser.parse_args()

    dt = parse_datetime_arg(args.time)
    month_dir = dt.strftime("%Y-%m")
    time_slug = dt.strftime("%d-%H%M")
    filename = f"{time_slug}{'-' + args.slug if args.slug else ''}.md"

    full_dir = os.path.join(args.dir, month_dir)
    os.makedirs(full_dir, exist_ok=True)

    filepath = os.path.join(full_dir, filename)

    lines = [
        "---",
        f"date: {dt.strftime('%Y-%m-%d %H:%M')}",
        "tags:",
        "  - general",
        "---",
        "",
    ]
    if args.content:
        lines.append(args.content)
    if args.image:
        lines.append("")
        lines.append(f"![Image](./{args.image})")
    lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    if not args.content:
        ret = subprocess.call([EDITOR, filepath])
        if ret != 0:
            print(f"Warning: editor exited with code {ret}")

    print(f"Created: {filepath}")
    print("Preview: uv run poe server  →  http://localhost:8000/moment/")


if __name__ == "__main__":
    main()
