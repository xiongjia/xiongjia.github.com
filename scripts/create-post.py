"""Create a new MkDocs blog post with proper frontmatter.

Usage:
    uv run poe create-post "Post Title"
    uv run poe create-post "Post Title" --category dev
    uv run poe create-post "Post Title" --category thought --tags life,mood
"""

import argparse
import datetime
import os
import re
import sys

DOCS_DIR = "docs"
DEFAULT_POST_DIR = "notes/posts"


def slugify(text: str, *, fallback: str = "post") -> str:
    """Generate a URL-friendly slug from text.

    Strips non-ASCII characters, lowercases, and replaces spaces with hyphens.
    If the result is empty (e.g. purely Chinese title), uses the fallback.
    """
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", " ", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    slug = slug.strip("-")
    return slug if slug else fallback


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

    args = parser.parse_args()
    today = datetime.date.today()

    # Determine slug — fallback to category name for Chinese-only titles
    slug = args.slug or slugify(args.title, fallback=args.category)

    # Build file path
    filename = f"{today.strftime('%Y%m%d')}-{slug}.md"
    post_dir = os.path.join(DOCS_DIR, DEFAULT_POST_DIR, args.category)
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

    content = f"""---
title: {args.title}
date:
  created: {today.isoformat()}
  updated: {today.isoformat()}
authors: [xiongjia]
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
    url_path = f"/{DEFAULT_POST_DIR}/{args.category}/{today.strftime('%Y/%m/%d')}/{slug}/"

    print(f"Created: {filepath}")
    print(f"URL:     {url_path}")


if __name__ == "__main__":
    main()
