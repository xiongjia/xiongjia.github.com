# Bot Remote API — Design Document

> Remote management entry point: HTTP API + Web console + Telegram Bot, all
> invoking the local `git_bot.py` execution engine.
>
> Core principle: the API layer is a thin shell — all business logic
> (worktree isolation, CI gate, PR flow) stays in `scripts/git_bot.py`; the
> remote layer only handles serialization and protocol adaptation.

> **Status (2026-08-14)** — English translation of the original design.
> Implementation has diverged from this document in several places; the
> authoritative plan is `internal/plans/bot-remote-api.md` (Findings section
> catalogs every discrepancy). Key divergences:
>
> - **No auth layer** (dev decision): API Key / IP whitelist / TG webhook
>   secret token are all removed. Bind to localhost / a trusted network.
> - **Default port 8100** (8000 belongs to the mkdocs dev server).
> - **Handoff-only** (dev decision): `auto_merge` is not in the API
>   contract; every run ends in a draft PR. The console has a Handoff
>   checkbox (off = `--wait-ci`, still draft, never merges).
> - Task list is **derived from the engine** (`mkdocs.yml extra.bot.tasks`
>   - `git_bot.TASKS`), not a hardcoded `TASK_SCHEMAS` dict.
> - Runtime data lives in `.bot-api/` (configurable via `BOT_API_LOG_DIR`):
>   `history.jsonl` (+ rotation) and `uploads/` staging.
> - Engine gained sanctioned exceptions: rest-arg template args
>   (`args: [text...]`) and a push retry in `push_branch` (3 attempts on
>   transient proxy connection errors). The planned `--stage-dir` copy-in
>   flag (uploads, Phase 2) was **dropped** — `create_moment` now converts
>   - uploads to R2 itself, so staged files never need to enter the
>     worktree.
> - `create-post` category options are `bits/dev/thought` (not `life`).
> - Task scheduling (cron) was originally dropped, then **implemented
>   (2026-08-21)** — mkdocs.yml `extra.bot.cron` + APScheduler in the API
>   process (see `internal/plans/arch/bot-cronjob.md`); console image
>   uploads landed as a base64 JSON staging endpoint (`POST /api/upload`
>   → `.bot-api/uploads/`, no multipart dependency).
> - **Telegram scope (dev decision, 2026-08-17)**: allowlisted users only
>   (`TG_ALLOWED_USER_IDS`), three tasks — `/weight`, `/enu`, simplified
>   `/moment` (text + multiple photos); no `/post` dialog, no `/sync`/
>   `/health`/`/status`; completion pushed to the issuing chat. Replies
>   in English; photo-only `/moment` allowed (empty text + `--no-editor`,
>   a new create_moment flag); `/weight` defaults to today; concurrent
>   runs allowed; completion push is one-way (PR link, no reply). The
>   Telegram design section below is outdated and superseded by the plan.

## Goals

1. **Web console**: open the browser to trigger bot tasks, watch logs live,
   and browse history.
1. **Telegram Bot**: one-tap execution from the phone (e.g.
   `/weight 82`), with multi-step dialogs (e.g. `/post` → title → content).
1. **Unified execution layer**: Web and TG both go through the same
   `POST /api/bot/run` → `poe bot ...` pipeline.
1. **Zero extra servers**: a single FastAPI process serves HTTP + webhook,
   sharing one event loop.
1. **Security**: API Key + IP whitelist double protection; the TG Bot
   validates the webhook via Telegram's secret token.
   *(Superseded: auth removed by dev decision — see status note.)*

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                             Client layer                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐  │
│  │  Browser    │    │  curl/httpie │    │  Telegram App              │  │
│  │  (console)  │    │  (script)    │    │  (/weight, /sync, ...)     │  │
│  └──────┬──────┘    └──────┬──────┘    └─────────────┬───────────────┘  │
└─────────┼──────────────────┼─────────────────────────┼─────────────────┘
          │ HTTPS            │ HTTPS                   │ HTTPS POST
          │                  │                         │ /webhook
┌─────────▼──────────────────▼─────────────────────────▼─────────────────┐
│                         FastAPI Server (single process)                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  StaticFiles  /  (index.html, css, js)  → Web console          │   │
│  │  Router       /api/*  → REST API                                │   │
│  │  Router       /webhook  → Telegram webhook handler              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                    ┌─────────▼──────────┐                               │
│                    │  api/routers/bot.py │  arg validation + async sched│
│                    │  api/routers/tg.py  │  TG command routing + dialog │
│                    └─────────┬──────────┘                               │
│                              │ subprocess / asyncio                     │
│                    ┌─────────▼──────────┐                               │
│                    │ scripts/git_bot.py  │  worktree / CI / PR / merge  │
│                    │ (existing, zero mod)│                              │
│                    └────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────┘
```

## Directory Layout

```
xiongjia.github.com/
├── api/                              # remote API service (new)
│   ├── __init__.py                   # repo-root bootstrap + .env loading
│   ├── server.py                     # FastAPI app + lifespan
│   ├── config.py                     # pydantic-settings (BOT_API_*)
│   ├── models.py                     # request/response models + task schema
│   ├── lifespan.py                   # startup cleanup, graceful shutdown
│   ├── state.py                      # in-memory: active runs + log queues
│   ├── history.py                    # file persistence (.bot-api/history.jsonl)
│   ├── executor.py                   # subprocess scheduling + outcome detection
│   ├── uploads.py                    # console image upload staging (base64 JSON)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── bot.py                    # POST /api/bot/run, status, stream, history, abort
│   │   ├── system.py                 # /api/health, /version, /schema/:task, /tasks
│   │   └── tg.py                     # Phase 2: POST /webhook + command routing
│   └── static/                       # Web console (pure static SPA)
│       ├── index.html
│       ├── css/
│       │   └── app.css
│       └── js/
│           └── app.js
│
├── scripts/
│   ├── git_bot.py                    # local bot (existing; sanctioned exceptions)
│   └── api_server.py                 # uvicorn launcher (new)
│
├── shared/                           # reused modules
│   ├── github_api.py
│   └── env.py
│
├── internal/
│   ├── bot-api-design.md             # this document
│   └── plans/bot-remote-api.md       # the authoritative plan
│
├── tests/
│   └── api/                          # API tests
│       ├── test_bot_router.py
│       ├── test_system.py
│       ├── test_executor.py
│       ├── test_history.py
│       └── test_tg_webhook.py        # Phase 2
│
├── pyproject.toml                    # modified: [api] extras + poe tasks
├── .env.example                      # modified: server + TG_* config
└── .bot-api/                         # runtime data (git-ignored; BOT_API_LOG_DIR)
    ├── history.jsonl                 # run history (30-day rotation)
    └── uploads/                      # console upload staging
```

## Dependencies

```toml
# pyproject.toml — deps live in [project.dependencies]; no extras so a
# plain `uv sync` is enough on any machine (no --extra bookkeeping, no
# venv churn between `poe test` and `poe api-server`).
"fastapi>=0.115.0",
"uvicorn[standard]>=0.32.0",
"python-telegram-bot>=20.6",             # added in Phase 2
"pydantic-settings>=2.0.0",              # config management
"pytest>=9.1.1",
"httpx>=0.27.0",                         # FastAPI TestClient

[tool.poe.tasks]
# existing ...
bot = { cmd = "python scripts/git_bot.py", help = "Local bot CLI" }

# added
api-server = { cmd = "uv run python scripts/api_server.py", help = "Start remote API (binds 0.0.0.0; BOT_API_HOST overrides)" }
api-server-prod = { ref = "api-server", help = "Start remote API (prod; alias of api-server)" }
```

Install: `uv sync` (API/test deps in `[project.dependencies]`, no extras)

## Configuration

All config is loaded via env vars / `.env` / `.env.local` (reusing the
`shared/env.py` mechanism).

```bash
# --- Bot API Server ---
BOT_API_HOST=127.0.0.1          # default
BOT_API_PORT=8100               # default (NOT 8000 — mkdocs dev server owns it)
# Runtime data dir: history JSONL + uploads staging (absolute or repo-relative)
BOT_API_LOG_DIR=.bot-api
# Run `poe bot cleanup` for stale worktrees at startup (default true)
BOT_API_STARTUP_CLEANUP=true

# --- Telegram Bot (Phase 2) ---
TG_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxyz
# Webhook mode needs a public URL; polling mode does not
TG_WEBHOOK_URL=https://your-bot.example.com/webhook
# Run mode: webhook | polling (polling for dev, webhook for prod)
TG_MODE=polling
```

## API Design

### 1. Task schema endpoint

The basis for the frontend's dynamic form rendering.

```
GET /api/schema/{task}
```

Response:

```json
{
  "task": "weight",
  "fields": [
    {"name": "value", "type": "number", "label": "Weight (kg)", "step": 0.1, "required": true},
    {"name": "date", "type": "text", "label": "Date (optional)", "required": false}
  ]
}
```

The task list and schemas are **derived from the engine** in the
implementation (`mkdocs.yml extra.bot.tasks` template tasks + builtins in
`git_bot.TASKS`); only UI field metadata lives in `api/models.py`, with a
generic fallback schema for tasks without explicit metadata. The original
hardcoded `TASK_SCHEMAS` dict was replaced (see plan finding 3).

Field types: `text` / `textarea` / `number` / `date` / `select` (fixed
`options`) / `checkbox`, `repeat` (list field — the console collects
multiple added values as an array, forwarded once per value, e.g.
`--meta=rating=4 --meta=name=x`) and `images` (paired rows — each row is
`{path, caption}`, rendered as `[path | caption | ×]` per image; forwarded
as `--image=<path>` / `--image=<path>|<caption>` so a sparse caption stays
with its image). A checkbox may gate a *group* of siblings
via comma-separated `enables` (e.g. moment's "Set coordinates" gates
`lng,lat,crs`); checkbox `emit` picks the flag direction (default
`unchecked`, e.g. create-post's `--no-draft`, or `checked`, e.g. `--draft`).
A coordinate gate (lng+lat) renders a "📍 Use my location" button in the
console that fills them from the browser geolocation API (WGS-84),
auto-checking the gate. Console forms group fields into tabs via `tab`
(labels = first-seen order; moment: Content / Images / Location / Meta);
tasks without `tab` metadata keep a single pane.
Flags are forwarded as a single token `--flag=value` — the bot spec format
(`poe bot run "<task> <args>"`) re-splits on whitespace, so flag values ride
the flag itself; values with spaces are therefore not supported through the
console/API (labels warn: "no spaces").

### 2. Run endpoint

```
POST /api/bot/run
Content-Type: application/json

{
  "task": "weight",
  "fields": {"value": "82.5"},   # or raw "args": ["82.5"]
  "handoff": true                # default; false = --wait-ci (still draft)
}
```

Response (immediate, does not wait for completion):

```json
{
  "run_id": "abc123def456",
  "task": "weight",
  "args": "82.5",
  "status": "running",
  "started_at": "2026-08-14T01:09:00+08:00",
  "stream_url": "/api/bot/stream/abc123def456"
}
```

*(`auto_merge` was removed from the contract — handoff-only, dev decision.)*

### 3. Status query

```
GET /api/bot/status/{run_id}
```

Response:

```json
{
  "run_id": "abc123def456",
  "task": "weight",
  "args": "82.5",
  "status": "submitted",
  "started_at": "2026-08-14T01:09:00+08:00",
  "finished_at": "2026-08-14T01:12:34+08:00",
  "pr_url": "https://github.com/xiongjia/xiongjia.github.com/pull/142",
  "logs": [
    {"time": "01:09:02", "level": "info", "msg": "worktree ready: bot/weight/20260814-0109"},
    {"time": "01:09:05", "level": "ok", "msg": "poe fmt ... ok"},
    {"time": "01:09:14", "level": "ok", "msg": "Draft PR created: #142"}
  ]
}
```

Statuses: `running | submitted | failed | aborted` (handoff-only —
`merged` only appears if someone runs the engine with `--auto-merge`
manually).

### 4. Log stream (SSE)

```
GET /api/bot/stream/{run_id}
Accept: text/event-stream
```

```
data: {"time":"01:09:02","level":"info","msg":"worktree ready..."}

data: {"time":"01:09:05","level":"ok","msg":"poe fmt ... ok"}

data: {"time":"01:09:14","level":"ok","msg":"Draft PR created: #142"}

data: [DONE]
```

The implementation adds a 15 s heartbeat (`: ping`), a `[RESET]` event on
connect (client clears its log pane — reconnect-friendly), and replays the
last 50 log entries.

### 5. History

```
GET /api/bot/history?limit=20&offset=0&q=search
```

### 6. Health

```
GET /api/health          # no auth, for uptime monitoring
GET /api/version         # version + git hash
```

## Web Console Design

Single-page app, pure static files, no build step.

### Page layout

```
┌─────────────────────────────────────────────────────────────┐
│  🤖 Bot Control Panel    ● online    v0.1.0    API docs     │
├────────────────────────┬────────────────────────────────────┤
│  📋 Tasks               │    📡 Live Output                           │
│  💬 text-moment         │    ┌────────────────────────────┐          │
│  ⚖️ weight             │    │ [01:09:02] worktree ready  │          │
│  🏃 sync-running        │    │ [01:09:05] poe fmt ... ok  │          │
│  📝 enu                 │    │ [01:09:14] PR #142 (link)  │          │
│  ❤️ health-summary     │    └────────────────────────────┘          │
│  📰 create-post         │                                            │
│                        │    📜 Recent Runs (clickable)               │
│  ───────────────────── │    ┌────────────────────────────┐          │
│  ⚡ Execute (moment)    │    │ 01:09 weight 82.5 submitted│          │
│  Content [hello …   ]  │    │ 08:15 sync-running failed  │          │
│  Time [   ] Tags [   ] │    │ ... (tooltip: last log)    │          │
│  Image [photo.jpg] ＋   │    └────────────────────────────┘          │
│  Meta [rating=4 ] ＋    │                                            │
│  [✓] draft [ ] no-up   │                                            │
│  [ ] Set coordinates … │                                            │
│  [✓] Handoff [▶ Run Bot]│                                            │
└────────────────────────┴────────────────────────────────────────────┘### Interaction flow

1. **Click a task** → the form renders dynamically from
   `GET /api/schema/{task}`
1. **Fill in args** → the frontend validates required fields
1. **Click Run** → `POST /api/bot/run` → get `run_id` → open an
   `EventSource` to `/api/bot/stream/{run_id}`
1. **Live logs** → SSE lines render to the output pane, colored by level
   (info/ok/err/warn); URLs are auto-linked
1. **History refresh** → auto `GET /api/bot/history` every 30 s or when the
   SSE stream ends; clicking a history row shows its logs (failure reason)

### Frontend files

```

api/static/
├── index.html # skeleton + task list (from /api/tasks)
├── css/
│ └── app.css # dark theme (GitHub dark style)
└── js/
└── app.js # task switching, form rendering, SSE, history

```

**No build tooling**: plain native JS (ES2020), plenty for modern browsers.

### Console verification (no JS test harness)

The console has no automated JS tests — form rendering, tabs, paired image
rows, geolocation and collection are verified via headless-Chrome DOM dumps
(per AGENTS.md vision guidance): serve the app (`poe api-server`), load a
temp copy of `index.html` that auto-selects the task and drives the UI,
then assert on `document.title` / the rendered DOM. The same dump approach
checks the assembled `fields` payload against `assemble_args` expectations.

## Telegram Bot Design (Phase 2)

### Command list

| Command          | Arg          | Behavior                                      |
| ---------------- | ------------ | --------------------------------------------- |
| `/weight <kg>`   | `82.5`       | run `poe bot weight 82.5`                     |
| `/sync`          | —            | run `poe bot sync-running`                    |
| `/enu <word>`    | `cumbersome` | run `poe bot enu add cumbersome`              |
| `/moment <text>` | `晨跑5km`    | run `poe bot text-moment "晨跑5km"`           |
| `/health`        | —            | run `poe bot health-summary`                  |
| `/post`          | —            | multi-step dialog: title → category → confirm |
| `/status`        | —            | show the last 5 runs                          |
| `/cancel`        | —            | cancel the current dialog                     |

All commands are **handoff-only** (never auto-merge), matching the web
console.

### Multi-step dialog example (/post)

```

User: /post
Bot: 📰 New Post
Step 1/3: Enter the post title

User: 关于 FastAPI 的笔记
Bot: Step 2/3: Choose a category
[bits] [dev] [thought]

User: dev
Bot: Step 3/3: Save as draft?
[Yes] [No]

User: Yes
Bot: ✅ Submitted
Task: create-post "关于 FastAPI 的笔记" --category dev --draft
Run ID: abc123
Progress: /status

````

### Implementation: ConversationHandler

```python
# api/routers/tg.py
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# dialog states
TITLE, CATEGORY, DRAFT = range(3)


async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 New Post\nStep 1/3: Enter the title")
    return TITLE


async def post_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    # send inline keyboard to pick category...
    return CATEGORY


# ... subsequent state handlers

post_conv = ConversationHandler(
    entry_points=[CommandHandler("post", post_start)],
    states={
        TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_title)],
        CATEGORY: [CallbackQueryHandler(post_category)],
        DRAFT: [CallbackQueryHandler(post_draft)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
````

### Execution

On a command, the TG Bot does **not** call `git_bot.py` directly — it goes
through the same shared execution function as the web console:

```python
# api/routers/tg.py
from api.executor import execute_bot_task  # same function as the web path


async def cmd_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weight = context.args[0] if context.args else None
    if not weight:
        await update.message.reply_text("Usage: /weight <kg>\nExample: /weight 82.5")
        return

    run = execute_bot_task(task="weight", args=[weight])  # handoff-only
    await update.message.reply_text(
        f"✅ Submitted: weight {weight} kg\nRun ID: `{run.run_id}`\nProgress: /status",
        parse_mode="Markdown",
    )
```

### Webhook vs Polling

| Mode        | Config                               | Use case                      |
| ----------- | ------------------------------------ | ----------------------------- |
| **Polling** | `TG_MODE=polling`                    | local dev, no public IP       |
| **Webhook** | `TG_MODE=webhook` + `TG_WEBHOOK_URL` | production, Cloudflare Tunnel |

Webhook integrated into FastAPI (no secret-token check — auth removed by
dev decision; use an unguessable path like `/webhook/<random>`):

```python
# api/server.py (Phase 2)
from api.routers.tg import tg_application


@app.post("/webhook/<random>")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_application.bot)
    await tg_application.process_update(update)
    return {"ok": True}
```

## State & History

### Runtime state (in-memory)

```python
# api/state.py
from dataclasses import dataclass, field
from typing import Optional
import asyncio


@dataclass
class BotRun:
    run_id: str
    task: str
    args: str
    status: str  # running | submitted | failed | aborted
    started_at: str
    finished_at: Optional[str] = None
    pr_url: Optional[str] = None
    logs: list[dict] = field(default_factory=list)
    log_queue: asyncio.Queue = field(default_factory=asyncio.Queue)


# global state (single process, no Redis)
active_runs: dict[str, BotRun] = {}
```

### Persisted history (file)

```
.bot-api/history.jsonl   # git-ignored, appended line by line
```

One JSON object per line; the implementation reads it on every
`/api/bot/history` request (no load-at-startup cache needed):

```json
{"run_id":"abc123","task":"weight","args":"82.5","status":"submitted","started_at":"2026-08-14T01:09:00+08:00","finished_at":"2026-08-14T01:12:34+08:00","pr_url":"https://github.com/.../142","logs":[...last 20 lines...]}
```

The `logs` field keeps only the last 20 entries (enough to diagnose a
failure without bloating the file).

### Cleanup strategy

- **Startup**: `lifespan.py` runs `poe bot cleanup` for stale worktrees
  (gated by `BOT_API_STARTUP_CLEANUP`)
- **Runtime**: `active_runs` keeps the latest 50; overflow is flushed to
  the file and dropped from memory
- **History file**: rotates by date (`history.jsonl.<date>`), keeps 30 days

## Execution Flow

### Web console trigger

```
1. User clicks "Run Bot"
2. frontend: POST /api/bot/run {task, fields, handoff}
3. api/routers/bot.py:
   a. validate task name and args (schema-derived)
   b. generate run_id (first 12 hex chars of uuid4)
   c. create BotRun and put it in active_runs
   d. asyncio.create_task(_run_bot(...))  # background execution
   e. return immediately {run_id, status: running, stream_url}
4. frontend: EventSource /api/bot/stream/{run_id}
5. _run_bot:
   a. asyncio.create_subprocess_exec("uv", "run", "poe", "bot", "run", spec, "--handoff")
      (PYTHONUNBUFFERED=1 merged into the env)
   b. read stdout line by line
   c. push each line to run.log_queue → SSE consumers
   d. on exit: detect outcome (exit code + "Draft PR" / "merged PR" scan),
      set status, write the trimmed history record
```

### Telegram trigger (Phase 2)

```
1. User sends /weight 82.5
2. Telegram Cloud POST /webhook
3. api/routers/tg.py:
   a. CommandHandler matches /weight
   b. parse args → call execute_bot_task() (same as the web path step 3)
   c. reply: Run ID + /status hint
4. User sends /status
5. query active_runs / history file, format the reply
```

## Telegram Bot Setup (Phase 2)

How to create the bot, get the token, and configure the API server for the
allowlisted private bot (`/weight`, `/enu`, `/moment`).

### 1. Create the bot and get the token (BotFather)

1. Open Telegram and start a chat with **@BotFather** (the official
   bot-creation bot, blue checkmark).
1. Send `/newbot`.
1. Follow the prompts:
   - **Name**: any display name (e.g. `Xiongjia Bot`).
   - **Username**: must end in `bot` (e.g. `xiongjia_bot`).
1. BotFather replies with an **HTTP API token**, e.g.
   `123456789:AAF...` — copy it, this is `TG_BOT_TOKEN`.
   (Rotate it later with `/token`; delete the bot with `/deletebot`.)

### 2. Get your Telegram user ID (allowlist)

The bot only answers allowlisted users (`TG_ALLOWED_USER_IDS`). Ask any
user-info bot for your numeric ID — they reply with a single number on
any message:

| Bot              | Notes                                    |
| ---------------- | ---------------------------------------- |
| **@userinfobot** | most common; compact reply               |
| @getidsbot       | replies with chat id / user id           |
| @RawDataBot      | full JSON — your id is `message.from.id` |

Web alternative: open `https://t.me/userinfobot`, tap "Open in
Telegram", send `/start`.

1. Start a chat with the bot and send `/start` (or any message) — it
   replies with your numeric user ID, e.g. `123456789`.
1. Put that number in `TG_ALLOWED_USER_IDS` (comma-separated for more
   than one user).

> **First-setup gotcha**: non-allowlisted messages are **silently
> ignored** (no reply, no error). If you mis-typed the ID, your own
> `/weight` / `/enu` / `/moment` will get no response either — re-check
> the ID with @userinfobot before digging elsewhere.

### 3. Configure `.env.local`

Add to `.env.local` (never commit secrets; `.env.example` documents the
keys). `shared.env.load_env_files()` picks `.env.local` up at server
start:

```bash
TG_BOT_TOKEN=123456789:AAF...
TG_ALLOWED_USER_IDS=123456789
TG_MODE=polling
```

- `TG_MODE=polling` — dev mode: the bot long-polls Telegram itself; no
  public URL needed. Use this first to verify.
- `TG_MODE=webhook` — production: Telegram POSTs updates to a public
  https URL. Needs `TG_WEBHOOK_URL` (e.g. Cloudflare Tunnel → nginx →
  `http://127.0.0.1:8100/webhook/...`). The webhook path is
  `/webhook/<secret>`; the secret comes from `TG_WEBHOOK_PATH` when set,
  otherwise a random value is generated at startup (nginx / the tunnel
  can forward the whole `/webhook/` prefix, so the value itself doesn't
  need to be pinned unless you want a stable URL).

### 4. Network / proxy

`python-telegram-bot` talks to `api.telegram.org` (outbound HTTPS). If
Telegram is unreachable directly (e.g. mainland China), reuse the
existing proxy env:

```bash
BOT_HTTP_PROXY=http://127.0.0.1:1095
```

### 5. Verify

1. Start the server: `uv run poe api-server`
   (defaults `BOT_API_HOST=127.0.0.1`, `BOT_API_PORT=8100`).
1. In Telegram, message the bot:
   - `/ping` → replies `pong` (config self-check — works even for
     non-allowlisted accounts, so it can tell a connection/token
     problem from an allowlist one).
   - `/help` → lists all available commands.
   - `/weight 82` (from your allowlisted account) → replies with a run
     id, then pushes the result + PR link when the run finishes.
   - `/moment Morning run 5km` (optionally with photos) → same flow.
1. Watch logs/history in the web console at `http://localhost:8100`.
1. A message from a **non-allowlisted** account is silently ignored
   (no reply, no error) — except `/ping`, which always answers.

### Troubleshooting

- **"Unauthorized" / 401 on start** → `TG_BOT_TOKEN` wrong or the bot
  was deleted; re-run `/newbot` or `/token` in BotFather.
- **No replies, server logs show polling errors** → outbound network
  problem; set `BOT_HTTP_PROXY` and restart.
- **Commands ignored even from your own account** → your user ID is not
  in `TG_ALLOWED_USER_IDS`, or the value has spaces/typos. Cross-check:
  `/ping` still answers (it bypasses the allowlist); if `/ping` also goes
  unanswered, the problem is upstream (token / connection / server).
- **Webhook 404** → `TG_MODE=webhook` but the tunnel/nginx path does
  not match `/webhook/`; or `TG_WEBHOOK_URL` was never registered
  (`set_webhook` runs at startup — check startup logs).

## Deployment

### Development

```bash
# 1. Install deps
uv sync

# 2. Configure .env (BOT_API_HOST/PORT, BOT_API_LOG_DIR; TG_* in Phase 2)

# 3. Start
uv run poe api-server
# → http://localhost:8100/        (Web console)
# → http://localhost:8100/docs    (Swagger UI)
# → http://localhost:8100/api/    (REST API)
```

### Production (public IP / VPS)

```bash
uv run poe api-server-prod
```

With systemd:

```ini
# ~/.config/systemd/user/bot-api.service
[Unit]
Description=Bot Remote API
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/xiongjia/xiongjia.github.com
ExecStart=/home/xiongjia/.local/bin/uv run poe api-server-prod
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

### No public IP (Cloudflare Tunnel)

```bash
# 1. Install cloudflared
# 2. Log in and create the tunnel
cloudflared tunnel create bot-api

# 3. config.yml
# tunnel: <tunnel-id>
# credentials-file: ~/.cloudflared/<tunnel-id>.json
# ingress:
#   - hostname: bot.xiongjia.github.io
#     service: http://localhost:8100
#   - service: http_status:404

# 4. Run
cloudflared tunnel run bot-api
```

With systemd autostart, zero-config public access. Note: with auth removed,
restrict tunnel ingress or accept the risk (see the plan).

### Nginx reverse proxy (optional)

```nginx
server {
    listen 443 ssl;
    server_name bot.xiongjia.github.io;

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_buffering off;   # SSE needs it
    }
}
```

## Risks & Constraints

- **No-auth upload endpoint**: `POST /api/upload` (no auth, like the rest
  of the API) lets anyone who can reach the server write files — ≤25 MB
  each, base64-decoded — into `BOT_API_LOG_DIR/uploads/` (name-sanitized,
  extension-whitelisted, stale-pruned after 30 days). The console only
  exposes it locally; if the port is ever tunneled/public, gate it behind a
  reverse-proxy auth / firewall first (see `.env.example` warning).
- **Single-process limit**: `active_runs` lives in memory; a restart loses
  in-flight runs (the history file survives). Redis can replace it later if
  high availability is needed.
- **Concurrency safety**: `git_bot.py` worktrees are isolated by branch
  name + timestamp, so concurrent runs are natural; but repeated same-day
  submissions of one task (e.g. weight) may overwrite the day's data
  (idempotency is guaranteed by `update_weight.py` itself).
- **Token safety**: `TG_BOT_TOKEN` lives only in `.env` and process memory,
  never in logs or responses. (With auth removed there is no `BOT_API_KEY`
  anymore.)
- **Network dependency**: `poe bot` needs to download mermaid and push to
  GitHub — the API server must reach the internet (or go through
  `BOT_HTTP_PROXY`). Pushing through a proxy can transiently drop the
  connection after the server accepted the ref; `push_branch` retries on
  such connection errors.
- **Resource footprint**: FastAPI + uvicorn single worker uses ~30–50 MB —
  negligible.

## File Size Estimate

| File                     | Estimated lines  |
| ------------------------ | ---------------- |
| `api/server.py`          | 30               |
| `api/config.py`          | 20               |
| `api/models.py`          | 130              |
| `api/lifespan.py`        | 45               |
| `api/state.py`           | 65               |
| `api/history.py`         | 60               |
| `api/executor.py`        | 130              |
| `api/routers/bot.py`     | 100              |
| `api/routers/system.py`  | 35               |
| `api/routers/tg.py`      | 150              |
| `api/static/index.html`  | 40               |
| `api/static/css/app.css` | 130              |
| `api/static/js/app.js`   | 190              |
| `scripts/api_server.py`  | 30               |
| **Total**                | **~1,150 lines** |
