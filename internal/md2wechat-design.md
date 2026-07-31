# md2wechat — Design Document

> Convert MkDocs Markdown articles to WeChat Official Account-compatible HTML.

## Overview

A CLI tool that transforms MkDocs blog posts into HTML suitable for the WeChat
Official Account (微信公众号) editor. It handles MkDocs-specific syntax
(admonitions, tabs, tasklists, footnotes, etc.) that WeChat's editor does not
support, converting them to plain-text or emoji-based equivalents.

## Input / Output

- **Input**: Any Markdown file with YAML frontmatter. Supports:
  - Direct file path argument
  - Interactive selection (lists published non-draft posts from `docs/notes/posts/posts/`)
  - `--open` flag to preview in browser
- **Output**: Multiple output modes:
  - Rich-text clipboard (macOS `textutil` + `pbcopy`) — paste directly into WeChat editor
  - Raw HTML clipboard (`pyperclip`) — fallback when rich-text fails
  - `--preview-only` — print HTML to stdout
  - `--no-copy` — print without clipboard
  - `--raw` — copy raw HTML source instead of rich text

## Pipeline

```
Markdown file
    │
    ▼
Frontmatter parser (python-frontmatter)
    ├── title → HTML <title>
    ├── draft? → reject if draft: true
    └── content → body text
    │
    ▼
Preprocessors (applied in order):
    1. preprocess_tasklist()     — [x] / [ ] → ✅ / ⬜
    2. preprocess_admonition()   — !!! type → emoji + bold title + <p> body
    3. preprocess_tabs()         — === "Tab" → flatten, unindent
    4. preprocess_mkdocs_attrs() — remove {:target="..."} syntax
    5. preprocess_abbreviation() — remove *[ABBR]: ... lines
    │
    ▼
Markdown renderer (markdown-it-py + footnote plugin)
    └── Custom WeChatRenderer class
        ├── fence()         — code blocks → placeholder ("screenshot and upload")
        │                     Mermaid blocks → placeholder
        ├── image()         — local images → placeholder with dimensions
        │                     remote images → <img> with max-width style
        ├── renderToken()   — collects external links for warnings
        └── footnote rules  — superscript refs, <hr> + <ol> list, no backrefs
    │
    ▼
Post-processor: _clean_for_wechat()
    └── Remove footnote-sep <hr>, redundant <p> wrapping block elements, etc.
    │
    ▼
Output (based on CLI flags)
```

## Preprocessors Detail

### `preprocess_admonition`

- Handles `!!! type "title"`, `!!! type`, `???`, `???+` variants
- Emoji mapping: `note`→📌, `info`→ℹ️, `tip`→💡, `success`→✅, `warning`→⚠️,
  `danger`/`error`→🚫, `bug`→🐛, `example`→📝, `quote`→💬, `question`→❓,
  `abstract`→📋
- Output: `<p><strong>{emoji} {title}</strong><br>{body}</p>`
- Stops at blank line, heading, or another admonition boundary
- Must run BEFORE `preprocess_tabs()` because tabs remove 4-space indent that
  admonition body detection relies on

### `preprocess_tabs`

- Removes `=== "TabName"` header lines
- Removes 4-space indent from nested content
- Flattens all tabs into a single continuous block

### `preprocess_tasklist`

- `- [x]` / `- [X]` → ✅
- `- [ ]` → ⬜
- Consecutive task items joined by `<br>` instead of newlines

### `preprocess_mkdocs_attrs`

- Removes `{:target="_blank"}` and similar attribute syntax

### `preprocess_abbreviation`

- Removes `*[ABBR]: definition` lines

## Custom Renderer (WeChatRenderer)

Extends `markdown_it.RendererHTML` with WeChat-specific handling:

### `fence()`

- Regular code blocks: `<p style="...">📄 Code block [lang] — screenshot and upload</p>`
- Mermaid blocks: `<p style="...">📊 [Mermaid] Screenshot and upload</p>`

### `image()`

- Local images (`src` does not start with `http://`/`https://`):
  - Reads dimensions via PIL (if available)
  - Outputs placeholder: `📷 [alt] (WxH)<br><small>Upload to WeChat media library...</small>`
  - Tracks in `_local_images` for warnings
- Drawio images (`.drawio` extension): placeholder: `📊 [Drawio: alt] Screenshot and upload`
- Remote images: `<img src="..." alt="..." style="max-width:100%;height:auto;">`

### Footnotes

- `footnote_ref`: `<sup style="color:#448aff;">[n]</sup>`
- `footnote_block_open`: `<hr><ol>`
- `footnote_block_close`: `</ol>`
- `footnote_open` / `footnote_close`: `<li>` / `</li>`
- `footnote_anchor` / `footnote_caption`: empty string (no backref links)

### Warnings Collection

After rendering, `get_warnings()` aggregates:

- Local images needing manual upload
- External links (not clickable in WeChat)
- Mermaid diagrams needing screenshot
- Drawio diagrams needing screenshot
- Footnotes conversion note
- Admonition simplification note
- Code line numbers removed

## CLI Usage

```bash
# Interactive post selection
uv run poe md2wechat

# Direct file path
uv run poe md2wechat docs/notes/posts/posts/bits/20260101-my-post.md

# Preview only (no clipboard)
uv run poe md2wechat path/to/file.md --preview-only

# No clipboard copy, print to stdout
uv run poe md2wechat path/to/file.md --no-copy

# Copy raw HTML source instead of rich text
uv run poe md2wechat path/to/file.md --raw

# Open preview in browser
uv run poe md2wechat path/to/file.md --open
```

## Edge Cases

- **Draft posts**: Rejected with error message — remove `draft: true` first
- **No published posts**: Error when using interactive mode
- **Rich text failure** (macOS `textutil`/`pbcopy` unavailable): Falls back to `pyperclip` HTML source copy, or stdout
- **Cross-platform paths**: Uses `os.path.normpath` for local image path resolution
- **Remote images**: Embedded directly (assumes no hotlink protection on CDN)
- **PIL unavailable**: Image dimensions omitted from placeholder

## Dependencies

| Package                     | Usage                                      |
| --------------------------- | ------------------------------------------ |
| `markdown-it-py`            | Markdown → HTML rendering                  |
| `mdit-py-plugins`           | Footnote plugin                            |
| `python-frontmatter`        | YAML frontmatter parsing                   |
| `pyyaml`                    | YAML parsing                               |
| `pyperclip`                 | Clipboard copy fallback                    |
| `Pillow`                    | Image dimension reading                    |
| macOS `textutil` + `pbcopy` | Rich-text clipboard (optional, macOS only) |
