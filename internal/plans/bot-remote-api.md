---
title: Bot Remote API — HTTP API + Web Console + Telegram Bot
created: 2026-08-14
updated: 2026-08-17
status: in-progress
tags: [bot, api, fastapi, telegram, web-console]
---

# Bot Remote API

## Goal

Expose the local `scripts/git_bot.py` execution engine through a remote
management entry point: a REST API + static Web console + Telegram Bot, all
served by a single FastAPI process. The API layer stays a thin shell —
business logic (worktree isolation, CI gate, PR flow) remains untouched in
`scripts/git_bot.py`; the remote layer only adds serialization and
protocol adaptation.

Source design: `internal/bot-api-design.md` (raw copy committed in-repo —
originally authored outside the repo; translation to English is a Phase 0
task). Engine reference: `internal/bot-auto-pr-design.md`.

## Status (2026-08-14)

**Phase 1 core done** — Web management API + console is live: API skeleton
(`config`/`state`/`history`/`models`/`executor`/`routers`/`lifespan`/
`server`), static dark SPA console, engine rest-arg support
(`text-moment` args `[text...]`, multi-word content), local test wiring
(`poe test` with api extra + `httpx`). Verified: 30 `tests/api/` tests +
full suite 415 passing, ruff clean, live smoke test on
`127.0.0.1:8100` (health/version/tasks/schema/console all 200).

**Phase 1 done** — web management API + console complete and verified
(30+ `tests/api/` tests, full suite 421 passing, ruff clean, live smoke
on `127.0.0.1:8100`). **Phase 0 done** — design doc translated, engine
registry aligned, `.gitignore` updated. Attachment uploads shipped early
in a simpler form than planned: base64 JSON staging (no python-multipart),
and `create_moment` converts + uploads to R2 so files never enter the
worktree — the planned `--stage-dir` engine flag is dropped (the Phase 2
upload entries below reflect this).

**Phase 2 done (2026-08-17)** — Telegram Bot implemented and verified:
allowlisted users only (`TG_ALLOWED_USER_IDS`, denied users silently
ignored), three tasks (`/weight`, `/enu`, simplified `/moment` text +
multiple photos via caption command / album aggregation), completion
push to the issuing chat (one-way, PR link), webhook + polling mode
switch, `--no-editor` sanctioned flag on `create_moment` for photo-only
moments, 13 `tests/api/test_tg_webhook.py` tests + full suite 634
passing, ruff clean. Setup guide: `internal/bot-api-design.md`
(§ Telegram Bot Setup). Real-device
smoke (a live bot token) is pending — see Phase 2's status note.
Task scheduling (cron) is dropped — not needed for now.

## Target structure

Final code layout this plan builds toward (differs from the design doc's
original layout — see the Findings below):

```
xiongjia.github.com/
├── api/                                  # remote API service (thin shell)
│   ├── __init__.py                       # package marker
│   ├── server.py                         # FastAPI app + StaticFiles(/ → static/) + route mounts + lifespan
│   ├── config.py                         # pydantic-settings: server host/port + TG_*; read after load_env_files()
│   ├── models.py                         # Pydantic request/response + task UI metadata; task list derived
│   │                                     #   from the engine (mkdocs.yml extra.bot.tasks + git_bot.TASKS)
│   ├── state.py                          # BotRun dataclass + active_runs (in-memory, capped at 50)
│   ├── history.py                        # JSONL append persistence + daily rotation (30 days)
│   ├── uploads.py                        # image staging: base64 from console; raw-bytes writer
│   │                                     #   shared with TG photo downloads (sanitize + limits)
│   ├── executor.py                       # execute_bot_task(): async subprocess scheduling + log queue
│   │                                     #   + status updates + history writes
│   ├── lifespan.py                       # startup: cleanup / schema validation / PTB init; shutdown: kill
│   │                                     #   in-flight bot subprocesses first
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── bot.py                        # POST /api/bot/run, GET /status/{id}, GET /stream/{id} (SSE+heartbeat),
│   │   │                                 #   GET /history, POST /abort/{id}
│   │   ├── system.py                     # GET /api/health, /version, /schema/{task}
│   │   └── tg.py                         # POST /webhook + allowlist gate + 3 commands
│   │                                     #   + completion push to the issuing chat
│   └── static/                           # Web console (pure static SPA, no build step)
│       ├── index.html
│       ├── css/
│       │   └── app.css                   # GitHub dark theme
│       └── js/
│           └── app.js                    # EventSource SSE + heartbeat, dynamic forms, history refresh
│
├── scripts/
│   ├── git_bot.py                        # existing, zero modification (rest-arg + push retry only)
│   └── api_server.py                     # new: uvicorn launcher (with REPO_ROOT sys.path bootstrap)
│
├── tests/
│   ├── conftest.py                       # modified: add REPO_ROOT to sys.path (for `import api`)
│   └── api/
│       ├── test_bot_router.py            # run / status / stream / history / abort
│       ├── test_tg_webhook.py            # allowlist gate + 3 commands + completion push
│       ├── test_executor.py              # subprocess scheduling, state transitions, arg pass-through
│       ├── test_history.py               # JSONL write / load / rotation
│       └── test_uploads.py               # base64 staging: sanitize / dedupe / limits / prune
│
├── internal/
│   ├── bot-api-design.md                 # committed (raw Chinese copy; translation is a Phase 0 task)
│   └── plans/bot-remote-api.md           # this plan
│
├── mkdocs.yml                            # modified: add create-post template task to extra.bot.tasks
├── pyproject.toml                        # modified: [api] extras + poe api-server / api-server-prod
├── .env.example                          # modified: append server (BOT_API_HOST/PORT) + TG_* blocks
├── .gitignore                            # modified: ignore .bot-api/ (runtime data dir)
│
└── .bot-api/                             # runtime data (git-ignored; BOT_API_LOG_DIR)
    ├── history.jsonl                     # run history (JSONL, 30-day rotation)
    └── uploads/                          # attachment staging (Phase 2)
```

Notable deltas vs. the design doc's original layout: no `api/templates/`
(pure static SPA needs none); **no `api/auth.py`** (auth layer dropped by
dev decision); `execute_bot_task()` lives in `api/executor.py` instead of
`routers/bot.py` so both bot.py and tg.py share it without router
cross-imports; the task list is engine-derived (mkdocs.yml + `git_bot.TASKS`)
with only UI metadata in `models.py`; `tests/api/` files need globally unique
basenames (no `__init__.py`, matching the flat test convention) plus the
conftest REPO_ROOT change; `POST /api/bot/abort/{id}` covers the cancel path
missing from the original design; `api/uploads.py` + `.bot-api/uploads/`
reserve the attachment-upload path (Phase 2).

## Findings — source design vs. actual codebase

The design doc was written against an idealized view of the repo. Repo
analysis surfaced the following discrepancies, all folded into the Tasks:

1. **`create-post` is not a bot task.** The engine registry is
   `TASKS = {weight, health-summary, sync-running, enu}` (builtins in
   `scripts/git_bot.py`) **+ template tasks from `mkdocs.yml extra.bot.tasks`** — which currently contains only `text-moment`. The
   design's `TASK_SCHEMAS` includes `create-post`, which the engine would
   reject (`unknown task`). Fix: add a `create-post` **template task** to
   `mkdocs.yml` (zero engine changes) or drop it from the schemas. Also
   verify the schema's `category` options against `create_post.py`
   (`--category` default `bits`; examples use `dev`/`thought`, not
   `life`).
1. **No auth layer** (dev decision) — drops the design's API-Key +
   IP-whitelist + TG secret-token machinery. Plain browser `EventSource`
   works directly (no `Authorization` header problem), so no
   `fetch`/`ReadableStream` shim is needed; still send an SSE heartbeat
   (`: ping` every ~15 s) so proxies don't kill idle connections.
1. **`TASK_SCHEMAS` would drift from the engine registry.** The schema
   list (task names + which args are required) is derivable — reuse
   `shared.mkdocs_yaml.load_extra("bot")` for template tasks and import
   `TASKS` from `scripts.git_bot` for builtins. Keep only UI metadata
   (label/type/step/options) in `api/models.py`, plus a generic fallback
   schema (fields from the template task's declared `args`) for tasks
   without explicit metadata. Validate at startup (lifespan): fail fast if
   a schema names a task the engine doesn't know.
1. **`import api` will not resolve from `scripts/api_server.py`.** Every
   script bootstraps `sys.path.insert(0, REPO_ROOT)` (see `git_bot.py`,
   `create_post.py`); `api_server.py` must do the same or `uv run python scripts/api_server.py` can't import the `api/` package. Likewise
   `tests/conftest.py` must add `REPO_ROOT` to `sys.path` (it currently
   only adds `scripts/` and the health macros) or `tests/api/` imports
   fail.
1. **`api/` is inside ruff's lint/format scope.** `poe lint-py`
   (`ruff check .`) and `poe fmt` (`ruff format .`) cover the whole repo,
   and the bot's own CI gate runs them in the worktree — new `api/` code
   must pass E/F/I/N/W, line-length 100, double quotes from day one.
1. **PTB polling blocks.** `python-telegram-bot`'s `run_polling()` is a
   blocking loop — in webhook mode it's fine (`process_update` per
   request), but `TG_MODE=polling` must be wired into the FastAPI
   lifespan as an async background task (`await app.initialize()` /
   `app.start()` / `updater.start_polling()` on startup, `app.stop()` on
   shutdown), not called synchronously.
1. **`.gitignore` has no entry for the history file.** The runtime data
   dir `.bot-api/` (history JSONL + rotation files, later uploads staging)
   must be ignored or the bot's own CI gate (`git add -A`) would try to
   commit run history from the worktree. The dir is configurable via
   `BOT_API_LOG_DIR` (default: repo-local `.bot-api/`, absolute or
   repo-relative).
1. **History endpoint missing from the phase-1 task list.** The design
   specifies `GET /api/bot/history` (§5) but Phase 1 only lists
   run/status/stream — the history endpoint belongs in Phase 1 (it backs
   the console's Recent Runs pane).
1. **Optional schema fields map to engine pass-through args.** `TemplateTask`
   (mkdocs.yml tasks) appends undeclared args to `cmd`; builtins accept
   `--date`/`--time`/`--dir` opts. The API must forward **only provided**
   fields as extra args (e.g. `text-moment` + `--time`, `weight` +
   `--date`, `enu` + `--date`), and must always supply declared args
   (defaults from the schema) — `TemplateTask.plan` raises when a declared
   arg is missing.
1. **Ports/hosts should be env-driven, not hardcoded.** The uvicorn bind
   comes from `api/config.py` defaults (`host` 0.0.0.0, port from
   `BOT_API_PORT`), and `poe api-server` / `poe api-server-prod` run the
   launcher without extra flags — so `BOT_API_HOST=127.0.0.1` restores
   local-only operation.
1. **Status enum should match engine outcomes.** Engine marker states are
   `running/ready/submitting/stale` + derived `merged`; map to API status
   `running → submitted` (draft PR, handoff — the only outcome, see the
   handoff-only note) **or** `failed` (non-zero exit) **or** `aborted`
   (API cancel).
   Add an `abort` action — the design has no way to cancel a running
   bot (subprocess terminate + `poe bot abort <branch>`).
1. **Attachment uploads (resolved — R2 route).** The design only
   supports text args, but `create_moment.py --image` writes
   `![Image](./<path>)` relative to the moment file, and the moment is
   content **committed in the PR** — so the file must be referenceable
   from inside the bot worktree's `docs/` *before* the task runs (race:
   `poe bot` creates the worktree inside its own subprocess). Two
   candidate mechanisms: (a) a sanctioned engine flag
   (`--stage-dir`, copy the API's staging dir into the worktree after
   `symlink_env()`) — the original plan, or (b) have the task itself
   upload to R2. **Shipped: (b)** — `create_moment` now converts +
   uploads to R2 immediately and references `assets/bucket/…` (commit
   `7ed3baa`), so files never enter the worktree and `--stage-dir` was
   dropped. What remains: `POST /api/upload` base64 staging to the
   git-ignored `.bot-api/uploads/` (done, `api/uploads.py` + `test_uploads.py`),
   and the TG photo path reusing the same sanitize/limits. The rejected
   alternative (uploads via PicList only) was superseded by
   `poe bucket-upload` / the create_moment R2 flow.

## Tasks

### Phase 0 — Design doc + engine-registry alignment (prereq)

- [x] Translate `internal/bot-api-design.md` to English — done (faithful
  translation; top-of-doc status note catalogs every implementation
  divergence and points to this plan)
- [x] `mkdocs.yml` `extra.bot.tasks`: add `create-post` template task
  (`args: [title, category]`, cmd
  `uv run python scripts/create_post.py {title} --category {category}`);
  API appends `--no-draft` when the console's draft checkbox is off
  (create_post.py drafts by default) — done, plus `text-moment` args
  became `[text...]` (rest arg, see Notes)
- [x] Verify schema `category` options against `create_post.py`
  (`bits`/`dev`/`thought` etc.) and fix the design's `life` option — done
- [x] `.gitignore`: ignore the `.bot-api/` runtime data dir
  (history + rotation + uploads staging) — done

### Phase 1 — Web management API + console (complete, standalone)

- [x] Add `api/` package: `server.py` (FastAPI app + lifespan), `config.py`
  (pydantic-settings; read after `shared.env.load_env_files()`; server
  host/port defaults `BOT_API_HOST=127.0.0.1`, `BOT_API_PORT=8100` — not
  8000, the mkdocs dev server owns it, see Notes; **no auth layer** per
  dev decision)
- [x] `api/models.py`: Pydantic request/response models + UI field
  metadata keyed by task; **task list derived from the engine** —
  `shared.mkdocs_yaml.load_extra("bot")["tasks"]` + builtins imported
  from `scripts.git_bot.TASKS`; generic fallback schema from declared
  `args`; startup validation that every schema maps to a known task;
  field metadata reserves a `file` type (attachment uploads, Phase 2)
- [x] `api/executor.py`: `execute_bot_task()` — build `uv run poe bot run … --handoff|--wait-ci`
  argv (handoff checkbox: True = draft PR immediately (default), False =
  wait for CI, still draft; auto-merge internal/test-only),
  spawn
  via asyncio subprocess (cwd = REPO_ROOT), stream stdout/
  stderr lines into the run's log queue (raw passthrough + optional
  emoji→level heuristic), **detect outcome** from exit code + output scan
  (`✅ merged PR` / `📦 Draft PR`) → status `merged`/`submitted`/`failed`,
  write history; injectable runner so unit tests never spawn a real
  `poe bot`
- [x] `api/routers/bot.py`: `POST /api/bot/run`, `GET /api/bot/status/{run_id}`,
  `GET /api/bot/stream/{run_id}` (SSE with heartbeat + reconnect-friendly
  tail replay), `GET /api/bot/history` (limit/offset + `q` search),
  `POST /api/bot/abort/{run_id}` (terminate subprocess + `poe bot abort`
  cleanup — the console's cancel button)
- [x] `api/routers/system.py`: `GET /api/health`, `GET /api/version`
  (git hash via `GIT_HASH` / `git rev-parse`), `GET /api/schema/{task}`,
  `GET /api/tasks` (engine-derived task list for the console's
  quick-task pane — no hardcoded list in index.html)
- [x] `api/state.py` + `api/history.py`: in-memory `BotRun` (active runs
  capped at 50, oldest flushed to file) + JSONL persistence in the
  `BOT_API_LOG_DIR` data dir (default `.bot-api/`, git-ignored; absolute
  or repo-relative; `history.jsonl` + 30-day rotation + prune)
- [x] `api/lifespan.py`: startup — stale-worktree cleanup
  (`poe bot cleanup`, gated by `BOT_API_STARTUP_CLEANUP`), schema
  validation; graceful shutdown — terminate in-flight bot subprocesses
  first (PTB init moves to Phase 2)
- [x] `scripts/api_server.py`: uvicorn wrapper with
  `sys.path.insert(0, REPO_ROOT)` bootstrap; host/port from
  `BOT_API_HOST/PORT` unless CLI-argued
- [x] `api/static/`: dark SPA console (index.html + css + js, no build
  step) — dynamic forms from `/api/schema/{task}`, `EventSource` SSE
  (no auth headers needed) with heartbeat, history refresh
- [x] `pyproject.toml`: `api` extras (`fastapi`, `uvicorn[standard]`,
  `pydantic-settings`) + `poe api-server` / `api-server-prod` tasks
  (port from env, not hardcoded; `python-telegram-bot>=20.6` is added in
  Phase 2)
- [x] `.env.example`: append server block only
  (`BOT_API_HOST=127.0.0.1`, `BOT_API_PORT=8100`); `TG_*` block comes in
  Phase 2
- [x] `tests/`: `tests/api/test_bot_router.py`, `test_system.py`,
  `test_executor.py`, `test_history.py` (30 tests; `test_uploads.py`
  comes with the uploads feature in Phase 2); add `REPO_ROOT` to `sys.path`
  in `tests/conftest.py`; keep `api/` ruff-clean (repo-wide
  `poe fmt`/`lint-py` enforce it). Test strategy: executor tests inject
  a fake runner (no real `poe bot`, no network/worktrees/GitHub);
  history tests use tmp_path (TG webhook tests come with Phase 2)
- [x] Local test wiring only (GitHub CI is deferred to Phase 2, with TG):
  `tests/api/` imports the `api` package → `poe test` becomes
  `uv run pytest -q` (fastapi/pytest/httpx live in
  `[project.dependencies]`, no extras — verified: without them pytest
  collection fails on fastapi import). No `.github/workflows/ci.yml`
  changes here.
- [x] History pagination + search (`GET /api/bot/history` limit/offset +
  `q` query param; `history.load(limit, offset, query)` returns
  newest-first records + total)

### Phase 2 — Telegram Bot: allowlist + 3 tasks + completion push (last phase)

**Scope (dev decision, 2026-08-17)**: private bot — only allowlisted
users may issue commands. Three tasks only: `/weight`, `/enu`, and a
simplified `/moment` (text + optional multiple photos; no
tags/captions/place/GPS/meta). Dropped from the original design: `/sync`,
`/health`, `/post` (ConversationHandler + `/cancel` fallback), `/status`
(completion push replaces it), and the complex moment flow (create_moment
extras stay web-console-only).

**Interaction decisions (2026-08-17)**: replies in **English**;
`/moment` allows **photo-only** (empty text — passes `""` +
`--no-editor`, see below); `/weight` defaults to today (no `--date`);
concurrent runs are **allowed** (worktree isolation, same as the console
— never rejected/queued); completion push is one-way — uniform handoff
(draft PR), sends the result + PR link, nothing further to reply.

**Status: implemented (2026-08-17)** — all items below are done and
verified by `tests/api/test_tg_webhook.py` (13 tests) + the full suite
(634 passing) + ruff clean. Remaining: a real-device smoke test with a
live bot token (see the design doc's "Telegram Bot Setup" section).

- [x] `api/config.py`: add TG settings — `tg_bot_token`,
  `tg_webhook_url`, `tg_webhook_path` (optional; random at startup if
  unset), `tg_mode` (`polling` default), `tg_allowed_user_ids`
  (comma-separated ints, parsed into a set; empty → no TG commands
  accepted, fail fast at startup)
- [x] `pyproject.toml`: add `python-telegram-bot>=20.6`
  (`download_to_drive`) to `[project.dependencies]` — no extras, matching
  the CI decision (finding 4; PTB must be importable in the lint job)
- [x] `.env.example`: append the `TG_*` block (`TG_BOT_TOKEN`,
  `TG_WEBHOOK_URL`, `TG_MODE=polling`, `TG_ALLOWED_USER_IDS`,
  `TG_WEBHOOK_PATH`; acquisition steps in the design doc's "Telegram
  Bot Setup" section)
- [x] `api/routers/tg.py`: webhook handler (`POST /webhook/{secret}` —
  secret = `TG_WEBHOOK_PATH` or random at startup) + command routing;
  **allowlist gate first** — `update.effective_user.id` not in
  `TG_ALLOWED_USER_IDS` → ignore silently (no reply, no hint the bot
  exists); no secret-token check (web API auth decision stands).
  Webhook registration: lifespan calls `bot.set_webhook(TG_WEBHOOK_URL)`
  on startup and `delete_webhook()` on shutdown (webhook mode only)
- [x] Commands (single-step, shared `execute_bot_task()`, handoff-only,
  never auto-merge — same as the console; English replies):
  - `/ping` → replies `pong` (config self-check; **bypasses the
    allowlist** so first-time setup can tell a connection/token problem
    from an allowlist one; no side effects)
  - `/help` → replies the command list (no side effects; also bypasses
    the allowlist, same reasoning as /ping)
  - `/weight <kg>` → `execute_bot_task("weight", [kg])` — defaults to
    today (no `--date`)
  - `/enu <text…>` → `execute_bot_task("enu", [" ".join(args)])` — free
    text, rest-arg join (finding 9)
  - `/moment [text…] [photos…]` → `execute_bot_task("text-moment", [text or "", *[f"--image={p}" for p in paths]])` — text optional
    (photo-only allowed); when text is empty pass `""` + `--no-editor`
    so create_moment skips the EDITOR step (new sanctioned flag, see
    Moment photos item); simplified — text + images only
- [x] Moment photos: gather **all** photos of the message or media group
  (album) — `update.message.photo` (per message) and, for albums,
  `media_group_id` aggregation across updates (each photo update carries
  the same group id); the text comes from the caption (first photo's
  caption for albums) or the command args. For each photo take
  `photo[-1]` (largest) → `get_file()` → `download_to_drive()` into
  `.bot-api/uploads/` through the same sanitize/validation as browser
  uploads (extract a raw-bytes writer in `uploads.py` sharing
  `_sanitize_name` + size/type limits; the PTB download bypasses the
  base64 route). Outbound HTTPS needed — `BOT_HTTP_PROXY` honored.
  Reply with run_id immediately
- [x] `create_moment.py` gains a `--no-editor` flag (sanctioned extension,
  like the rest-arg marker): when `content` is empty/absent AND
  `--no-editor` is set, skip the `subprocess.call([EDITOR, …])` step —
  required for photo-only TG moments (the bot subprocess has no TTY and
  EDITOR would fail/hang). Web console unaffected (content is required
  there)
- [x] Completion push: after a run finishes (submitted/failed/aborted),
  send a one-way result (task, args, status, PR link) to the **issuing
  chat** — uniform handoff (always draft PR), no reply expected. Needs
  an `on_done` hook in `api/state.py` `BotRun.finish()` (covers every
  finish path incl. abort) — `api/routers/tg.py` registers a callback
  per run; `--wait-ci` runs can take minutes, so the webhook handler
  never blocks on completion
- [x] Polling/Webhook mode switch (`TG_MODE=polling|webhook`) — lifespan
  PTB lifecycle (Phase 1 lifespan gains this): `initialize()`/`start()`
  unconditionally, then `updater.start_polling()` as an async background
  task (finding 6) or `set_webhook()` per mode; `stop()` on shutdown;
  webhook mode via `process_update` per request. Keep the handler fast
  and always return 200 — Telegram retries on timeout, and a retried
  `/moment` would create two moments (dedupe on `update.update_id` if
  cheap)
- [x] `tests/api/test_tg_webhook.py`: allowlist gate (allowed/denied),
  the three commands (monkeypatch `execute_bot_task` — no real `poe bot`), and the completion-push callback, using in-memory PTB `Update`
  objects (no network); PTB `Application` built with a fake token, bot
  sends monkeypatched
- [x] GitHub CI (already done): `.github/workflows/ci.yml`
  `uv sync` (API/test deps moved into `[project.dependencies]`, no
  extras); the lint job runs pytest incl. `tests/api/` — PTB joins the
  same deps, so the job keeps working with no changes

## Notes

- **Zero-modification rule**: `scripts/git_bot.py` must not change; the API
  shells out via `uv run poe bot ...` (subprocess) and derives its task
  list from `mkdocs.yml` + `git_bot.TASKS` (read-only import). Sanctioned
  exceptions so far: a rest-arg marker in `TemplateTask`
  (mkdocs.yml `args: [text...]` — joins free-text tokens so multi-word
  moment content survives the engine's whitespace split), and a
  **push retry** in `push_branch` (3 attempts on transient
  connection errors — diagnosed: pushing through the HTTP proxy sometimes
  drops the connection after the server accepted the ref, e.g. "Remote end
  closed connection without response"), and a **no-op commit guard** in
  `do_submit`/`commit_workdir` (returns whether a commit was created; no
  diff → print `⏭ no changes (already recorded)` and exit clean instead
  of pushing and failing PR creation with GitHub 422 — hit with a
  same-day duplicate `/weight 82`). The originally planned
  `--stage-dir` flag (copy uploads into the worktree after
  `symlink_env()`) was **dropped**: `create_moment.py --image` now
  converts + uploads to R2 and references `assets/bucket/…`, so staged
  files never need to enter the worktree.
- **Task registry is config-driven**: adding a task = mkdocs.yml
  `extra.bot.tasks` entry + optional UI metadata in `api/models.py`; the
  schema endpoint and console forms follow automatically.
- **TG attachments (Phase 2, simplified)**: `/moment` takes text plus
  multiple photos — from one message or an album (media group,
  aggregated on `media_group_id`); each photo `photo[-1]` → `get_file()`
  → `download_to_drive()` into `.bot-api/uploads/` through the same
  sanitize/size checks as browser uploads, then forwarded as one
  `--image=<abs path>` per photo; `create_moment` converts + uploads to
  R2 (staging is transient — no `--stage-dir`). Keep downloads small
  (bots cap at 20 MB) and reply promptly —
  background the work so the webhook 200 isn't delayed (Telegram retries
  on timeout). Voice is out of scope (would need transcription).
- **Handoff-only (dev decision)**: auto-merge is removed from the API
  contract and the console (no `auto_merge` field — extra client fields are
  ignored; the executor never passes `--auto-merge`). Every run ends in a
  draft PR for the developer; the engine's CLI flag stays a manual option
  (`poe bot run … --auto-merge`). The console has a **Handoff checkbox**
  (default on): off = `--wait-ci` (wait for CI checks, still draft — never
  merges). TG (Phase 2) is handoff-only too.
- **Auth split** (dev decision): the **web API/console stays
  unauthenticated** (design's API-Key + IP-whitelist + TG secret-token
  machinery dropped; bind to localhost / a trusted network via
  `BOT_API_HOST`, add auth back later if ever exposed publicly). The
  **Telegram bot is allowlisted** instead: `TG_ALLOWED_USER_IDS`
  (comma-separated Telegram user IDs), denied users ignored silently.
  `TG_BOT_TOKEN` stays a secret — never log it.
- **Single process**: FastAPI serves HTTP + webhook on one event loop;
  `active_runs` is in-memory (restart loses in-flight runs, history file
  survives). ~30–50 MB memory footprint.
- **Concurrency**: worktrees isolated by branch `bot/<slug>/<timestamp>`;
  same-day duplicate tasks (e.g. weight) rely on `update_weight.py`
  idempotency. API must not `--preview` (blocks on a dev server).
- **Network**: `poe bot` needs outbound access (mermaid download, GitHub
  push); `BOT_HTTP_PROXY` is honored by `git_bot.py`'s `_apply_proxy()` —
  the API server process just inherits the env.
- **CI interplay**: `api/` is linted/formatted by repo-wide `poe fmt` /
  `lint-py` (also run by the bot's own CI gate in worktrees), and the
  API deps live in `[project.dependencies]` (no extras), so they are
  always present — no manual `uv sync --extra api` needed.
- **Port**: default `BOT_API_PORT=8100` (documented in `.env.example`) —
  8000 belongs to the mkdocs dev server (`poe server`), and the engine's
  preview already avoids it (`bot-auto-pr-design.md` §1). Port is
  env-driven everywhere (config default host 0.0.0.0); pin `BOT_API_HOST=127.0.0.1` for local-only operation. The
  same port is the webhook/nginx/tunnel target in Phase 2, so it's a
  stable contract once chosen.
- **Webhook exposure (allowlist on top)**: the TG webhook URL is
  effectively public (set via `set_webhook`), so anyone who knows it can
  POST updates — but the allowlist gate (user ID check) runs before any
  command, so fake webhook calls can't start bot runs. Mitigations:
  unguessable path (`/webhook/<random>`), Cloudflare Tunnel access rule /
  restrict ingress to Telegram ASN, or accept the risk for local/polling
  usage. `TG_BOT_TOKEN` stays a secret — never log it.
- **Deployment**: dev = `poe api-server`; prod = `poe api-server-prod` +
  systemd user service, Cloudflare Tunnel or Nginx reverse proxy for
  public access / webhook (Nginx needs SSE/websocket-friendly proxy
  settings: `proxy_buffering off`).
