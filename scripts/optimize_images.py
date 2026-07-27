"""Optimise images by converting PNG/JPG/JPEG to WebP.

Converts specified image(s) to WebP (quality=85), updates .md references
to point to the new .webp files. Originals are left untouched.

Usage:
    uv run poe optimize-images docs/path/to/img.png
    uv run poe optimize-images img1.png img2.jpg
    uv run poe optimize-images --all          # process everything under docs/
"""

import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path

from PIL import Image

DOCS = Path("docs")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
WEBP_QUALITY = 85


def iter_images(root: Path) -> Iterator[Path]:
    """Yield all image files under *root* matching IMAGE_EXTENSIONS."""
    for path in root.rglob("*"):
        if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file():
            yield path


def convert_to_webp(src: Path) -> Path | None:
    """Convert a single image to WebP.

    Returns the path to the new .webp file, or None if the WebP already exists
    and is not smaller.
    """
    dst = src.with_suffix(".webp")
    if dst.exists() and dst.stat().st_size <= src.stat().st_size:
        print(f"  [SKIP] {src} -> {dst} (already exists and not larger)")
        return None

    try:
        with Image.open(src) as im:
            im.save(dst, "WEBP", quality=WEBP_QUALITY, method=6)
    except Exception as exc:
        print(f"  [SKIP] {src}: {exc}")
        return None

    ratio = dst.stat().st_size / src.stat().st_size
    print(f"  {src} -> {dst} ({ratio:.0%})")
    return dst


def update_md_references(src: Path, dst: Path) -> None:
    """Replace references to *src* with *dst* in all .md files under docs/."""
    src_str = str(src.as_posix())
    dst_str = str(dst.as_posix())
    rel_variants = {src_str, src_str.lstrip("/")}

    for md_file in DOCS.rglob("*.md"):
        original = md_file.read_text(encoding="utf-8")
        changed = original

        for old in rel_variants:
            # Markdown: ![alt](path) or ![alt](path "title")
            changed = re.sub(
                rf'(!\[.*?\]\s*\(\s*){re.escape(old)}\s*(".*?")?\s*\)',
                rf'\1{dst_str}\2)',
                changed,
            )
            # HTML: <img ... src="path" ...>
            changed = re.sub(
                rf'(<img\s[^>]*?src\s*=\s*["\']){re.escape(old)}(["\'][^>]*?/?>)',
                rf'\1{dst_str}\2',
                changed,
            )

        if changed != original:
            md_file.write_text(changed, encoding="utf-8")
            print(f"  [UPDATE] {md_file}")




def resolve_paths(args: list[str]) -> list[Path]:
    """Resolve command-line args to image paths."""
    paths: list[Path] = []
    for raw in args:
        p = Path(raw)
        if not p.exists():
            print(f"  [WARN]  path not found: {raw}", file=sys.stderr)
            continue
        if p.is_dir():
            paths.extend(iter_images(p))
        elif p.suffix.lower() in IMAGE_EXTENSIONS:
            paths.append(p)
        else:
            print(f"  [WARN]  unsupported image type: {p.suffix} ({raw})", file=sys.stderr)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert PNG/JPG/JPEG images to WebP and update .md references.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process ALL images under docs/ (default: only specified paths)",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="IMAGE",
        help="One or more image files or directories to process",
    )
    args = parser.parse_args()

    if args.all:
        images = list(iter_images(DOCS))
    elif args.paths:
        images = resolve_paths(args.paths)
    else:
        parser.print_help()
        print("\nError: specify at least one image path, or use --all")
        sys.exit(1)

    if not images:
        print("No matching images found.")
        sys.exit(0)

    print(f"Found {len(images)} image(s)\n")

    converted = 0
    for img in images:
        dst = convert_to_webp(img)
        if dst is not None:
            update_md_references(img, dst)
            converted += 1

    print(f"\nDone — {converted} image(s) converted to WebP")


if __name__ == "__main__":
    main()
