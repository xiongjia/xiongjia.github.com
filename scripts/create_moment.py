"""Create a new Moment entry.

Usage:
    uv run python scripts/create_moment.py "Content text"
    uv run python scripts/create_moment.py "Content text" --image photo.jpg
    uv run python scripts/create_moment.py "Content text" --slug my-slug
    uv run python scripts/create_moment.py "Content text" --draft
    uv run python scripts/create_moment.py "Content text" --time "9am"
    uv run python scripts/create_moment.py "Content text" --time "yesterday 9am"
    uv run python scripts/create_moment.py "Content text" --time "30 9pm"
    uv run python scripts/create_moment.py "Content text" --meta name="La Mian" --meta rating=4
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.date import parse_datetime_arg
from shared.gcj02 import gcj02_to_wgs84

EDITOR = os.environ.get("EDITOR", "vim")


def _meta_value(v: str) -> str:
    """Format a ``--meta`` value for the YAML frontmatter.

    Plain integer strings stay bare (``rating: 4`` → int in YAML); anything
    else is double-quoted via JSON so special characters (``:``, ``#``,
    quotes, leading/trailing spaces) can never break the frontmatter.
    """
    try:
        int(v)
    except ValueError:
        return json.dumps(v, ensure_ascii=False)
    return v


def main():
    parser = argparse.ArgumentParser(description="Create a new Moment")
    parser.add_argument("content", nargs="?", help="Moment content (opens editor if empty)")
    parser.add_argument("--image", help="Reference an existing image path")
    parser.add_argument("--slug", help="Custom slug for the filename")
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Mark as draft (hidden in production builds, kept in dev)",
    )
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
    parser.add_argument("--place", help="Location display text (e.g. 徐汇滨江某咖啡店)")
    parser.add_argument("--lng", type=float, help="Longitude (coordinate system per --crs)")
    parser.add_argument("--lat", type=float, help="Latitude (coordinate system per --crs)")
    parser.add_argument(
        "--crs",
        choices=["wgs84", "gcj02"],
        default="wgs84",
        help=(
            "Coordinate system of --lng/--lat: wgs84 (default) or gcj02 "
            "(Amap/Baidu; converted to WGS-84 before saving)"
        ),
    )
    parser.add_argument("--region", help="Map region (e.g. shanghai); auto-probed when omitted")
    parser.add_argument(
        "--meta",
        action="append",
        metavar="KEY=VALUE",
        help=(
            'Metadata key/value (repeatable), e.g. --meta name="La Mian" --meta rating=4; '
            "rendered per extra.moment.meta_fields in mkdocs.yml"
        ),
    )
    args = parser.parse_args()

    if (args.lng is None) != (args.lat is None):
        parser.error("--lng and --lat must be given together")

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
    ]
    if args.draft:
        lines.append("draft: true")
    if args.place:
        lines.append(f"place: {args.place}")
    if args.lng is not None:
        lng, lat = args.lng, args.lat
        if args.crs == "gcj02":
            lng, lat = gcj02_to_wgs84(lng, lat)
            print(f"GCJ-02 -> WGS-84: {args.lng},{args.lat} -> {lng:.6f},{lat:.6f}")
        lines.append(f"lng: {lng:.6f}")
        lines.append(f"lat: {lat:.6f}")
    if args.region:
        lines.append(f"region: {args.region}")
    if args.meta:
        meta = {}
        for item in args.meta:
            if "=" not in item:
                parser.error(f"--meta expects KEY=VALUE, got {item!r}")
            k, v = item.split("=", 1)
            key = k.strip()
            # CLI duplicates: last value wins (override semantics) — note this
            # is the opposite of extra.moment.meta_fields config dedupe, which
            # keeps the FIRST definition (typo protection)
            if key in meta:
                print(
                    f"Warning: duplicate --meta key {key!r} — keeping the last value",
                    file=sys.stderr,
                )
            meta[key] = _meta_value(v)
        lines.append("meta:")
        for k, v in meta.items():
            lines.append(f"  {k}: {v}")
    lines += ["---", ""]
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
