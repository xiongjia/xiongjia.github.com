# Reading Assistant — Design Document

> AI chapter-level reading assistant: a skill (`.pi/skills/reading-assist/`) +
> a **dedicated queue file** `internal/plans/reading-items.md` (`## Reading Items`
> entries + `## 记录（Log）` 完成/失败 sections — separate from the dev plan
> `internal/plans/arch/reading-assist.md`, which keeps design + tasks only).
> **Manual, on demand** — there is deliberately no cron/bot auto-run, because
> analysis quality needs the user to review and adjust the produced notes by
> hand. On `poe reading-assist run` the assistant takes the raw material
> (article URL or a local pdf/epub), produces `docs/notes/reading/<slug>/`
> chapter summaries + `notes.md`, self-reviews (≤ 10 rounds), marks the entry
> `organized` and writes a done/fail/abort record to the queue file (one line
> per (slug, result) — refreshed on rerun, never growing). Book source files
> never enter the repo; extracted sources stay in a **local cache** that the
> script never deletes.

## Overview

```
Reading Items (internal/plans/reading-items.md) ──► skill `read` ──► raw material
  slug / type / state                          web: URL (script pre-fetches)
  + Log (完成/失败/放弃 records)               local: pdf/epub (pymupdf→pypdf / zipfile)
                                  │
                                  ▼
   docs/notes/reading/<slug>/  (index / ch-0001… / part-0001… / notes,
                                + characters / storyline for novels)
                                  │
        self-review ≤ 10 rounds → mdformat → poe fmt → CI green
                                  │
        entry: not-started → reading → organized (整理完成) + Log record
                                  │
        user reviews & adjusts notes → commits manually (no auto PR)
```

The pipeline reuses the proven `inbox → AI organize → archive → self-check`
pattern of `english-scraps` / `enu-organize`, but the "inbox" is the
machine-readable `## Reading Items` section of **`internal/plans/reading-items.md`**
— a queue file, deliberately separate from the dev plan so entries and run
history never mix with development tasks.

## Design Decisions

### Queue file, separate from the dev plan

- **`internal/plans/reading-items.md`** is the machine-readable queue: a template
  comment block (kept commented — the parser skips it), the
  `## Reading Items` section with `### <slug>` entries (each carrying
  `slug / 类型 / 出处 / 状态 / 原材料 / 输出`), and a `## 记录（Log）` section
  (`### 完成（Organized）` / `### 失败 / 放弃（Failed / Aborted）`) for run
  outcomes
- **`internal/plans/arch/reading-assist.md`** is the dev plan (design + tasks +
  pilot record only) — it no longer holds entries or run history, so reading
  data never mixes with development tracking
- Both are referenced by `scripts/reading_assist.py` / the skill; the queue
  file is machine-parsed (entries from `## Reading Items`; the Log is never
  parsed), the dev plan is only referenced
- Adding an item = adding one entry block (see `internal/commands.md` →
  「新增阅读项」); removing = deleting the block. Outcome records (done / fail /
  abort) are written by the script to the Log section — one line per (slug,
  result), refreshed on rerun, so the log does not grow with repeated runs

Because the skill/script read the queue file as live data, entries live in a
plain markdown file that is not submitted to the plan-archive lifecycle; the
dev plan itself follows the normal archive convention when done.

### Skill spec: read / ask / done

- `read <slug|标题>` — main flow: pick an item → fetch raw material → build the
  full page set → self-review ≤ 10 rounds → mdformat → report (item state →
  `organized`)
- `ask <slug> <问题>` — post-reading Q&A / summary edits / manual notes as a
  **suggestion draft**; respects existing content (never overwrites user-edited
  pages)
- `done <slug>` — user marks "finished reading" on the overview (organizing
  state stays `organized`)

`ask`/`done` are interactive skill actions (not script subcommands); their
verification was consciously deferred/taken off the plan after the pilot — the
actions remain specified in the skill but are exercised by the user during real
reading.

### Input modes — only URL or local file

| Mode         | Purpose                                        | Acquisition                                                                                                                                                             |
| ------------ | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `web`        | articles / tutorials / papers                  | script pre-fetches each URL to `$READING_CACHE_DIR/<slug>/source-01.html…` (`curl -S -L -m 20`, browser UA, muted retries ≤ 3 with 2s/4s backoff — anti-robot courtesy) |
| `local-file` | books / novels (primary for long-form reading) | user gives a **local pdf/epub filename/path** under the git-ignored `external/`; AI reads it on this machine                                                            |

Files live under the git-ignored `external/` (conventionally `external/book/`,
never committed). `原材料` accepts three forms: an explicit `{projectRoot}/…`
path (e.g. `{projectRoot}/external/book/1.pdf` — the placeholder is replaced
with the repo root, so no directory convention is required and it works from
any checkout), a relative path (tried in order: repo root, `external/<path>`,
`external/book/<path>`), or an absolute path (passed through). Because runs
are manual (no bot worktree), paths resolve directly against the checkout
where the user runs the script.

**Multiple sources (series)**: one 原材料 field may hold several sources
separated by spaces. For article/paper that is a series of URLs — the script
checks reachability of **each** URL and pre-fetches each to
`source-01.html…`; the assistant writes one `part-000N.md` per article and
keeps cross-article concepts in `notes.md` (series 主线 in `index.md`). For
book/novel it is a set of volume files — each file = one volume → one
`part-000N` page. Any source unusable → the whole item aborts.

- No pasted text: the two accepted inputs are **URL** or a **local pdf/epub
  file name** — reading local files is *reading, not uploading*
- Source files are **never committed / pushed**: only summaries + short excerpts
  (≤ 10 lines each) land in `reading/<slug>/`; the entry's 出处 records the
  bibliographic info (Douban / URL / DOI), never the local path
- Extraction (uv-managed, cross-host): epub = stdlib `zipfile` (toc/spine
  splitting, zero deps); pdf = `pymupdf` (first choice) → `pypdf` (pure-Python
  fallback). Runs as `uv run --with pymupdf --with pypdf python …` — first run
  downloads + caches, later runs offline; no apt/brew needed on Linux/macOS
- Chapter splitting with degradation: split by book TOC (epub toc/spine, pdf
  bookmarks) into `ch-0001…`; **no TOC (scanned / bookmark-less PDF) → degrade**
  to page/volume groups `part-0001…` (or a single whole-book note) — never
  abort for missing structure; abort only if the file is unparseable/corrupt

### Content boundaries & naming (enforced)

- File/dir names: only `[a-z0-9-]` (lowercase + digits + hyphen) — slug and
  files; chapter numbers zero-padded (`ch-0001`, `part-0001`); human titles go
  in frontmatter, never in filenames
- Every page: frontmatter `title` / `tags` / `categories: [reading]`;
  relative links between pages; reading sub-pages add `hide: [navigation]`
  (sidebar = TOC + 「← 返回 Reading」, matching knowledge pages)
- Sensitive info (API keys, local passwords, personal data) stripped/shortened —
  never on public pages
- Expression: concise **lists** over long prose; the whole-book storyline is
  a **list by default — no mermaid**; mermaid (flowchart/timeline) is allowed
  for structure/flow only with short node labels (≤ 10 chars, details in the
  list), `timeline` rendering is build-time verified, with flowchart as
  documented fallback

### Page set & templates

```
<slug>/
├── index.md        # 书目入口: type / status / author / source + 全书主线 + links
├── ch-0001.md      # book chapter summaries (ch-0001, ch-0002, …)
├── part-0001.md    # web long-form split into parts (+《原文链接》row)
├── characters.md   # novels: name kept in original language + mermaid relation graph
├── storyline.md    # novels: mermaid timeline/flowchart of plot arcs & turning points
└── notes.md        # cross-chapter concepts (定义/出现章节/关联/延伸)
```

Chapter template: `原书章节` / `阅读日期` / `输入来源` + `摘要` (中文正文,
英文原词术语不翻译) + `要点归纳` (list) + `术语/概念` + `原句摘录`
(book mandatory, ≤ 10 lines) + `疑问/待查`. `notes.md` carries cross-chapter
concepts; the whole-book 主线 lives in `index.md`.

### Status semantics: organizing progress ≠ finished

`not-started → reading → organized` tracks **organizing** (AI produced the
notes), not user reading progress. The state is maintained in **one place** —
the `## Reading Items` entries in the plan (and mirrored in the
`reading/index.md` overview per type); item `index.md` frontmatter deliberately
does **not** duplicate it (avoids dual drift). "Finished reading" is marked by
the user via `done` on the overview, with organizing state kept at `organized`.

### Self-review loop (≤ 10 rounds)

After `read` output, a forced review cycle (`review_loop` tool
`maxIterations: 10`, fresh context each round):

1. sensitive info — must be zero
1. logic & completeness — no missing chapters; each chapter has 摘要 + 要点;
   concepts have 定义 + 出处
1. consistency — English original terms consistent; slug / links / naming match
1. format & CI — frontmatter complete, mdformat passes, MkDocs build passes
   (incl. mermaid render); no `\*\*`-style escaped-bold residue (known pilot
   friction point, now a checklist item)

must-fix → fix → fresh-eyes re-check; same issue twice in a row → stop and ask
the user. A pilot-round self-review genuinely caught & fixed an issue (escaped
bold), so the gate is not a walk-through. Optionally combined with the
`code-review` skill (content dimension there, reading-specific items here).

### CLI & automation

`poe reading-assist` (script `scripts/reading_assist.py`, kebab-case CLI name,
snake_case file):

| Subcommand           | Behavior                                                                                                                                     |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `list`               | List Reading Items with slug / type / state / source                                                                                         |
| `cache [slug]`       | Step 1: fetch/extract the raw material into the local cache (`CACHE_DIR/<slug>/`), no AI — repeatable, reuses existing cache                 |
| `read [slug]`        | Step 2: AI analysis on the cached sources → local `pi -p --mode json` runs the skill flow → write `reading/<slug>/` → mark entry → `poe fmt` |
| `run [slug]`         | `cache` + `read` in one go (backwards compatible)                                                                                            |
| `read/run --dry-run` | Print selected item + prompt, no AI call                                                                                                     |
| `read/run --model …` | Pin the pi model (default: local config)                                                                                                     |

**No scheduling, no bot**: reading runs are manual only (no `extra.bot.cron`
job, no `git_bot` task). The user runs `cache` then `read` (or `run` for
both) when they want, edits `docs/notes/reading/<slug>/` by hand (AI quality
needs human review), and commits on their own schedule. AI/scripts never push.
Splitting `cache` from `read` lets the user inspect the extracted sources and
tune the raw material before spending AI tokens.

### Abort branches (silent, zero output)

Any of: no Reading Items / local file missing / pdf·epub unparseable
(pymupdf/pypdf unavailable or corrupt) / URL unreachable → exit 0 with **no**
pages. `no items` also writes **no** record (idle state); an
abort against an existing item writes one `放弃` line to the queue Log (so an
unusable source is traceable; refreshed per slug on rerun), a mid-run failure
writes one `失败` line (also refreshed).
Outcome records live only in `internal/plans/reading-items.md` — never in the dev
plan.

### Proxy

URL fetch uses `READING_PROXY` (`.env`, per-machine via `shared/env.py`),
falling back to `$https_proxy` → default local proxy `http://127.0.0.1:1095`.
Local cache `READING_CACHE_DIR/<slug>/` (default system temp, never in-repo)
holds the fetched html + stripped txt sources. The script **never deletes**
the cache — the user may re-read or re-extract a pdf/epub while adjusting
notes; removal is manual.

## Testing

`tests/test_reading_assist.py` (no pi invocation, offline):

- Reading Items parsing (Chinese key names, commented template skipped, empty
  items → abort)
- Item picking: first `not-started`; `organized` skipped
- Validation: missing local file / unreachable URL / invalid slug / empty
  source → reject
- Output index resolution honors the entry's 输出 (falls back to slug)
- `mark_organized` touches only the target item and stays scoped to the
  Reading section
- Temp cleanup guards invalid slug; removes item dir; run failure (validate /
  no index / mdformat fail) cleans tmp; mdformat failure keeps pages for
  inspection but unmarks the item
- Success path: marks item + cleans tmp; `--dry-run` never touches tmp

## Non-Goals

- Pasting original text into chat — inputs are URL / local file only
- Committing book source files or full-text quotes (excerpts ≤ 10 lines)
- Build-time AI generation (offline, deterministic builds — AI runs on demand
  only, same rule as `update-health-summary`)
- Replacing `reading-list.md` (long-term wishlist) or `collection/reading.md`
  (Study Materials) — items migrate in only when actually starting to read

## Related

- Queue file (entries + Log records): `internal/plans/reading-items.md`
- Dev plan (design + tasks + pilot record): `internal/plans/arch/reading-assist.md`
- Skill spec: `.pi/skills/reading-assist/SKILL.md`
- Command reference: `internal/commands.md` → Reading
- Archive: `docs/notes/reading/index.md`
- Sibling on-demand-AI pattern: `internal/health-summary-design.md`
- [Architecture — Design Documents](./architecture.md#design-documents)
