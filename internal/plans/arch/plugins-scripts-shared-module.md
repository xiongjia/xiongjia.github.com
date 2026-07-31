---
title: MkDocs Plugins & Scripts Shared Module Refactor
created: 2026-07-31
archived: 2026-08-01
status: completed
tags: [refactor, mkdocs, plugins, python, tooling]
---

# MkDocs Plugins & Scripts — Shared Module Refactor

## Goal

Extract common utilities from the current `plugins/*.py` (MkDocs hooks) and
`scripts/*.py` CLI tools into a shared module, reducing duplication and
improving maintainability.

## Current State

```
plugins/
├── __init__.py              (empty)
├── draft_filter.py          # draft frontmatter parsing, blog_dir lookup
├── mermaid_assets.py        # HTTP download, version check, BeautifulSoup
├── moment_hook.py           # delegates to mkdocs_moment package
├── snippet_include.py       # regex file inclusion, path traversal guard
└── mkdocs_moment/
    ├── __init__.py           # on_* hook delegation
    └── plugin.py             # frontmatter parse, date parse, slugify, render

scripts/
├── create_post.py            # slugify, tags parse, date format, argparser
├── create_moment.py          # argparser, date format
├── add_weight_week.py        # argparser, date format
├── optimize_images.py        # argparser, path walking, md ref update
└── md2wechat.py              # markdown-it renderer, file ops
```

## Duplications Found

| Pattern                                         | Locations                                                                             | Count |
| ----------------------------------------------- | ------------------------------------------------------------------------------------- | ----- |
| Logger setup (`logging.getLogger("mkdocs...")`) | all 4 hook files + mkdocs_moment                                                      | 5     |
| Frontmatter parsing (YAML)                      | `draft_filter.py`, `mkdocs_moment/plugin.py`                                          | 2     |
| Date format / parse                             | `create_post.py`, `create_moment.py`, `add_weight_week.py`, `mkdocs_moment/plugin.py` | 4     |
| Slugify                                         | `create_post.py`, `mkdocs_moment/plugin.py`                                           | 2     |
| File read/write with UTF-8                      | nearly all files                                                                      | 7+    |
| Project root detection                          | scripts reference root differently                                                    | 3+    |
| Docs_dir resolution                             | `draft_filter.py`, `snippet_include.py`, `mermaid_assets.py`                          | 3     |
| Argparse common options                         | `create_post.py`, `create_moment.py`, `add_weight_week.py`                            | 3     |

## Tasks

### Phase 1: Audit & Discovery

- [x] **Audit all plugins and scripts for duplicated code**

  - Catalog every utility function and its locations — see Duplications Found table above
  - Note API differences between duplicate implementations — `slugify` vs `_extract_slug` same-name/different-semantics; frontmatter fast-scan vs full-parse
  - Identify patterns that are hard to extract (tight coupling) — mkdocs hook load-time `sys.path` (see Open Questions #1)
  - Deliverable: duplication map — this document

- [x] **Design the shared module structure**

  - Decide: single top-level `shared/` package at repo root (developer decision; `share` rejected, `_lib`/`toolkit` alternatives documented)
  - Define module boundaries — `strings.py`, `frontmatter.py`, `date.py` (from `scripts/time_arg.py`), `io.py`, `logging.py`, `cli.py`
  - Decide naming conventions — explicit names (`slugify_title`, `slug_from_filename`, `has_draft_flag`, `parse_frontmatter`), no overloaded generic names
  - Deliverable: module layout + API signatures (see Phase 2)

### Phase 2: Extract Shared Library

- [x] **Extract: string utilities — `shared/strings.py`**

  - `slugify_title(text, *, fallback="post")` — URL slug from a title; non-ASCII stripped → fallback when empty (migrated from `create_post.slugify`)
  - `slug_from_filename(stem)` — slug from a moment filename stem: `30-1430-home-lab` → `home-lab` (migrated from `mkdocs_moment._extract_slug` + `_RE_FILENAME_DATE`)
  - Kept as two functions — different inputs/semantics, must not merge

- [x] **Extract: frontmatter utilities — `shared/frontmatter.py`**

  - `has_draft_flag(text)` — fast scan (no YAML parse) for `draft: true/yes/1` with any spacing (migrated from `draft_filter._has_draft_frontmatter`)
  - `parse_frontmatter(text) -> tuple[dict, str] | None` — full YAML parse (migrated from `mkdocs_moment` inline block); callers keep per-case logs by inspecting `text` around a `None`
  - Kept as two functions — fast path must stay cheap (`on_files` scans every file)

- [x] **Extract: date utilities — `shared/date.py`**

  - `scripts/time_arg.py` moved to `shared/date.py` (`parse_datetime_arg` unchanged)
  - Added `parse_date_strict` (from `mkdocs_moment._parse_date`; no fallback, `None` on failure)
  - `add_weight_week` inline `strptime` converged on `parse_datetime_arg`

- [x] **Extract: file I/O & path helpers** — `shared/io.py` (`safe_read`, `resolve_within` traversal guard from `snippet_include.py`); draft_filter and snippet_include migrated

- [x] **Extract: logging setup** — *cancelled (low value: uniform pattern only, no behavior change)*

- [x] **Extract: CLI argument patterns** — *cancelled (low value, see Open Questions #6: thin flag overlap across scripts)*

### Phase 3: Migrate & Clean Up

- [x] **Migrate plugins to use shared module** (draft_filter → shared/frontmatter+io; mkdocs_moment → shared/date+frontmatter+strings; snippet_include → shared/io; mermaid_assets & moment_hook have no shared-dependency)

  - Update `draft_filter.py`, `mermaid_assets.py`, `snippet_include.py`, `moment_hook.py`
  - Keep backward compatibility (public hook function signatures unchanged)

- [x] **Migrate scripts to use shared module** (create_post, create_moment, add_weight_week on shared/date; optimize_images/md2wechat have no shared-dependency)

  - Update `create_post.py`, `create_moment.py`, `add_weight_week.py`, `optimize_images.py`
  - Update `scripts/md2wechat/` if applicable

- [x] **Remove dead code** (local slugify, \_extract_slug, \_parse_date, inline draft scan removed; lint clean)

  - Delete now-unnecessary inline implementations after migration
  - Run `uv run poe lint-py` — no new violations

### Phase 4: Unit Tests

- [x] **Set up test infrastructure**

  - Add `tests/` directory at project root
  - Choose test runner (`pytest` — already compatible with uv)
  - Add `pytest` to `pyproject.toml` dev dependencies
  - Add `uv run poe test` task in `pyproject.tool.poe`

- [x] **Write tests for shared utilities** (test_date.py, test_strings.py, test_frontmatter.py, test_io.py — 31 cases)

  - `frontmatter.py`: ✅ `test_frontmatter.py` (draft variants, malformed YAML, no frontmatter)
  - `io.py`: ✅ `test_io.py` (safe_read ok/limit/missing, resolve_within traversal + prefix attack)
  - `strings.py`: ✅ `test_strings.py` (Chinese fallback, special chars, empty input)
  - `date.py`: ✅ `tests/test_date.py` (11 cases; migrated from test_time_arg.py)
  - `cli.py`: *cancelled* — `shared/cli.py` never extracted (see Open Questions #6)

- [x] **Write integration tests for hooks**

  - ✅ `draft_filter.on_files` with draft/non-draft fixture files (`tests/test_hooks.py`)
  - ✅ `snippet_include.on_page_markdown` with valid, missing, and path-traversal includes (`tests/test_hooks.py`)
  - `mermaid_assets.on_post_page` — *cancelled (mock-HTTP cost outweighs value)*

- [x] **Write integration tests for scripts**

  - ✅ `slugify`/slug outputs (`tests/test_strings.py`)
  - ✅ `create-post` frontmatter generation with various arg combinations (`tests/test_scripts.py`, incl. `--dir`)
  - ✅ `optimize_images` dry-run (no file mutation) (`tests/test_scripts.py`)

- [x] **CI integration**

  - Add `uv run poe test` to `.github/workflows/` (run on PR to main)

## Open Questions / Risks

These are the hard parts of the `shared/` approach that need resolving before
or during Phase 2/3:

1. **Import path bootstrap (biggest risk) — RESOLVED (verified)** — a probe
   hook confirmed the mkdocs hook loader puts `plugins/` on `sys.path[0]`
   temporarily and the repo root is NOT on `sys.path`; `import shared` fails
   inside hooks and in `python scripts/x.py`. Decision: each consumer file adds
   a 2-3 line bootstrap before importing `shared`:

   ```python
   import sys
   from pathlib import Path

   sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
   ```

   (`plugins/mkdocs_moment/plugin.py` uses `parent.parent.parent`.)

1. **`slugify` vs `_extract_slug` may be a false duplicate** —
   `create_post.slugify` builds a URL slug from a title (Chinese → fallback);
   `mkdocs_moment._extract_slug` extracts a slug from a filename. Same name,
   different semantics. Extract as two named functions
   (`slugify_title` / `slug_from_filename`), not one `slugify`.

1. **Frontmatter fast-path vs full parse — API decided** — keep two functions
   in `shared/frontmatter.py` (`has_draft_flag` fast scan + `parse_frontmatter`
   full parse); draft_filter keeps its IOError handling and passes the 2KB head
   to `has_draft_flag`; mkdocs_moment keeps its per-case log messages by
   inspecting `text` features around a `None` result.

1. **`md2wechat` domain logic stays out** (non-goal) — only its file I/O
   utilities are candidates; its markdown-it rendering stays put.

1. **Logger name semantics** — unifying `logging.getLogger("mkdocs.hooks.*")`
   helpers must preserve distinct logger names per module, or log filtering
   and mkdocs' own logger handlers may break.

1. **CLI common args have thin overlap** — `create_post`/`create_moment`/
   `add_weight_week`/`optimize_images` share few flags; `add_common_args`
   (dry-run/verbose) is worth it only if `optimize_images` gains a dry-run.
   Low value — reconsider scope.

1. **`time_arg.py` migration** — the existing `scripts/time_arg.py` moves into
   `shared/date.py`; both `create_post`/`create_moment` plus `add_weight_week`
   (still has its own `strptime`) should converge on it.

## Proposed Directory (shared/ at repo root)

Single shared package at the repo root, imported by both plugins and scripts:

```
shared/                      # NEW — shared utilities (repo root)
├── __init__.py
├── frontmatter.py           # parse_frontmatter, has_draft_flag
├── io.py                    # safe_read, docs_dir_resolve, traversal_guard
├── logging.py               # mkdocs_logger helper, uniform script log format
├── strings.py               # slugify (unify with mkdocs_moment._extract_slug)
├── date.py                  # date format/parse (supersedes scripts/time_arg.py)
└── cli.py                   # common argparse helpers (add_common_args)

plugins/                     # cleaned up, imports from shared
└── …
scripts/                     # cleaned up, imports from shared
└── …
```

> `shared/` was chosen over `_lib/`/`toolkit/` per developer decision. The
> naming follows the monorepo convention (`shared/`); "share" was rejected
> (uncommon for code packages, ambiguous with data-dir semantics).

## Non-Goals

- Changing hook function signatures (must remain backward compatible)
- Extracting `mkdocs_moment` core logic — it's already a package, only utility extraction
- Extracting `md2wechat/` rendering logic — it's domain-specific, only utility extraction

## References

- [pyproject.toml](../../../pyproject.toml) — project dependencies
- [plugins/](../../../plugins/) — current plugin files
- [scripts/](../../../scripts/) — current script files
