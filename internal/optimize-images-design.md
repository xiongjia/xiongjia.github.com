# optimize-images — Design Document

> Convert PNG/JPG/JPEG images to WebP and update Markdown references.

## Overview

A CLI tool that converts image files to WebP format for smaller file sizes,
and automatically updates all `.md` file references to point to the new `.webp`
files. Original files are left untouched.

## Input / Output

- **Input**: One or more image paths (files or directories), or `--all` flag
- **Output**:
  - `.webp` files created alongside originals (same directory, same stem)
  - `.md` files under `docs/` updated with new `.webp` paths
  - Originals preserved

## Pipeline

```
CLI args → resolve_paths()
    │
    ▼
For each image:
    convert_to_webp()
    ├── Check if .webp exists and is not smaller → SKIP
    ├── PIL Image.open → save as WEBP (quality=85, method=6)
    ├── Preserve EXIF data
    └── Return dst path (or None on skip/failure)
    │
    ▼
    update_md_references()
    ├── Traverse docs/**/*.md
    ├── Compute path variants:
    │   ├── Absolute from root: docs/assets/foo.png
    │   ├── Root-relative (no leading /): docs/assets/foo.png
    │   └── Relative from .md dir: ../assets/foo.png
    ├── Replace Markdown: ![alt](old) → ![alt](new)
    ├── Replace HTML: <img src="old"> → <img src="new">
    └── Compute correct relative path from each .md to the .webp destination
```

## Core Functions

### `resolve_paths(args)`

- Parses CLI arguments into `list[Path]`
- Directories → recursively iterated for image files
- Non-existent paths → WARN to stderr, skipped
- Unsupported extensions (not `.png`/`.jpg`/`.jpeg`) → WARN, skipped
- Returns `(paths, has_errors)`

### `convert_to_webp(src, dry_run=False)`

- Quality: 85 (configurable via `WEBP_QUALITY`)
- Method: 6 (slowest, best compression)
- EXIF preservation: reads EXIF from source before conversion, passes to `save()`
- Skip condition: if `.webp` already exists AND `dst.stat().st_size <= src.stat().st_size`
- PIL failure (corrupted image, unsupported format) → SKIP, non-fatal

### `update_md_references(src, dst, dry_run=False)`

- Walks `docs/` recursively for all `*.md` files
- For each `.md` file, tries 3 path variants of `src`:
  1. Direct posix string: `docs/assets/foo.png`
  1. Without leading slash: `foo/bar.png` (if src was `/foo/bar.png`, strips `/` → `foo/bar.png`)
  1. Relative from `.md`'s parent directory: `../assets/foo.png`
- Regex replacement for Markdown images: `!\[.*?\]\s*\(\s*{old}(?:\s*".*?")?\s*\)`
- Regex replacement for HTML images: `<img\s[^>]*?src\s*=\s*["']{old}["'][^>]*?/?>`
- Relative path computation: `os.path.relpath(dst, md_file.parent)`
- Dry-run: prints would-change without writing

## CLI Usage

```bash
# Single image
uv run poe optimize-images docs/path/to/img.png

# Multiple images
uv run poe optimize-images img1.png img2.jpg

# Directory (recursive)
uv run poe optimize-images docs/notes/research/topics/lux/

# Everything under docs/
uv run poe optimize-images --all

# Preview only (no writes)
uv run poe optimize-images --dry-run docs/path/to/img.png
```

## Configuration

| Parameter          | Value                       | Description                         |
| ------------------ | --------------------------- | ----------------------------------- |
| `WEBP_QUALITY`     | `85`                        | WebP quality (0-100)                |
| `method`           | `6`                         | Compression method (0=fast, 6=best) |
| `IMAGE_EXTENSIONS` | `{".png", ".jpg", ".jpeg"}` | Supported input formats             |

## Edge Cases

- **Source file not found** → WARN, continue processing remaining files
- **Unsupported extension** → WARN, continue
- **WebP already exists and not smaller** → SKIP (avoids unnecessary re-encode)
- **PIL cannot parse image** (corrupt, truncated, unsupported sub-format) → SKIP, non-fatal
- **Multiple `.md` files reference same image** → all updated
- **`--all` + `--dry-run`** → preview everything without writing
- **Cross-platform paths** (Windows vs Unix) → `os.path.relpath` fallback to posix
- **No matching images** → exit code 1 if errors occurred, 0 otherwise

## Dependencies

| Package  | Usage                            |
| -------- | -------------------------------- |
| `Pillow` | Image decoding and WebP encoding |
