"""Create a new MkDocs blog post with proper frontmatter.

Usage:
    uv run poe create-post "Post Title"
    uv run poe create-post "Post Title" --category dev
    uv run poe create-post "Post Title" --category thought --tags life,mood
    uv run poe create-post "Post Title" --time "yesterday 9am"
"""

import argparse
import os
import sys
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.date import parse_datetime_arg
from shared.strings import slugify_title

DOCS_DIR = "docs"
DEFAULT_POST_DIR = "notes/posts/posts"


def parse_tags(raw: str | None) -> list[str]:
    """Parse comma-separated tags string into a list."""
    if not raw:
        return ["dev"]
    return [t.strip() for t in raw.split(",") if t.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new MkDocs blog post")
    parser.add_argument("title", help="Post title")
    parser.add_argument(
        "--category",
        "-c",
        default="bits",
        help="Category directory (e.g. bits, dev, thought). Default: bits",
    )
    parser.add_argument(
        "--tags",
        "-t",
        default=None,
        help="Comma-separated tags. Default: dev",
    )
    parser.add_argument(
        "--slug",
        "-s",
        default=None,
        help="URL slug. Auto-generated from title if omitted",
    )
    parser.add_argument(
        "--description",
        "-d",
        default=None,
        help="Post description. Reuses title if omitted",
    )
    parser.add_argument(
        "--no-draft",
        action="store_true",
        help="Publish immediately instead of creating as draft",
    )
    parser.add_argument(
        "--time",
        help=(
            "Publish date/time for backdating (default: now). Examples: 9am, "
            "yesterday, yesterday 9am, 30 9am, 2026-07-30 21:36"
        ),
    )
    parser.add_argument(
        "--dir",
        default=DOCS_DIR,
        help=f"Docs root directory (default: {DOCS_DIR})",
    )

    args = parser.parse_args()
    dt = parse_datetime_arg(args.time)

    # Determine slug — fallback to category name for Chinese-only titles
    slug = args.slug or slugify_title(args.title, fallback=args.category)
    # pure-digit slugs would be parsed as int by YAML — guard against it
    if slug.isdigit():
        if args.slug is not None:
            print(
                "Error: --slug cannot be a pure number (YAML would parse it as int)",
                file=sys.stderr,
            )
            sys.exit(1)
        slug = f"post-{slug}"

    # Build file path
    filename = f"{dt.strftime('%Y%m%d')}-{slug}.md"
    post_dir = os.path.join(args.dir, DEFAULT_POST_DIR, args.category)
    os.makedirs(post_dir, exist_ok=True)
    filepath = os.path.join(post_dir, filename)

    if os.path.exists(filepath):
        print(f"Error: {filepath} already exists!", file=sys.stderr)
        sys.exit(1)

    tags = parse_tags(args.tags)
    description = args.description or args.title
    categories = [args.category]
    if args.category != "dev":
        categories.append("dev")

    draft_line = "draft: true\n" if not args.no_draft else ""
    # seconds required so PyYAML parses it as a timestamp (not a string)
    created_iso = dt.strftime("%Y-%m-%d %H:%M:%S")

    content = f"""---
title: {args.title}
date:
  created: {created_iso}
  updated: {created_iso}
{draft_line}authors: [xiongjia]
tags:
{chr(10).join(f"  - {tag}" for tag in tags)}
slug: {slug}
description: >
  {description}
categories:
{chr(10).join(f"  - {cat}" for cat in categories)}
---

<!-- more -->
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Compute URL path (matches blog plugin's default post_url_format)
    url_path = f"/notes/posts/{dt.strftime('%Y/%m/%d')}/{slug}/"

    print(f"Created: {filepath}")
    print(f"URL:     {url_path}")


if __name__ == "__main__":
    main()
