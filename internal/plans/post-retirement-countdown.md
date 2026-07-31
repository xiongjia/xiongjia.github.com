---
title: Blog Post — Retirement Countdown Implementation
created: 2026-07-31
tags: [blog, post, health, retirement, mkdocs-macros]
---

# Blog Post: Retirement Countdown Implementation

## Goal

Write a blog post documenting how the Retirement Countdown health page works —
the MkDocs macros plugin integration, China's progressive delayed retirement
policy (2025 reform), date calculation logic, monthly grid visualization,
and data configuration.

Published under `docs/notes/posts/posts/`.

## Tasks

- [ ] **Outline the post**

  - Motivation: personal retirement planning tracker
  - Architecture: MkDocs macros plugin → `retire_macros.py` → `retire.yml` data
  - Policy overview: China's 渐进式延迟退休 (progressive delayed retirement) effective 2025-01-01
    - Male: 60→63, delay 1 month per 4 months, max 36 months
    - Female cadre: 55→58, delay 1 month per 4 months, max 36 months
    - Female worker: 50→55, delay 1 month per 2 months, max 60 months
  - Core algorithm: `_add_months()`, delay calculation, retirement date determination
  - Rendering: info card, monthly grid with color-coded cells
  - Published to `docs/notes/posts/posts/`

- [ ] **Write the post**

  - Follow existing post format (frontmatter with date, tags, slug, categories)
  - Include code snippets for key parts:
    - Gender configuration table (original age, delay rate, max delay)
    - Delay month calculation formula
    - Monthly grid rendering with CSS-only color coding
    - YAML data structure
  - Explain edge cases: people born before 2025 unaffected, rounding logic
  - Published to `docs/notes/posts/posts/`

- [ ] **Review & publish**

  - Verify dev server renders the post correctly
  - Cross-check calculation results against government policy examples
  - Remove `draft: true` when ready

## References

- [Health: Retirement Countdown](../../docs/notes/health/retire.md)
- [retire_macros.py](../../docs/notes/health/macros/retire_macros.py)
