---
title: Prototype Mechanism — Repo-level Prototype Directory
created: 2026-07-31
archived: 2026-08-01
status: completed
tags: [prototype, repo, workflow, gitignore, poe]
---

# Prototype Mechanism — Repo-level Prototype Directory

> **Archived** — `archived: 2026-08-01`, `status: completed` (all 27 tasks done).
> Location: `internal/plans/arch/prototypes-mechanism.md`.

## Goal

Add a **prototype mechanism** to this repo: keep experimental mini-projects
directly under the repo root (e.g. `prototypes/prototype-example`) so ideas can be
validated quickly and captured in place, without disturbing the main MkDocs
build, formatting, or lint workflow.

## Tasks

### Directory Convention

- [x] Place all prototypes under repo root `prototypes/<name>/`, one subdirectory per prototype
- [x] Use kebab-case naming (e.g. `prototype-example`, `pmtiles-viewer`)
- [x] Each prototype has its own `README.md` describing purpose, usage, and
  current status, and may maintain its own environment (e.g. a local `.venv`)
- [x] Prototypes are NOT part of the MkDocs build (not registered in
  `mkdocs.yml`, not treated as `docs/` content)

### Index README

- [x] Create `prototypes/README.md` as the prototype **index**, listing all
  prototypes: name, one-line description, created date, status
  (experimental / shelved / done / abandoned)
- [x] Use relative links between prototypes and the index (following the repo's
  relative links convention)

### Gitignore

- [x] **Prototypes are committed**: no root-level ignore rules for
  `prototypes/` (unlike agent-tool dirs `.claude/*`, `.pi/*`)

- [x] Each prototype has its own `.gitignore` for its own build artifacts
  (e.g. Rust `/target`, Python `.venv/`, Node `node_modules/`). For Rust
  prototypes use the common Rust template (`target/`, `debug/`, `**/*.rs.bk`,
  `*.pdb`), while keeping `Cargo.lock` tracked (binary crate convention):

  ```gitignore
  # prototypes/prototype-example/.gitignore
  debug/
  target/
  **/*.rs.bk
  *.pdb
  ```

### Format / Lint Skipping

- [x] Add `extend-exclude` to `[tool.ruff]` in `pyproject.toml` so both
  `ruff format .` and `ruff check .` skip prototypes automatically:

  ```toml
  [tool.ruff]
  extend-exclude = ["prototypes"]
  ```

- [x] Verify `uv run poe fmt`, `uv run poe check-fmt`, and `uv run poe lint-py`
  no longer touch `prototypes/` (mdformat uses explicit path args that
  already exclude prototypes — only the two ruff commands need verification)

- [x] Run `uv run poe check-fmt` and `uv run poe lint-py` to confirm they pass

- [x] Run the mutating `uv run poe fmt` and confirm it leaves `prototypes/`
  untouched (ruff: 99 files unchanged; mdformat explicit-path args)

- [x] Confirm root `extend-exclude` is authoritative during traversal: even
  with a nested `pyproject.toml` (no exclude) inside a prototype, bare
  `ruff check .` / `ruff format .` still skip the prototype subtree

### AI / Manual Tooling on Prototypes

- [x] Document that AI assistance is unaffected: the exclude only stops
  repo-wide automation (`poe fmt` / `poe lint-py` / CI) from touching
  prototypes — AI agents read/edit/build prototype files directly

- [x] Verify `extend-exclude` does NOT block explicit-path calls, so a Python
  prototype can be linted/formatted on demand:

  ```bash
  uv run ruff check prototypes/<name>/        # lint one prototype
  uv run ruff format prototypes/<name>/       # format one prototype
  uv run mdformat prototypes/<name>/README.md # format its markdown
  ```

  A prototype may also carry its own `pyproject.toml`/config to override
  repo-wide rules for its own code.

### Documentation Convention

- [x] Document the prototypes convention in `AGENTS.md` (project structure /
  coding principles): directory location, index README requirement,
  gitignore rules, fmt/lint skip rules
- [x] Update `prototypes/README.md` index whenever a new prototype is created

### First Prototype Validation

- [x] Create `prototypes/prototype-example` as the first prototype to validate the whole flow
- [x] Keep it a **minimal Rust app** (hello-world style, no external deps):
  validates that a non-Python toolchain project sits cleanly in the repo
  without disturbing the MkDocs / ruff / mdformat workflow
- [x] Confirm `cargo build` / `cargo run` works locally (toolchain: cargo 1.97.0 / rustc 1.97.0)
- [x] Confirm `git status` shows `prototypes/` files tracked (index README +
  each prototype's source + its own `.gitignore`) while per-prototype
  artifacts (e.g. `target/`) stay ignored

### Site Listing (docs/notes)

- [x] Create `docs/notes/prototypes.md` — a site page listing all prototypes,
  imitating the `projects.md` style: an **Overview** table (Prototype / Status
  / Created) at the top, then per-toolchain sections with one subsection per
  prototype (description + GitHub Source link). Chinese content, `icon`
  frontmatter
- [x] Each row jumps to the prototype's GitHub tree path:
  `https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/<name>`
  (branch: `master` — matches CI trigger branch; follow the repo's default
  branch if it changes). No special markup needed: the site's global
  external-link override (`overrides/main.html`) already opens every
  off-site link in a new tab (`target="_blank"` + `rel="noopener noreferrer"`)
- [x] Register the page in `mkdocs.yml` nav under Notes
  (e.g. `- Prototypes: notes/prototypes.md`)
- [x] Link the page from the notes landing page
  (`docs/notes/_index_content.md`) so it is discoverable
- [x] Keep the page in sync with `prototypes/README.md` index whenever a
  prototype is added/removed
- [x] Verify `uv run poe build` succeeds with no broken-link warnings

## Notes

- **Why prototypes are committed**: prototypes are first-class mini-projects
  meant to be shared and reviewed in place, unlike agent-tool local state
  (`.claude/*`, `.pi/*`) which is machine-specific and stays ignored — so
  `prototypes/` needs no root-level ignore rules; each prototype ignores its
  own artifacts via its own `.gitignore`
- **No toolchain pollution**: `extend-exclude` in ruff covers both format and
  lint in one place; mdformat naturally skips prototypes via its explicit path
  args (`AGENTS.md CLAUDE.md README.md docs/ internal/`)
- **AI assistance is unaffected**: the exclude only stops repo-wide automation
  (`poe fmt` / `poe lint-py` / CI) from touching prototypes; AI agents and
  manual devs read/edit/build prototype files directly. Verified:
  `extend-exclude` does NOT block explicit-path calls, so a Python prototype
  can still be linted/formatted on demand:
  `uv run ruff check prototypes/<name>/`, `uv run ruff format prototypes/<name>/`,
  `uv run mdformat prototypes/<name>/README.md`
- **CI does not build/test prototypes** (by design): CI only runs
  pytest / mkdocs build / lint for the main repo; prototypes are
  experimental and validated locally (e.g. `cargo build` for the Rust one)
- **Prototype vs. real project**: a validated prototype can be promoted to a
  real project (e.g. a plan under `internal/plans/` or a standalone repo) instead of
  being maintained long-term inside `prototypes/`
- **First prototype is language-agnostic**: `prototype-example` (Rust) proves the
  mechanism works for any toolchain; prototypes may use any language/toolchain
  (Python `.venv`, Node, Rust cargo, etc.), each keeping its own environment
- **Site listing**: prototypes are committed, so a `docs/notes/prototypes.md`
  page documents each prototype and jumps to its GitHub tree path
  (`https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/<name>`);
  relative links to repo-root `prototypes/` do NOT survive the MkDocs build
  (outside `docs_dir`, would warn), so GitHub URLs are the jump target. The
  GitHub links open in a new tab automatically via the global external-link
  override in `overrides/main.html` — no per-link markup required
- **English content**: everything under `prototypes/` (index README,
  per-prototype READMEs, code comments) is written in English; the site
  listing page `docs/notes/prototypes.md` is in Chinese (it is a `docs/`
  page, not prototype content)
- **prototype-example is an example, not a practical prototype**: its
  descriptions (index, README, site page) state it only validates the
  mechanism — it has no real feature
- Related files (paths relative to this archive location): `../../../pyproject.toml`,
  `../../../AGENTS.md`, `../../../prototypes/README.md`, `../../../mkdocs.yml`,
  `../../../docs/notes/`
