---
title: Prototype Mechanism — Repo-level Prototype Directory
created: 2026-07-31
tags: [prototype, repo, workflow, gitignore, poe]
---

# Prototype Mechanism — Repo-level Prototype Directory

## Goal

Add a **prototype mechanism** to this repo: keep experimental mini-projects
directly under the repo root (e.g. `prototypes/r2-client`) so ideas can be
validated quickly and captured in place, without disturbing the main MkDocs
build, formatting, or lint workflow.

## Tasks

### Directory Convention

- [ ] Place all prototypes under repo root `prototypes/<name>/`, one subdirectory per prototype
- [ ] Use kebab-case naming (e.g. `r2-client`, `pmtiles-viewer`)
- [ ] Each prototype has its own `README.md` describing purpose, usage, and
  current status, and may maintain its own environment (e.g. a local `.venv`)
- [ ] Prototypes are NOT part of the MkDocs build (not registered in
  `mkdocs.yml`, not treated as `docs/` content)

### Index README

- [ ] Create `prototypes/README.md` as the prototype **index**, listing all
  prototypes: name, one-line description, created date, status
  (experimental / shelved / done / abandoned)
- [ ] Use relative links between prototypes and the index (following the repo's
  relative links convention)

### Gitignore

- [ ] Add prototypes ignore rules to `.gitignore` — ignore everything, keep only the index:

  ```gitignore
  # prototypes — ignore everything except the index
  prototypes/*
  !prototypes/README.md
  ```

- [ ] Follow the repo's existing "partial ignore" pattern (`.claude/*` +
  `!.claude/skills/`) for consistency

### Format / Lint Skipping

- [ ] Add `extend-exclude` to `[tool.ruff]` in `pyproject.toml` so both
  `ruff format .` and `ruff check .` skip prototypes automatically:

  ```toml
  [tool.ruff]
  extend-exclude = ["prototypes"]
  ```

- [ ] Verify `uv run poe fmt`, `uv run poe check-fmt`, and `uv run poe lint-py`
  no longer touch `prototypes/` (mdformat uses explicit path args that
  already exclude prototypes — only the two ruff commands need verification)

- [ ] Run `uv run poe check-fmt` and `uv run poe lint-py` to confirm they pass

### Documentation Convention

- [ ] Document the prototypes convention in `AGENTS.md` (project structure /
  coding principles): directory location, index README requirement,
  gitignore rules, fmt/lint skip rules
- [ ] Update `prototypes/README.md` index whenever a new prototype is created

### First Prototype Validation

- [ ] Create `prototypes/r2-client` as the first prototype to validate the whole flow
- [ ] Confirm `git status` shows `prototypes/README.md` tracked while other
  prototype content stays ignored

## Notes

- **Why "partial ignore"**: fully ignoring `prototypes/` would leave the repo
  with no entry point for prototypes; keeping the index README committed
  matches the repo's existing convention of tracking part of a directory
  (`.pi/*`, `.claude/*`) while ignoring the rest
- **No toolchain pollution**: `extend-exclude` in ruff covers both format and
  lint in one place; mdformat naturally skips prototypes via its explicit path
  args (`AGENTS.md CLAUDE.md README.md docs/ internal/`)
- **Prototype vs. real project**: a validated prototype can be promoted to a
  real project (e.g. a plan under `internal/plans/` or a standalone repo) instead of
  being maintained long-term inside `prototypes/`
- Related files: `.gitignore`, `pyproject.toml`, `AGENTS.md`, `prototypes/README.md`
