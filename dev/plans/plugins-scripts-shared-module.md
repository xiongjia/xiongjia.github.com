---
title: MkDocs Plugins & Scripts Shared Module Refactor
created: 2026-07-31
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
├── create-post.py            # slugify, tags parse, date format, argparser
├── create-moment.py          # argparser, date format
├── add_weight_week.py        # argparser, date format
├── optimize_images.py        # argparser, path walking, md ref update
└── md2wechat.py              # markdown-it renderer, file ops
```

## Duplications Found

| Pattern                                         | Locations                                                                             | Count |
| ----------------------------------------------- | ------------------------------------------------------------------------------------- | ----- |
| Logger setup (`logging.getLogger("mkdocs...")`) | all 4 hook files + mkdocs_moment                                                      | 5     |
| Frontmatter parsing (YAML)                      | `draft_filter.py`, `mkdocs_moment/plugin.py`                                          | 2     |
| Date format / parse                             | `create-post.py`, `create-moment.py`, `add_weight_week.py`, `mkdocs_moment/plugin.py` | 4     |
| Slugify                                         | `create-post.py`, `mkdocs_moment/plugin.py`                                           | 2     |
| File read/write with UTF-8                      | nearly all files                                                                      | 7+    |
| Project root detection                          | scripts reference root differently                                                    | 3+    |
| Docs_dir resolution                             | `draft_filter.py`, `snippet_include.py`, `mermaid_assets.py`                          | 3     |
| Argparse common options                         | `create-post.py`, `create-moment.py`, `add_weight_week.py`                            | 3     |

## Tasks

### Phase 1: Audit & Discovery

- [ ] **Audit all plugins and scripts for duplicated code**

  - Catalog every utility function and its locations
  - Note API differences between duplicate implementations
  - Identify patterns that are hard to extract (tight coupling)
  - Deliverable: duplication map (markdown doc in plan)

- [ ] **Design the shared module structure**

  - Decide: flat `plugins/_lib/` and `scripts/_lib/` vs single top-level `toolkit/` package
  - Define module boundaries (e.g. `frontmatter.py`, `logging.py`, `io.py`, `cli.py`)
  - Decide naming conventions for the extracted functions
  - Deliverable: module layout proposal

### Phase 2: Extract Shared Library

- [ ] **Extract: frontmatter utilities**

  - Move YAML frontmatter parsing into shared module
  - Support: `draft: true` check, arbitrary field extraction
  - Replace inline implementations in `draft_filter.py` and `mkdocs_moment/plugin.py`

- [ ] **Extract: file I/O & path helpers**

  - Move `safe_read()`, `safe_write()`, `docs_dir_resolve()` into shared module
  - Path traversal guard (from `snippet_include.py`)
  - Replace inline implementations across all plugins

- [ ] **Extract: logging setup**

  - Standardize `logging.getLogger()` pattern across all plugin files
  - Add uniform log format for scripts

- [ ] **Extract: string utilities**

  - Move `slugify()` into shared module (single implementation)
  - Date formatting helpers used across scripts

- [ ] **Extract: CLI argument patterns**

  - Common argparse options (dry-run, verbose, etc.)
  - Reusable `add_common_args()` helper

### Phase 3: Migrate & Clean Up

- [ ] **Migrate plugins to use shared module**

  - Update `draft_filter.py`, `mermaid_assets.py`, `snippet_include.py`, `moment_hook.py`
  - Keep backward compatibility (public hook function signatures unchanged)

- [ ] **Migrate scripts to use shared module**

  - Update `create-post.py`, `create-moment.py`, `add_weight_week.py`, `optimize_images.py`
  - Update `scripts/md2wechat/` if applicable

- [ ] **Remove dead code**

  - Delete now-unnecessary inline implementations after migration
  - Run `uv run poe lint-py` — no new violations

### Phase 4: Unit Tests

- [ ] **Set up test infrastructure**

  - Add `tests/` directory at project root
  - Choose test runner (`pytest` — already compatible with uv)
  - Add `pytest` to `pyproject.toml` dev dependencies
  - Add `uv run poe test` task in `pyproject.tool.poe`

- [ ] **Write tests for shared utilities**

  - `frontmatter.py`: test `has_draft_flag`, arbitrary field extraction, malformed YAML, no frontmatter
  - `io.py`: test `safe_read`, `docs_dir_resolve`, traversal guard (path traversal attempts)
  - `strings.py`: test `slugify` edge cases (Chinese chars, special chars, empty input)
  - `date.py`: test date format/parse with various input formats
  - `cli.py`: test `add_common_args` parser output

- [ ] **Write integration tests for hooks**

  - Test `draft_filter.on_files` with draft/non-draft fixture files
  - Test `snippet_include.on_page_markdown` with valid, missing, and path-traversal includes
  - Test `mermaid_assets.on_post_page` with & without mermaid script tags
  - Mock external HTTP to avoid network dependency

- [ ] **Write integration tests for scripts**

  - Test `slugify` output against expected patterns
  - Test `create-post` frontmatter generation with various arg combinations
  - Test `optimize_images` dry-run mode (no actual file mutation)

- [ ] **CI integration**

  - Add `uv run poe test` to `.github/workflows/` (run on PR to main)

## Proposed Directory (Illustrative)

```
plugins/
├── __init__.py
├── _lib/                    # NEW — shared plugin utilities
│   ├── __init__.py
│   ├── frontmatter.py       # parse_frontmatter, has_draft_flag
│   ├── io.py                # safe_read, docs_dir_resolve, traversal_guard
│   └── logging.py           # mkdocs_logger helper
├── draft_filter.py          # cleaned up, imports from _lib
├── mermaid_assets.py
├── moment_hook.py
├── snippet_include.py
└── mkdocs_moment/ …

scripts/
├── _lib/                    # NEW — shared script utilities
│   ├── __init__.py
│   ├── cli.py               # common argparse helpers
│   ├── date.py              # date format/parse
│   ├── io.py                # project root, file ops
│   └── strings.py           # slugify
├── create-post.py           # cleaned up
├── create-moment.py
├── add_weight_week.py
├── optimize_images.py
└── md2wechat/ …
```

## Non-Goals

- Changing hook function signatures (must remain backward compatible)
- Extracting `mkdocs_moment` core logic — it's already a package, only utility extraction
- Extracting `md2wechat/` rendering logic — it's domain-specific, only utility extraction

## References

- [pyproject.toml](../../pyproject.toml) — project dependencies
- [plugins/](../../plugins/) — current plugin files
- [scripts/](../../scripts/) — current script files
