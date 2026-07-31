---
title: Blog Post — Weight Track Implementation
created: 2026-07-31
tags: [blog, post, health, weight, mkdocs-macros]
---

# Blog Post: Weight Track Implementation

## Goal

Write a blog post documenting how the Weight Track health page works —
the MkDocs macros plugin integration, data format, chart rendering
(Mermaid), BMI calculation, and weekly tracking workflow.

Published under `docs/notes/posts/posts/`.

## Tasks

- [ ] **Outline the post**

  - Motivation: why track weight programmatically in a static site
  - Architecture: MkDocs macros plugin → `weight_macros.py` → `weight.yml` data
  - Data format: YAML schema (start_date, records per week)
  - Rendering: BMI info card, progress bar, weekly table, trend chart (Mermaid)
  - Maintenance: `uv run poe add-weight-week [n]` script for adding empty weeks
  - Published to `docs/notes/posts/posts/`

- [ ] **Write the post**

  - Follow existing post format (frontmatter with date, tags, slug, categories)
  - Category: suitable category (e.g. `dev` or a new `health` category)
  - Include code snippets for key parts:
    - Weight YAML data structure
    - BMI calculation and classification (Chinese standard)
    - Mermaid chart generation from macro
    - Weekly grid rendering logic
  - Explain BMI Chinese classification standard (underweight / normal / overweight / obese)
  - Published to `docs/notes/posts/posts/`

- [ ] **Review & publish**

  - Verify dev server renders the post correctly
  - Check links, code blocks, and Mermaid diagrams
  - Remove `draft: true` when ready

## References

- [Health: Weight Track](../../docs/notes/health/weight.md)
- [weight_macros.py](../../docs/notes/health/macros/weight_macros.py)
- [scripts/add_weight_week.py](../../scripts/add_weight_week.py)
