---
title: Notes Tools — Externalize Inline JS/CSS Assets
created: 2026-08-13
tags: [tools, refactor, assets, css, javascript, mkdocs]
---

# Notes Tools — Externalize Inline JS/CSS Assets

## Goal

Move the inline `<style>` / `<script>` blocks out of the Notes → Tools markdown
pages into standalone asset files (`docs/assets/stylesheets/` and
`docs/assets/javascripts/`), so they are easier to maintain and get compressed
by the site's minify pipeline.

**This plan is deferred** — recorded for future work, not implemented now
(decision 2026-08-13: batch this with other tools improvements).

## Problem Statement

Tools pages currently mix UI code into markdown:

| Page                     | Style                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------- |
| `ramen-timer.md`         | inline CSS + JS                                                                             |
| `med-tracker.md`         | inline CSS + JS                                                                             |
| `coffee-flavor-wheel.md` | inline CSS + JS                                                                             |
| `gps-tracker.md`         | inline CSS + JS (just built, ~250 CSS + ~575 JS lines)                                      |
| `fitness.md`             | **already external** (fitness.css / fitness.js via global `extra_css` / `extra_javascript`) |

Pain points of inline assets:

- **Maintainability**: editing JS/CSS inside markdown triggers mdformat churn,
  bloats diffs, mixes concerns, and makes per-tool tooling (lint, format, tests)
  impossible
- **Compression**: inline `<script>`/`<style>` only gets HTML-minified; standalone
  files in `extra_css` / `extra_javascript` are additionally processed by the
  minify plugin (`minify_css` / `minify_js` are already enabled in `mkdocs.yml`)

## Context / Constraints (verified 2026-08-13)

- MkDocs 1.6.1 has **no page-level `extra_css` / `extra_javascript`** — the
  config keys are global only (checked `mkdocs/commands/build.py`: values come
  exclusively from `config.extra_css` / `config.extra_javascript`)
- The minify plugin (`mkdocs.yml` line ~161) has `minify_css: true` and
  `minify_js: true` — global extra asset files get compressed at build time
- `fitness.md` is the established precedent: page keeps only the HTML shell
  (`<div id="fitness-app"></div>`), styles/script registered globally
- Tools page CSS uses `.gps-*` / `.med-*` etc. prefixed selectors → safe to load
  globally (no cross-page collisions); **JS must guard**: standalone scripts run
  on every page, so each needs an early exit when its host element is absent
  (e.g. `if (!document.getElementById("gps-map-host")) return;`)

## Options

- **Option A — global `extra_css` / `extra_javascript` (fitness mode)**
  - Extract each page's CSS → `docs/assets/stylesheets/<tool>.css`, JS →
    `docs/assets/javascripts/<tool>.js`; register in `mkdocs.yml`
  - Pros: zero new infrastructure, minify works, consistent with fitness
  - Cons: every page loads every tool's CSS/JS (small for a personal site)
- **Option B — page-level injection hook**
  - Small MkDocs hook (like `draft_filter` / `snippet_include`) that reads
    `extra_css` / `extra_javascript` from page frontmatter and injects them
  - Pros: per-page loading only
  - Cons: new infrastructure to maintain; MkDocs core doesn't support it
- **Option C — macros (jinja) injection**
  - Use the macros plugin to emit `<link>` / `<script>` tags per page
  - Pros: no hook code
  - Cons: macros module is health-specific today; adds config coupling

**Recommendation**: start with **Option A** (consistent with fitness); revisit
Option B if a third/fourth map-heavy tool makes global loading wasteful.

## Tasks

- [ ] Extract `gps-tracker.md` CSS → `docs/assets/stylesheets/gps-tracker.css`
- [ ] Extract `gps-tracker.md` JS → `docs/assets/javascripts/gps-tracker.js`
  (add the page-guard early exit; keep the `MAP` config + comments)
- [ ] Trim `gps-tracker.md` to HTML shell + prose; drop the `<style>`/`<script>` blocks
- [ ] Repeat for `ramen-timer.md`, `med-tracker.md`, `coffee-flavor-wheel.md`
- [ ] Register all files in `mkdocs.yml` `extra_css` / `extra_javascript`
  (next to `tools.css` / `fitness.css` / `fitness.js`)
- [ ] Verify: `poe server` + CDP smoke test per tool (geolocation mock for
  gps-tracker; the existing CDP test scripts under /tmp are a template)
- [ ] Verify **non-host pages**: because `extra_javascript` loads globally, open
  a few unrelated pages (e.g. `/`, `/moments/`) and confirm each tool script
  exits via its page guard with zero console errors
- [ ] Verify minification: built `site/assets/...` files are compressed
- [ ] Update `internal/architecture.md` file tree + design docs
  (`gps-tracker-design.md` Overview/Decisions/Files, med-tracker-design.md,
  ramen/coffee if they have design docs) to reflect external assets
- [ ] Update `docs/notes/tools/index.md` if the tool descriptions change

## Acceptance Criteria

- All five tools (`ramen-timer`, `med-tracker`, `coffee-flavor-wheel`,
  `gps-tracker`, `fitness`) render identically after extraction (CDP smoke
  tests pass, no console errors on their own pages or on unrelated pages)
- Every tool's CSS/JS lives in `docs/assets/stylesheets|javascripts/<tool>.{css,js}`;
  the markdown pages contain only the HTML shell + prose
- `site/assets/...` built files are minified (csscompressor/jsmin applied) and
  the tools still work (gps-tracker's dynamic `import()` survives compression)
- `mkdocs.yml` `extra_css` / `extra_javascript` lists are alphabetical /
  grouped consistently; `internal/architecture.md` file tree + design docs
  describe the external-asset layout

## Notes

- Deferred by user decision 2026-08-13: "以后和其他几个一起优化" — batch this
  with the other tools improvements instead of doing it alone now
- The gps-tracker CDP test scripts (`/tmp/gps-*.mjs`, headless Chrome +
  SwiftShader + `Emulation.setGeolocationOverride`) are reusable for regression
  testing after the extraction
- Watch out: minify's JS minifier is token-level (jsmin-style) — verify the
  extracted files (template literals / dynamic `import()` in gps-tracker) still
  work after compression; fall back to excluding the file if needed
