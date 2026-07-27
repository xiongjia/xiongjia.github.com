"""Optimise images by converting PNG/JPG/JPEG to WebP.

Converts specified image(s) to WebP (quality=85), updates .md references
to point to the new .webp files. Originals are left untouched.

Usage:
    uv run poe optimize-images docs/path/to/img.png
    uv run poe optimize-images img1.png img2.jpg
    uv run poe optimize-images --all          # process everything under docs/
    uv run poe optimize-images --dry-run docs/path/to/img.png   # preview only
"""

import argparse
import os
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


def convert_to_webp(src: Path, *, dry_run: bool = False) -> Path | None:
    """Convert a single image to WebP.

    Returns the path to the new .webp file, or None if the WebP already exists
    and is not smaller.
    """
    dst = src.with_suffix(".webp")
    if dst.exists() and dst.stat().st_size <= src.stat().st_size:
        print(f"  [SKIP] {src} -> {dst} (already exists and not larger)")
        return None

    if dry_run:
        print(f"  [DRY-RUN] would convert {src} -> {dst}")
        return dst

    try:
        with Image.open(src) as im:
            exif = im.info.get("exif")
            save_kwargs: dict = {"quality": WEBP_QUALITY, "method": 6}
            if exif is not None:
                save_kwargs["exif"] = exif
            im.save(dst, "WEBP", **save_kwargs)
    except Exception as exc:
        print(f"  [SKIP] {src}: {exc}")
        return None

    ratio = dst.stat().st_size / src.stat().st_size
    print(f"  {src} -> {dst} ({ratio:.0%})")
    return dst


def _path_variants_for_md(src: Path, md_file: Path) -> set[str]:
    """Return a set of path strings that could reference *src* from *md_file*.

    Tries:
      - absolute-from-root:  docs/assets/foo.png
      - root-relative:       /docs/assets/foo.png  (handled by lstrip below)
      - relative from .md's own directory: e.g. ../assets/foo.png
    """
    src_str = str(src.as_posix())
    variants = {src_str, src_str.lstrip("/")}

    # Relative path from the .md file's directory to the image
    try:
        rel = Path(os.path.relpath(src, md_file.parent)).as_posix()
        variants.add(rel)
    except ValueError:
        pass  # different drives on Windows – ignore

    return variants


def update_md_references(src: Path, dst: Path, *, dry_run: bool = False) -> None:
    """Replace references to *src* with *dst* in all .md files under docs/."""
    for md_file in DOCS.rglob("*.md"):
        original = md_file.read_text(encoding="utf-8")
        changed = original

        # Compute the correct relative path from this .md file to the destination
        try:
            rel_dst = Path(os.path.relpath(dst, md_file.parent)).as_posix()
        except ValueError:
            rel_dst = str(dst.as_posix())  # fallback (different drive on Windows)

        for old in _path_variants_for_md(src, md_file):
            # Markdown: ![alt](path) or ![alt](path "title")
            changed = re.sub(
                rf'(!\[.*?\]\s*\(\s*){re.escape(old)}\s*(".*?")?\s*\)',
                rf'\1{rel_dst}\2)',
                changed,
            )
            # HTML: <img ... src="path" ...>
            changed = re.sub(
                rf'(<img\s[^>]*?src\s*=\s*["\']){re.escape(old)}(["\'][^>]*?/?>)',
                rf'\1{rel_dst}\2',
                changed,
            )

        if changed != original:
            if dry_run:
                print(f"  [DRY-RUN] would update {md_file}")
            else:
                md_file.write_text(changed, encoding="utf-8")
                print(f"  [UPDATE] {md_file}")


def resolve_paths(args: list[str]) -> tuple[list[Path], bool]:
    """Resolve command-line args to image paths. Returns (paths, has_errors)."""
    paths: list[Path] = []
    has_errors = False
    for raw in args:
        p = Path(raw)
        if not p.exists():
            print(f"  [WARN]  path not found: {raw}", file=sys.stderr)
            has_errors = True
            continue
        if p.is_dir():
            paths.extend(iter_images(p))
        elif p.suffix.lower() in IMAGE_EXTENSIONS:
            paths.append(p)
        else:
            print(f"  [WARN]  unsupported image type: {p.suffix} ({raw})", file=sys.stderr)
            has_errors = True
    return paths, has_errors


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
        "--dry-run",
        action="store_true",
        help="Preview changes without writing anything",
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
        images, has_errors = resolve_paths(args.paths)
    else:
        parser.print_help()
        print("\nError: specify at least one image path, or use --all")
        sys.exit(1)

    if not images:
        print("No matching images found.")
        sys.exit(1 if has_errors else 0)

    print(f"Found {len(images)} image(s){' (dry-run)' if args.dry_run else ''}\n")

    converted = 0
    for img in images:
        dst = convert_to_webp(img, dry_run=args.dry_run)
        if dst is not None:
            update_md_references(img, dst, dry_run=args.dry_run)
            converted += 1

    suffix = " (dry-run, no changes written)" if args.dry_run else ""
    print(f"\nDone — {converted} image(s) converted to WebP{suffix}")


if __name__ == "__main__":
    main()
