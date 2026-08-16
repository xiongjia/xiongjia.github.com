"""Create a new Moment entry.

Usage:
    uv run python scripts/create_moment.py "Content text"
    uv run python scripts/create_moment.py "Content text" --image photo.jpg
    uv run python scripts/create_moment.py "Content text" --image a.jpg --image b.png
    uv run python scripts/create_moment.py "Content text" --image a.jpg --image b.png \
        --caption "第一张" --caption "第二张"
    uv run python scripts/create_moment.py "Content text" --image photo.jpg --no-upload
    uv run python scripts/create_moment.py "Content text" --tags food,film --meta rating=4
    uv run python scripts/create_moment.py "Content text" --place "徐汇滨江某咖啡店" \
        --lng 121.47 --lat 31.16
    uv run python scripts/create_moment.py "Content text" --slug my-slug --draft
    uv run python scripts/create_moment.py "Content text" --time "9am"
    uv run python scripts/create_moment.py "Content text" --time "yesterday 9am"
    uv run python scripts/create_moment.py "Content text" --time "30 9pm"
    uv run python scripts/create_moment.py "Content text" --meta name="La Mian" --meta rating=4

Images (``--image``, repeatable): each source is converted to WebP
(PNG/JPG/JPEG at ``extra.optimize_images.quality``; .webp sources are copied
as-is), staged under ``docs/assets/bucket/`` (git-ignored preview copy) and
uploaded to the bucket with ``bucket-upload``'s key rule
(``extra.bucket.upload.rule``). The md link is written as a local relative
path under ``assets/bucket/``, which the build rewrites to the bucket URL
(see internal/bucket-design.md). GPS coordinates embedded in the photo EXIF
are read and saved as ``lng``/``lat`` (WGS-84) when no explicit
``--lng/--lat`` are given. ``--no-upload`` stages the WebP locally without
the rclone upload (e.g. for a later ``poe bucket-upload`` / PicList).
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bucket_sync import resolve_remote
from scripts.bucket_upload import (
    DEFAULT_FALLBACK_NAME,
    DEFAULT_RULE,
    _bucket_config,
    _clamp_quality,
    _pick,
    _resolve_max_size_mb,
    _unique_relative_path,
    config_quality,
    render_rule,
    resolve_quality,
    sanitize_filename,
)
from scripts.optimize_images import IMAGE_EXTENSIONS, convert_to_webp
from shared.bucket import is_enabled as bucket_is_enabled
from shared.date import parse_datetime_arg
from shared.env import load_env_files
from shared.gcj02 import gcj02_to_wgs84

EDITOR = os.environ.get("EDITOR", "vim")

# png/jpg/jpeg are re-encoded to WebP; .webp sources are uploaded as-is
_IMAGE_TYPES = IMAGE_EXTENSIONS | {".webp"}


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


def _yaml_scalar(v: str) -> str:
    """Format a user string (tag / place) for YAML frontmatter.

    Plain-scalar-safe values (letters, digits, ``_``/``-``/``.``, Chinese)
    stay bare; anything a YAML parser could misread — ``foo: bar`` as a
    mapping, ``#tag`` as a comment, ``1_000``/``0x1F`` as ints, booleans,
    dates, quotes — is double-quoted via JSON (always valid YAML). The
    round-trip check uses the SAME yaml loader as the moment plugin, so
    quoting decisions can never disagree with how the frontmatter parses.

    NOTE: contract differs from ``_meta_value`` (which deliberately keeps
    bare ints so ``rating: 4`` stays an int) — tags/place must ALWAYS parse
    back as strings, so numbers/bools are quoted here. Do not merge them.
    """
    if not re.fullmatch(r"[A-Za-z0-9_\-.\u4e00-\u9fff]+", v or ""):
        return json.dumps(v, ensure_ascii=False)
    try:
        if yaml.safe_load(v) == v:
            return v
    except yaml.YAMLError:
        pass
    return json.dumps(v, ensure_ascii=False)


def _parse_tags(raw: list[str]) -> list[str]:
    """Flatten repeated/comma-separated ``--tags`` into a deduped list.

    ``general`` is always first (the site's default tag); user tags follow in
    first-seen order (duplicates across flags collapse).
    """
    tags: list[str] = []
    for item in raw or []:
        for part in item.split(","):
            part = part.strip()
            if part and part not in tags:
                tags.append(part)
    if "general" not in tags:
        tags.insert(0, "general")
    return tags


def _dms_to_degrees(value, negative: bool) -> float | None:
    """Convert an EXIF GPS DMS value to decimal degrees (or None).

    Values read back as (IFDRational|float, ...) DMS tuples or a bare decimal
    float (modern files); non-finite/unparseable input → None.
    """
    try:
        if isinstance(value, (tuple, list)):
            deg, mn, sec = (float(v) for v in value[:3])
        else:
            deg, mn, sec = float(value), 0.0, 0.0
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (deg, mn, sec)):
        return None
    result = deg + mn / 60.0 + sec / 3600.0
    return -result if negative else result


def exif_gps(path: Path) -> tuple[float, float] | None:
    """Read WGS-84 ``(lng, lat)`` from the image's EXIF GPS IFD, else None.

    Photos without GPS data return None silently (the common case); unreadable
    EXIF prints a warning. Out-of-range coordinates are dropped.
    """
    try:
        from PIL import Image

        with Image.open(path) as im:
            gps = im.getexif().get_ifd(0x8825)  # GPSInfo IFD
    except Exception as exc:
        print(f"  [WARN]  {path.name}: cannot read EXIF: {exc}", file=sys.stderr)
        return None
    if not gps or 2 not in gps or 4 not in gps:
        return None
    lat = _dms_to_degrees(gps.get(2), str(gps.get(1, "")).upper() == "S")
    lng = _dms_to_degrees(gps.get(4), str(gps.get(3, "")).upper() == "W")
    if lat is None or lng is None or not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None
    return lng, lat


def _stage_webp(src: Path, webp: Path, quality: int) -> bool:
    """Produce the WebP at *webp* from *src* (True on success).

    PNG/JPG/JPEG are re-encoded at *quality* via ``convert_to_webp`` (EXIF
    preserved, mirrors ``bucket-upload``); .webp sources are copied as-is. The
    target is removed first so a stale file from a failed run never masks a
    fresh conversion.
    """
    webp.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".webp":
        if not webp.exists():
            shutil.copy2(src, webp)
        return True
    webp.unlink(missing_ok=True)
    dst = convert_to_webp(src, quality=quality, dst=webp)
    return dst is not None or webp.is_file()


def _process_image(
    raw: str,
    *,
    now,
    local_dir: Path,
    quality: int,
    max_bytes: int,
    fallback: str,
    rule: str,
    remote: str,
    bucket: str,
    remote_prefix: str,
    upload: bool,
) -> Path | None:
    """Convert one image, upload it to the bucket and return the staged WebP.

    Key rendering mirrors ``bucket-upload`` (``extra.bucket.upload.rule`` on
    *now*, sanitized stem, ``-2`` suffix on same-second collisions). Returns
    None on any failure — upload errors degrade to a local-only stage with a
    warning (the md link still works in dev/VSCode preview).
    """
    src = Path(raw).expanduser()
    if not src.is_file():
        print(f"  [WARN]  path not found: {raw}", file=sys.stderr)
        return None
    if src.suffix.lower() not in _IMAGE_TYPES:
        print(f"  [WARN]  unsupported image type: {src.suffix} ({raw})", file=sys.stderr)
        return None
    if src.stat().st_size > max_bytes:
        print(
            f"  [WARN]  {raw}: {src.stat().st_size / 1e6:.1f}MB exceeds the "
            f"{max_bytes / 1e6:g}MB image limit — skipped",
            file=sys.stderr,
        )
        return None

    stem = sanitize_filename(src.stem, fallback)
    rendered = render_rule(rule, now, stem)
    if not rendered.lower().endswith(".webp"):
        rendered += ".webp"
    rel = _unique_relative_path(rendered, local_dir)
    webp = local_dir / rel

    if not _stage_webp(src, webp, quality):
        print(f"  [SKIP]  {src}: conversion failed", file=sys.stderr)
        return None

    print(f"  [IMAGE]  {src} -> {webp}")
    if upload:
        key = f"{remote_prefix}/{rel}" if remote_prefix else rel
        rpath = f"{remote}:{bucket}/{key}"
        rc = subprocess.call(
            ["rclone", "copyto", str(webp), rpath, "--s3-no-check-bucket", "--progress"]
        )
        if rc != 0:
            print(
                f"  [WARN]  upload failed (rclone rc={rc}) — staged locally at {webp}; "
                f"upload it later via PicList or rclone (key: {key})",
                file=sys.stderr,
            )
        else:
            print(f"  [UPLOAD]  {rpath}")
    return webp


def main():
    parser = argparse.ArgumentParser(description="Create a new Moment")
    parser.add_argument("content", nargs="?", help="Moment content (opens editor if empty)")
    parser.add_argument(
        "--no-editor",
        action="store_true",
        help=(
            "with empty content: skip the editor step — for non-interactive / "
            "bot use (e.g. photo-only moments; the bot subprocess has no TTY)"
        ),
    )
    parser.add_argument(
        "--image",
        action="append",
        metavar="PATH",
        help=(
            "photo(s): converted to WebP, uploaded to the bucket and linked via "
            "assets/bucket/ (repeatable); EXIF GPS fills --lng/--lat when absent. "
            'A caption (alt text) can be attached inline: --image "path|caption"'
        ),
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="with --image: stage the WebP under docs/assets/bucket/ only — skip the rclone upload",
    )
    parser.add_argument(
        "--caption",
        action="append",
        metavar="TEXT",
        help=(
            "per-image caption (order-matched to --image); images without an "
            "inline path|caption are filled in order. Prefer the inline form "
            "for exact pairing; the caption becomes the markdown image's "
            "alt text (the [ ] in ![alt](src))"
        ),
    )
    parser.add_argument(
        "--tags",
        action="append",
        metavar="TAG",
        help="tag(s) — comma-separated and/or repeatable (default: general)",
    )
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
    if args.slug and not re.fullmatch(r"[A-Za-z0-9_-]+", args.slug):
        # the slug is embedded in the filename (``DD-HHMM-{slug}.md``) — a
        # ``/`` or ``..`` would escape the month dir (path traversal) or
        # crash on a missing parent dir; restrict the charset
        parser.error(f"--slug must be letters/digits/_/- only, got {args.slug!r}")

    dt = parse_datetime_arg(args.time)
    month_dir = dt.strftime("%Y-%m")
    time_slug = dt.strftime("%d-%H%M")
    filename = f"{time_slug}{'-' + args.slug if args.slug else ''}.md"

    full_dir = os.path.join(args.dir, month_dir)
    os.makedirs(full_dir, exist_ok=True)

    filepath = os.path.join(full_dir, filename)

    # --- images: WebP + bucket + GPS from EXIF -----------------------------
    image_links: list[str] = []
    inline_captions: list[str] = []
    gps: tuple[float, float] | None = None
    if args.image:
        # R2 credentials / BUCKET_* overrides come from .env (like bucket-upload)
        load_env_files()
        cfg = _bucket_config()
        mapping = (cfg.get("mappings") or [{}])[0]
        upload_cfg = cfg.get("upload") or {}
        quality = _clamp_quality(resolve_quality(None, config_quality()))
        max_bytes = int(
            _resolve_max_size_mb(None, str(upload_cfg.get("max_size_mb") or "")) * 1024 * 1024
        )
        fallback = _pick(
            None,
            "BUCKET_UPLOAD_FALLBACK_NAME",
            str(upload_cfg.get("fallback_name") or DEFAULT_FALLBACK_NAME),
        )
        rule = _pick(None, "BUCKET_UPLOAD_RULE", str(upload_cfg.get("rule") or DEFAULT_RULE))
        prefix = _pick(None, "BUCKET_SYNC_PREFIX", str(mapping.get("prefix") or "assets/bucket/"))
        # cwd-based (not REPO_ROOT): the bot runs inside a worktree whose
        # docs/assets/bucket is symlinked to the main repo, and the md link
        # must stay relative to the moment file inside that worktree — a
        # REPO_ROOT-anchored local_dir would cross the worktree boundary and
        # produce a broken link.
        local_dir = Path.cwd() / "docs" / prefix.strip("/")

        upload = not args.no_upload
        if upload and shutil.which("rclone") is None:
            print(
                "create-moment: WARNING rclone not found — images staged locally without "
                "upload (install rclone or re-upload later with poe bucket-upload)",
                file=sys.stderr,
            )
            upload = False
        if upload and not mapping:
            print(
                "create-moment: WARNING extra.bucket has no mappings — images staged "
                "locally without upload",
                file=sys.stderr,
            )
            upload = False

        remote = bucket = remote_prefix = ""
        if upload:
            remote = resolve_remote(None, label="create-moment")
            bucket = _pick(None, "BUCKET_SYNC_BUCKET", str(mapping.get("bucket") or ""))
            if not bucket:
                bucket = remote
                print(
                    "create-moment: WARNING bucket name fell back to the rclone remote name — "
                    "set BUCKET_SYNC_BUCKET (.env) or mappings[].bucket (mkdocs.yml)",
                    file=sys.stderr,
                )
            remote_prefix = _pick(
                None, "BUCKET_SYNC_REMOTE_PREFIX", str(mapping.get("remote_prefix") or "")
            )

        # each --image may carry an inline caption: ``path|caption`` (the
        # exact pairing the console's paired rows emit; sparse captions stay
        # attached to the right image)
        for raw in args.image:
            path, sep, inline = raw.partition("|")
            webp = _process_image(
                path.strip(),
                now=dt,
                local_dir=local_dir,
                quality=quality,
                max_bytes=max_bytes,
                fallback=fallback,
                rule=rule,
                remote=remote,
                bucket=bucket,
                remote_prefix=remote_prefix,
                upload=upload,
            )
            if webp is None:
                continue
            link = Path(os.path.relpath(webp, full_dir)).as_posix()
            image_links.append(link)
            inline_captions.append(inline.strip() if sep else "")
            if gps is None and args.lng is None:
                gps = exif_gps(Path(path.strip()).expanduser())

        if image_links and not bucket_is_enabled(cfg):
            print(
                "create-moment: NOTE extra.bucket.enabled is false — assets/bucket/ links "
                "resolve only in dev/VSCode preview until you enable it in mkdocs.yml",
                file=sys.stderr,
            )

    # --- geo: explicit --lng/--lat (per --crs) else GPS from the photo ----
    lng = lat = None
    if args.lng is not None:
        lng, lat = args.lng, args.lat
        if args.crs == "gcj02":
            lng, lat = gcj02_to_wgs84(lng, lat)
            print(f"GCJ-02 -> WGS-84: {args.lng},{args.lat} -> {lng:.6f},{lat:.6f}")
    elif gps is not None:
        lng, lat = gps
        print(f"GPS from EXIF (WGS-84): {lng:.6f},{lat:.6f}")

    tags = _parse_tags(args.tags)

    # captions: inline ``path|caption`` wins; the --caption flags fill the
    # images without an inline caption, in order
    fallback_captions = [c.strip() for c in (args.caption or []) if c.strip()]
    if fallback_captions and not image_links:
        print("Warning: --caption given without any image — ignored", file=sys.stderr)
        fallback_captions = []
    captions: list[str] = []
    for cap in inline_captions:
        if cap:
            captions.append(cap)
        elif fallback_captions:
            captions.append(fallback_captions.pop(0))
        else:
            captions.append("")
    if fallback_captions:
        print(
            f"Warning: {len(fallback_captions)} extra --caption(s) with no matching "
            "image — ignored",
            file=sys.stderr,
        )

    lines = [
        "---",
        f"date: {dt.strftime('%Y-%m-%d %H:%M')}",
        "tags:",
    ]
    for t in tags:
        lines.append(f"  - {_yaml_scalar(t)}")
    if args.draft:
        lines.append("draft: true")
    if args.place:
        lines.append(f"place: {_yaml_scalar(args.place)}")
    if lng is not None:
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
            # the KEY rides bare into ``  {key}: {value}`` — quote it when it
            # could be misread as nested YAML (``foo: bar`` would nest)
            safe_key = (
                k if re.fullmatch(r"[A-Za-z0-9_\-. ]+", k) else json.dumps(k, ensure_ascii=False)
            )
            lines.append(f"  {safe_key}: {v}")
    lines += ["---", ""]
    if args.content:
        lines.append(args.content)
    for i, link in enumerate(image_links):
        lines.append("")
        caption = captions[i] if i < len(captions) else ""
        if caption:
            # the caption becomes the markdown image's ALT text (the [ ] in
            # ![alt](src)) — never a separate line; brackets are stripped so
            # they can't break the link syntax, and newlines are flattened
            # (a line break inside the [ ] would split the image link in two)
            alt = (
                caption.replace("[", "")
                .replace("]", "")
                .replace("(", "")
                .replace(")", "")
                .replace("\r", " ")
                .replace("\n", " ")
            )
            lines.append(f"![{alt}]({link})")
        else:
            lines.append(f"![Image]({link})")
    lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    if not args.content and not args.no_editor:
        ret = subprocess.call([EDITOR, filepath])
        if ret != 0:
            print(f"Warning: editor exited with code {ret}")

    print(f"Created: {filepath}")
    if image_links:
        print(f"Images:  {', '.join(image_links)}")
        print("         (assets/bucket/ links are rewritten to the bucket URL at build time)")
    if args.image and not image_links:
        # the moment is saved (content-only) but the run must not look like a
        # success — a bot would open a PR with a broken (imageless) moment
        print(
            "create-moment: ERROR all images failed — moment saved without images; "
            "exit code 1 so the bot does not publish it",
            file=sys.stderr,
        )
        return 1
    print("Preview: uv run poe server  →  http://localhost:8000/moments/")
    return 0


if __name__ == "__main__":
    main()
