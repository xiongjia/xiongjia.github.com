"""Optimise images by converting PNG/JPG/JPEG to WebP.

Converts specified image(s) to WebP and updates .md references to point to
the new .webp files. Originals are left untouched.

WebP quality resolution: ``--quality`` CLI arg > ``extra.optimize_images.quality``
in mkdocs.yml > default 85. Out-of-range values are clamped to 1-100.
Optional long-edge scaling: ``--max-dimension`` CLI arg >
``extra.optimize_images.max_dimension`` in mkdocs.yml > off (opt-in).

Usage:
    uv run poe optimize-images docs/path/to/img.png
    uv run poe optimize-images img1.png img2.jpg --quality 80
    uv run poe optimize-images --all --max-dimension 2000
    uv run poe optimize-images --all          # process everything under docs/
    uv run poe optimize-images --dry-run docs/path/to/img.png   # preview only
"""

import argparse
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

from PIL import Image, ImageOps

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.mkdocs_yaml import load_extra

DOCS = Path("docs")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
# WebP defaults: q85 is visually near-lossless for photos while much smaller
# than q90; the long-edge cap is OPT-IN (None = no scaling).
DEFAULT_WEBP_QUALITY = 85
DEFAULT_MAX_DIMENSION: int | None = None


def config_quality() -> int | None:
    """Read ``extra.optimize_images.quality`` from mkdocs.yml (None when absent/invalid).

    Accepts ints and numeric strings (e.g. an ``!ENV`` default); other values
    — including ``true``, which is a bool subclass of int — are rejected with
    a warning.
    """
    quality = load_extra("optimize_images", label="optimize-images").get("quality")
    if type(quality) is int:
        return quality
    if isinstance(quality, str) and quality.strip().isdigit():
        return int(quality)
    if quality is not None:
        print(
            f"  [WARN] invalid quality in mkdocs.yml extra.optimize_images: {quality!r}",
            file=sys.stderr,
        )
    return None


def config_max_dimension() -> int | None:
    """Read ``extra.optimize_images.max_dimension`` from mkdocs.yml.

    Long-edge pixel cap for the WebP conversion; absent/0/invalid → ``None``
    (no scaling — opt-in). Non-positive values disable it explicitly.
    """
    value = load_extra("optimize_images", label="optimize-images").get("max_dimension")
    if type(value) is int:
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value) if int(value) > 0 else None
    if value is not None:
        print(
            f"  [WARN] invalid max_dimension in mkdocs.yml extra.optimize_images: {value!r}",
            file=sys.stderr,
        )
    return None


def resolve_quality(cli_quality: int | None, cfg_quality: int | None) -> int:
    """Resolve WebP quality: ``--quality`` CLI arg > mkdocs.yml > module default."""
    if cli_quality is not None:
        return cli_quality
    if cfg_quality is not None:
        return cfg_quality
    return DEFAULT_WEBP_QUALITY


def resolve_max_dimension(cli_max: int | None, cfg_max: int | None) -> int | None:
    """Resolve the long-edge cap: ``--max-dimension`` > mkdocs.yml > off.

    A non-positive CLI value (``--max-dimension 0``) explicitly disables the
    cap even when mkdocs.yml sets one.
    """
    if cli_max is not None:
        return cli_max if cli_max > 0 else None
    return cfg_max


def _clamp_quality(quality: int) -> int:
    """Clamp quality into the valid WebP range 1-100 (out-of-range → nearest bound)."""
    return max(1, min(100, quality))


def iter_images(root: Path) -> Iterator[Path]:
    """Yield all image files under *root* matching IMAGE_EXTENSIONS."""
    for path in root.rglob("*"):
        if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file():
            yield path


def convert_to_webp(
    src: Path,
    *,
    dry_run: bool = False,
    quality: int = DEFAULT_WEBP_QUALITY,
    dst: Path | None = None,
    max_dimension: int | None = DEFAULT_MAX_DIMENSION,
) -> Path | None:
    """Convert a single image to WebP at the given *quality*.

    Out-of-range *quality* values are clamped to 1-100 (above → 100, below → 1).
    *dst* overrides the output location (default: next to *src* with a .webp
    suffix) — used by bucket-upload to convert straight into the keyed target
    path. *max_dimension* downscales so the longest edge is at most that many
    pixels (``None``/0 = no scaling — opt-in; the biggest size win for phone
    photos). Returns the path to the new .webp file, or None if the WebP
    already exists and is not smaller.

    The effective parameters (quality / max_dimension / dimensions / ratio)
    are printed so a bot run's log records exactly how the file was encoded.

    EXIF orientation is baked into the pixels via ``ImageOps.exif_transpose``
    (and the Orientation tag dropped) — WebP viewers often ignore the EXIF
    Orientation tag, so photos taken sideways would otherwise render rotated
    by 90°. All other EXIF (GPS, Make/Model, …) is preserved and carried
    into the WebP.
    """
    quality = _clamp_quality(quality)
    max_dimension = max_dimension if (max_dimension or 0) > 0 else None
    dst = dst or src.with_suffix(".webp")
    if dst.exists() and dst.stat().st_size <= src.stat().st_size:
        print(f"  [SKIP] {src} -> {dst} (already exists and not larger)")
        return None

    if dry_run:
        print(
            f"  [DRY-RUN] would convert {src} -> {dst} "
            f"[WebP q={quality}, max_dimension={max_dimension or 'off'}]"
        )
        return dst

    try:
        with Image.open(src) as im:
            # bake EXIF orientation into the pixels and strip the Orientation
            # tag; other EXIF (GPS, Make/Model, …) is kept in im.info["exif"].
            # Only transpose when an Orientation tag is present (1 / none =
            # already upright): exif_transpose always COPIES the image, so
            # calling it unconditionally would double the peak memory for
            # every correctly-oriented photo.
            if im.getexif().get(0x0112) not in (None, 1):
                im = ImageOps.exif_transpose(im)
            # read EXIF AFTER the transpose (the resized copy loses .info)
            exif = im.info.get("exif")
            src_size = im.size
            scaled = im
            if max_dimension and max(src_size) > max_dimension:
                scale = max_dimension / max(src_size)
                scaled = im.resize(
                    (max(1, round(src_size[0] * scale)), max(1, round(src_size[1] * scale))),
                    Image.LANCZOS,
                )
            save_kwargs: dict = {"quality": quality, "method": 6}
            if exif is not None:
                save_kwargs["exif"] = exif
            scaled.save(dst, "WEBP", **save_kwargs)
    except Exception as exc:
        print(f"  [SKIP] {src}: {exc}")
        return None

    ratio = dst.stat().st_size / src.stat().st_size
    dims = f"{src_size[0]}x{src_size[1]}"
    if scaled.size != src_size:
        dims += f"->{scaled.size[0]}x{scaled.size[1]}"
    print(
        f"  {src} -> {dst} ({ratio:.0%})  "
        f"[WebP q={quality}, max_dimension={max_dimension or 'off'}, {dims}]"
    )
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
                rf"\1{rel_dst}\2)",
                changed,
            )
            # HTML: <img ... src="path" ...>
            changed = re.sub(
                rf'(<img\s[^>]*?src\s*=\s*["\']){re.escape(old)}(["\'][^>]*?/?>)',
                rf"\1{rel_dst}\2",
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
        "--quality",
        type=int,
        metavar="1-100",
        help=(
            f"WebP quality 1-100 (default: {DEFAULT_WEBP_QUALITY}, "
            "or extra.optimize_images.quality in mkdocs.yml; "
            "out-of-range values clamp to the range)"
        ),
    )
    parser.add_argument(
        "--max-dimension",
        type=int,
        metavar="PX",
        help=(
            "downscale so the longest edge is at most PX pixels "
            "(0 = off; default: extra.optimize_images.max_dimension in mkdocs.yml, else off)"
        ),
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

    quality = _clamp_quality(resolve_quality(args.quality, config_quality()))
    max_dimension = resolve_max_dimension(args.max_dimension, config_max_dimension())

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

    mode = " (dry-run)" if args.dry_run else ""
    print(
        f"Found {len(images)} image(s), WebP quality={quality}, "
        f"max_dimension={max_dimension or 'off'}{mode}\n"
    )

    converted = 0
    for img in images:
        dst = convert_to_webp(
            img, dry_run=args.dry_run, quality=quality, max_dimension=max_dimension
        )
        if dst is not None:
            update_md_references(img, dst, dry_run=args.dry_run)
            converted += 1

    suffix = " (dry-run, no changes written)" if args.dry_run else ""
    print(f"\nDone — {converted} image(s) converted to WebP{suffix}")


if __name__ == "__main__":
    main()
