---
title: Collection Scrape — daily capture + periodic organize
created: 2026-08-18
archived: 2026-08-18
status: completed
tags: [collection, scrape, bot, ai-archive]
---

# Collection Scrape — daily capture + periodic organize

## One-liner

Unified inbox for **fragments from everywhere** (random ideas, TODOs, books to
read, links, notes) → AI organizes and **directly appends** to the existing
`collection/<domain>.md` pages (for resources) or to a visible
`collection/scraps/plans.md` (for TODOs / ideas).

No intermediate archive — the collection pages and plans page ARE the
archive.

## Background

- `docs/notes/collection/` already exists: hand-curated link pages organized by
  domain (dev-tools, ai, database, etc.). But there is **no capture entry
  point** — good finds get lost.
- `internal/plans/english-scraps.md` has a mature pipeline (inbox → organize →
  archive/week files). This plan reuses the **capture → organize** part but
  skips the archive layer: collection items go straight into the curated pages.
- **Gap**: tech bookmarks, books to read, product ideas, TODOs, RSS articles,
  etc. are scattered across browsers, Raindrop/Pocket, phone notes, WeChat —
  no unified capture.

## vs. English Scraps

| Dimension        | English Scraps                   | Collection Scrape                                                      |
| ---------------- | -------------------------------- | ---------------------------------------------------------------------- |
| Content          | words, grammar, sentences        | links, tools, books, ideas, articles, TODOs                            |
| Taxonomy         | `type` (word/grammar/…)          | `domain` + `type` (link/book/idea/todo/note)                           |
| Final sink       | archive week files               | `collection/<domain>.md` (resources) + `scraps/plans.md` (TODOs/ideas) |
| Archive          | yes (week files)                 | **none** — pages are the archive                                       |
| External sources | none                             | none (manual capture only)                                             |
| Commands         | `poe enu` / `enu-organize` skill | `poe collect-add` / `collect-organize` skill                           |
| Visibility       | public (archive)                 | public (plans.md visible in nav)                                       |

## Workflow

```text
Manual capture ──> inbox ──> AI organize ───> collection/<domain>.md  (link / book / note)
  (ideas/TODO/books)         (staging)  (batch)  └──> scraps/plans.md  (todo / idea)
```

## Content layout

```text
docs/notes/collection/
├── index.md                  # entry page + capture usage guide
├── dev-tools.md              # existing curated pages
├── ai.md
├── database.md
├── ...
│
└── scraps/                   # capture zone
    ├── inbox.md              # 📥 raw fragments (draft: true)
    └── plans.md              # 📋 visible plan list (TODOs / ideas, deletable)
```

## Taxonomy

### domain (maps to existing collection pages)

| domain        | collection page        | examples                          |
| ------------- | ---------------------- | --------------------------------- |
| dev-tools     | `dev-tools.md`         | CLI tools, RPC frameworks, DevOps |
| ai            | `ai.md`                | LLM tools, MCP, AI CLI            |
| database      | `database.md`          | SQLite extensions, KV stores      |
| media         | `media.md`             | streaming, automation             |
| monitor       | `monitor.md`           | Prometheus, APM                   |
| frontend      | `frontend.md`          | React, UI frameworks              |
| languages     | `languages.md`         | Go, Rust, Java toolchains         |
| game-dev      | `game-dev.md`          | Godot plugins, Krita brushes      |
| maps          | `maps.md`              | MapLibre plugins, PMTiles         |
| emoji         | `emoji.md`             | rarely needed                     |
| uncategorized | appended to `index.md` | fallback section                  |

### type

| type | meaning                   | target                   | append format                                     |
| ---- | ------------------------- | ------------------------ | ------------------------------------------------- |
| link | URL / tool recommendation | `collection/<domain>.md` | `- [<title>](<url>) — <description>`              |
| book | to-read or read           | `collection/<domain>.md` | `- 📖 <title> — <author>`                         |
| note | reading note / summary    | `collection/<domain>.md` | `- 📝 <title> — <summary>`                        |
| todo | task / plan               | `scraps/plans.md`        | `- <date> <task>` (under `### 📋 TODOs`)          |
| idea | product / project idea    | `scraps/plans.md`        | `- 💡 <title> — <context>` (under `### 💡 Ideas`) |
| misc | unclassifiable            | `scraps/plans.md`        | `- <content>` (under `### 📦 Misc`)               |

Items on `plans.md` can be freely deleted when done or abandoned — no
commitment.

## Capture channels

### 1. Manual

```bash
poe collect-add "content" [--source <source>] [--url <url>]   # resource → inbox
poe collect-todo "content"                                     # TODO → plans.md
poe collect-idea "content"                                     # idea → plans.md
```

### 2. pi skill

```
/skill:collect-organize add <content>   # resource only
```

`todo` / `idea` use the CLI directly (no AI needed).

### 3. Telegram bot

```
/collect <content>
/collect_todo <content>
/collect_idea <content>
```

## AI organize flow

Trigger (any of): inbox ≥ 15 lines / ≥ 2 weeks since last organize / explicit
`/skill:collect-organize arch`.

1. Read all inbox entries
1. Classify by `type` (link/book/note/todo/idea/misc) and `domain` (match
   against existing collection page names)
1. **Deduplicate**: check target page for existing URL or title match; skip
   duplicates
1. **Route** by type:
   - `link` / `book` / `note`: append to `collection/<domain>.md`
   - `todo` / `idea` / `misc`: append to `collection/scraps/plans.md`
1. Clean inbox (remove processed entries)
1. Update `collection/index.md` last-organized date
1. Report: N items appended (by target + by type) + items needing confirmation

### Dedup rules

- **Primary key**: URL (check target page for the URL)
- **Secondary key**: title text (fuzzy match for items without URL)

### Append format: resources (link / book / note → `<domain>.md`)

- `link`: `- [<title>](<url>) — <description>` (main list)
- `book`: `- 📖 <title> — <author>` (under `### 📚 Reading`; create if missing)
- `note`: `- 📝 <title> — <summary>` (under `### 📝 Notes`; create if missing)

### Append format: plans (todo / idea → `plans.md`)

- `todo`: `- <date> <task>` (under `### 📋 TODOs`; create if missing)
- `idea`: `- 💡 <title> — <context>` (under `### 💡 Ideas`; create if missing)
- `misc`: `- <content>` (under `### Misc`; create if missing)

## Toolchain

### CLI

```bash
poe collect-add "content"                    # resource → inbox
poe collect-add "content" --source manual
poe collect-add "content" --date 2026-08-01
poe collect-todo "看这个视频"                   # TODO → plans.md
poe collect-idea "用 MapLibre 做热力图"         # idea → plans.md
```

Script: `scripts/collect.py` (subcommands: `add`, `todo`, `idea`).

### pi skill

`.pi/skills/collect-organize/SKILL.md`:

| Trigger         | Action                                                          |
| --------------- | --------------------------------------------------------------- |
| `add <content>` | Append to inbox (resource, needs arch)                          |
| `arch`          | Batch organize: classify → dedup → route to pages → clean inbox |

`todo` / `idea` bypass the skill — use `poe collect-todo` / `poe collect-idea` directly.

### Privacy

- `inbox.md`: `draft: true` (not on production)
- External tool credentials: `.env` only, **never committed**

## Tasks

### Phase 1 — Foundation

- [x] Create `collection/scraps/` structure (index.md / inbox.md)
- [x] `inbox.md` with `draft: true` + format instructions
- [x] Update `docs/notes/collection/index.md` with capture usage + Plans link
- [x] Create `collection/scraps/` (inbox.md + plans.md; scraps/index.md removed as redundant)
- [x] `scripts/collect.py` + poe tasks `collect-add` / `collect-todo` / `collect-idea`
- [x] `pyproject.toml`: add poe task `collect`

### Phase 2 — AI organize

- [x] `.pi/skills/collect-organize/SKILL.md` (classify + dedup + append to collection pages)
- [x] `arch` action: read inbox → classify → dedup → append to `<domain>.md` → clean inbox

### TODO lifecycle (suggestion)

`plans.md` is a **transient staging area**. Items flow in from inbox, and flow
out when acted upon. Simple rule:

- **Done / abandoned** → delete the line from `plans.md`
- **Promoted to something more** → delete from plans.md, create the target

Common transitions:

| From | To              | Action                                                   |
| ---- | --------------- | -------------------------------------------------------- |
| TODO | Research topic  | Delete line, create `docs/notes/research/topics/<name>/` |
| TODO | Blog post       | Delete line, `poe create-post "Title"`                   |
| TODO | Moment          | Delete line, `poe create-moment "Text"`                  |
| TODO | Collection item | Delete line, append to `collection/<domain>.md` directly |

No automation needed — the line deletion is the signal that the item has been
handled. AI can help with a `move` action if useful later.

### Phase 3 — Plans page (visible TODO/Idea board)

- [x] Create `collection/scraps/plans.md` with TODOs / Ideas / Misc sections
- [x] Add `plans.md` to mkdocs nav

### Phase 4 — Bot API + Telegram

- [x] Register `collect` task in mkdocs.yml `extra.bot.tasks`
- [x] Telegram `/collect <content>` command (`api/routers/tg.py`)
