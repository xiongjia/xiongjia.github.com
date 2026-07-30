# Discuss System — Design Document

> Giscus-powered comment system built on GitHub Discussions.

## Overview

A comment system that appears on any page with `comments: true` in its
frontmatter. Powered by [Giscus](https://giscus.app/), which uses GitHub
Discussions as the comment storage backend.

## Trigger Condition

Comments only render on pages where both conditions are met:

1. `config.extra.comments.enabled` is `true` in `mkdocs.yml`
1. Page frontmatter contains `comments: true`

```yaml
---
title: Discuss
comments: true
---
```

## Page Structure

- **Dedicated page**: `docs/discuss/index.md` — a single page for general
  discussion, questions, or feedback
- Other pages can also enable comments by adding `comments: true` to their
  frontmatter (currently only the Discuss page)

## Implementation

### Theme Override: `overrides/partials/comments.html`

A Jinja2 template fragment that:

1. Checks `config.extra.comments.enabled AND page.meta.comments`
1. If true, renders a `<div id="giscus-container">` and loads Giscus via a
   dynamically created `<script>` element
1. Configures Giscus with:
   - `data-repo`, `data-repo-id`, `data-category`, `data-category-id`
   - `data-mapping`: pathname-based (maps URL path to GitHub Discussion)
   - `data-strict`: 0 (allow discussion creation on new pages)
   - `data-reactions-enabled`: 1
   - `data-input-position`: bottom
   - `data-theme`: dynamic (light or dark based on site palette)
   - `data-lang`: configurable (default: `en`)

### Theme Sync

A `MutationObserver` watches `document.body` for `data-md-color-scheme`
attribute changes (triggered by the Material theme toggle):

```javascript
observer.observe(document.body, {
  attributes: true,
  attributeFilter: ['data-md-color-scheme']
});
```

On change:

1. Clears the previous timer (100ms debounce via `el._themeTimer`)
1. Removes the old Giscus iframe by clearing `innerHTML`
1. Re-creates the `<script>` tag with the correct theme (`light_theme` or
   `dark_theme` from config)

This full destroy-reload cycle is necessary because Giscus doesn't support
runtime theme swapping without reinitialization.

### Theme Override: `overrides/main.html`

Extends the base Material theme template to:

- Add Google Site Verification meta tag
- Embed `GIT_HASH` in a `<meta name="git-hash">` tag (when `config.extra.git_hash` is set)
- Auto-set `target="_blank"` + `rel="noopener noreferrer"` on all external
  links via a small inline script

## Configuration (`mkdocs.yml`)

```yaml
extra:
  comments:
    enabled: true
    repo: xiongjia/xiongjia.github.com
    repo_id: MDEwOlJlcG9zaXRvcnkxMjM4MjI0NQ==
    category: General
    category_id: DIC_kwDOALzwJc4DCO5O
    mapping: pathname
    lang: en
    light_theme: light
    dark_theme: dark
```

## Setup (one-time)

1. **Enable GitHub Discussions** on the repository settings page
1. **Install the [Giscus GitHub App](https://github.com/apps/giscus)** and
   grant access to the repository
1. **Get `repo_id` and `category_id`**:
   - Visit [giscus.app](https://giscus.app/), enter repo name, follow guided form
   - Or query via [GitHub GraphQL API](https://docs.github.com/en/graphql/overview/explorer):
     ```graphql
     { repository(owner: "xiongjia", name: "xiongjia.github.com") { id } }
     { repository(owner: "xiongjia", name: "xiongjia.github.com") {
         discussionCategory(name: "General") { id }
       }
     }
     ```
1. **Update `mkdocs.yml`** with the obtained values

## Testing

```bash
uv run poe server
# Visit http://localhost:8000/discuss/
# Verify: Giscus comment box visible
# Test: Toggle light/dark theme — widget follows
# Test: Visit other pages — comments should NOT appear
```

## Edge Cases

- **Config disabled** (`enabled: false`): No Giscus script loaded
- **No `comments` frontmatter**: No comment section rendered
- **Theme toggle race condition**: 100ms debounce timer prevents rapid
  reloads during quick theme switching
- **Giscus CDN failure**: Comment section simply doesn't load (visible as
  empty container, graceful degradation)

## Dependencies

| Service                       | Usage                                          |
| ----------------------------- | ---------------------------------------------- |
| [Giscus](https://giscus.app/) | Comment system (GitHub Discussions as storage) |
| GitHub Discussions            | Backend storage for comments                   |
