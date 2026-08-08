---
title: Blog Post — Fitness Counter Implementation
created: 2026-08-05
tags: [blog, post, fitness, tools, vanilla-js, localStorage]
---

# Blog Post: Fitness Counter Implementation

## Goal

Write a blog post documenting the Fitness Counter tool (`docs/notes/tools/fitness.md`)
— a lightweight daily workout counter with kcal estimation. Covers the
architecture (vanilla JS widget + localStorage), the MET calorie formula, the
Material-theme color adaptation, and the build pitfalls found along the way.

Published under `docs/notes/posts/posts/`.

## Tasks

- [ ] **Outline the post**

  - Motivation: why a workout counter in a static notes site (open page →
    count → close, no backend)
  - Architecture: `fitness.md` mount point + `fitness.js` (state-driven render,
    event delegation) + `fitness.css` (Material variables) + `localStorage`
  - Color adaptation: Kimi tokens → Material theme variables (mapping table),
    dark mode via `[data-md-color-scheme="slate"]`
  - Kcal estimation: MET method, per-exercise MET table, example calculation
    (70kg × pushup 3×12 → 13 kcal)
  - Interaction details: exercise tab strip with emoji, two-step confirm reset,
    goal modal, cross-day auto reset
  - Build integration: `mkdocs.yml` extra_css/extra_javascript **and** minify
    plugin `css_files`/`js_files` (the pitfall that drops assets otherwise)
  - Reference design doc: `internal/fitness-counter-design.md`

- [ ] **Write the post**

  - Follow existing post format (frontmatter with date, tags, slug, description)
  - Category: `bits` (matching the current post layout) or a new suitable category
  - Include code snippets:
    - MET formula + exercise table
    - localStorage schema (`fitness_counter_v1`)
    - Kimi → Material variable mapping table
    - Record id uniqueness fix (`Date.now()` collision)
  - Draft first (`draft: true`), then publish

- [ ] **Review & publish**

  - Verify dev server renders the post correctly
  - Check links, code blocks
  - Remove `draft: true` when ready

## References

- [Fitness Counter](../../docs/notes/tools/fitness.md)
- [Design doc](../../internal/fitness-counter-design.md)
- [fitness.js](../../docs/assets/javascripts/fitness.js)
- [fitness.css](../../docs/assets/stylesheets/fitness.css)
- [Health: Weight Track](../../docs/notes/health/weight.md) — related health-tool post for style reference
