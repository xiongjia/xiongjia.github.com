---
title: Bot API Cronjobs — 定时任务调度
created: 2026-08-21
archived: 2026-08-21
status: completed
tags: [bot, api, cron, apscheduler, fastapi]
---

> **Archived 2026-08-21** — implemented, tested (667 suite), and in daily
> use. Remaining optional item deferred (see the phase notes): the
> `source: cron|<name>` history tag was not needed in practice.

# Bot API Cronjobs

## Goal

Add a **cronjob feature to the bot_api server**: scheduled bot runs configured
from `mkdocs.yml`, executed by the running API process, reusing the existing
`poe bot` handoff flow (worktree → task → CI gate → draft PR). Source idea:
git-ignored `internal/local-draft.md`.

Two pilot jobs (the acceptance target):

1. **daily-sync-running** — every day 00:45: `poe sync-running` + upload
   `.running/splits.json` to R2 (`poe sync-running-splits --confirm`) →
   handoff draft PR with the updated `running.yml`
1. **weekly-health-summary** — every Saturday 05:00: regenerate the AI
   health summary (`poe bot run "health-summary"` → local `pi` CLI) →
   handoff draft PR

Future jobs must be addable by editing `mkdocs.yml` alone (config-driven,
no code).

## Design overview

```
mkdocs.yml extra.bot.cron          # job registry (dict keyed by name)
        │  schedule: "45 0 * * *"  # 5-field cron string (server-local TZ)
        │  spec: "sync-running + sync-splits --confirm"   # raw `poe bot run` spec
        │  handoff: true           # draft PR (default; never auto-merge)
        │  enabled: true           # per-job switch (default on)
        │  timezone: …             # optional, default server-local
        ▼
api/cron.py                        # APScheduler AsyncIOScheduler + job wrapper
        │  CronTrigger.from_crontab(schedule, timezone)
        │  coalesce=True, misfire_grace_time=3600
        │  per-job overlap guard (skip if previous run still RUNNING)
        ▼
api/executor.execute_bot_spec()    # NEW: raw-spec entry, validates via
        │                          #   git_bot.parse_task_specs (handles the
        │                          #   '+' composition), shares _run_bot()
        ▼
uv run poe bot run "<spec>" --handoff
        ▼
worktree → task(s) → fmt/lint/test/build → commit → push → 📦 draft PR
```

Everything already exists below the new `execute_bot_spec()` line — the cron
feature is a **thin scheduling shell**, matching the API's existing
"thin shell over `poe bot`" architecture.

## Findings / key decisions

1. **APScheduler (3.x) for the scheduler.** `AsyncIOScheduler` +
   `CronTrigger.from_crontab()` gives correct 5-field cron semantics (DOW/DOM
   OR-rule), timezone handling, coalescing and misfire policy for free.
   Dependency goes into `[project.dependencies]` (no extras — same decision
   as fastapi/PTB/garth; CI and `poe test` must import it). Alternative
   (hand-rolled cron matcher, zero deps) is contained behind `api/cron.py`
   if the dep is ever unwanted.
1. **Cron specs are raw `poe bot run` specs, not single tasks.** Job 1 needs
   two steps in **one** PR (sync + splits upload). The engine already
   supports `spec1 + spec2` composition in one worktree/branch/PR
   (`parse_task_specs` splits on `+`), so a cron job maps to **one**
   `execute_bot_task`-style run whose "task" is the whole spec. The existing
   `execute_bot_task()` validates `task_schema(task)` — a composite spec
   would fail, so cron gets a sibling entry point `execute_bot_spec(spec)`
   that validates with the engine's own `parse_task_specs` instead and shares
   `_run_bot` (streaming logs, outcome detection, history write, abort).
1. **`sync-splits` must become a bot task.** `sync-running-splits` is not in
   the engine registry — a cron spec `… + sync-running-splits --confirm`
   would fail with `unknown task`. Fix: a template task in
   `extra.bot.tasks` (zero engine code):
   ```yaml
   sync-splits:
     args: []
     cmd: ["uv", "run", "python", "scripts/sync_running_splits.py"]
     commit: '[bot] chore(running): upload splits to R2'
     body: "- splits uploaded to R2 (data/metadata/running/splits.json)"
   ```
   The R2 upload stays **dry-run by default** for manual use; the cron spec
   passes `--confirm` explicitly. rclone works from the worktree: binary on
   PATH, credentials in `~/.config/rclone/` (same host user), proxy from
   `.env` (symlinked in) / `BOT_HTTP_PROXY`.
1. **`.running/` must be symlinked into worktrees (sanctioned engine
   change).** The Garmin cache `.running/splits.json` is git-ignored and NOT
   currently symlinked, so a fresh worktree has no cache → `sync_running`
   full-fetches every activity detail on **every** cron run (slow, Garmin
   API load). Add `.running` to `symlink_env()` links and to the
   `remove_worktree()` unlink list; also add it to the `commit_workdir()`
   `git reset --` list (same pattern as `docs/assets/bucket` — protects older
   master checkouts that lack the ignore rule). The worktree sync then
   reads/writes the main-repo cache → incremental across daily runs. This is
   the same class of change as the existing `.venv`/`.env`/`docs/assets/bucket`
   symlinks.
1. **Overlap guard + misfire policy.** A long job (sync + full CI gate takes
   minutes) could still be running when the next daily fire is due — each
   fire would spawn another worktree/PR (same-day duplicate running data is
   mostly no-op thanks to the engine's `⏭ no changes` guard, but avoid PR
   spam). `api/cron.py` tracks last run per job and **skips a fire while the
   previous run is still RUNNING** (log + history note). `coalesce=True` +
   `misfire_grace_time=3600` for missed fires (server down / busy).
1. **In-memory schedule, config is source of truth.** Jobs re-register from
   `mkdocs.yml` at every startup — no jobstore persistence (restart loses
   nothing: schedule comes from config, last-run state from the JSONL
   history). Matches the API's "restart loses in-flight runs, history
   survives" model.
1. **Kill switch + tests.** `BOT_API_CRON_ENABLED=false` (config default
   true) disables all scheduling — tests and ops escape hatch, same pattern
   as `BOT_API_STARTUP_CLEANUP`. Scheduler code must be unit-testable
   without real time (inject a clock / use the cron expression parser
   directly; manual-trigger endpoint is the deterministic test path).
1. **Server must be running for fires to happen.** Cron lives in the API
   process — like the TG bot, it only fires while `poe api-server` runs.
   Deployment note: run under systemd (prod) if 24/7 scheduling is wanted.
1. **Manual trigger endpoint** (`POST /api/cron/{name}/run`) is the smoke
   test path and the "run it now" button — no waiting for 00:45 to verify.

## Tasks

### Phase 1 — Scheduler core + config + API + tests (standalone)

- [x] `pyproject.toml`: add `apscheduler>=3.10,<4` to `[project.dependencies]`
  (no extras — CI lint job + `poe test` import it; note: APScheduler 4.x has
  a different API, pin the 3.x line) — done (`apscheduler==3.11.3`, only
  dep `tzlocal`)
- [x] `mkdocs.yml`: add `extra.bot.cron` (dict keyed by job name; see
  Design overview) and two template tasks under `extra.bot.tasks`
  (Finding 3): `sync-splits` + a zero-arg `hello` smoke task (creates a
  "hello world" moment — every run has a fresh timestamped filename →
  always a diff/PR, the shortest end-to-end bot-flow test). Update the
  `# 参见 internal/local-draft.md` comment under `extra.bucket.running` to
  point at this plan — done
- [x] `api/config.py`: add `cron_enabled: bool = True` (`BOT_API_CRON_ENABLED`,
  kill switch); `.env.example` documents it — **implemented as a dynamic
  env check in `api/cron.py`** (`BOT_API_CRON_ENABLED`, default true) — the
  same pattern as `BOT_API_STARTUP_CLEANUP` in `api/lifespan.py`, which
  keeps it testable (monkeypatchable per test). No `config.py` field.
- [x] `api/cron.py` (new): job config dataclass + loader from
  `extra.bot.cron` via `shared.mkdocs_yaml.load_extra("bot")` (same source as
  `load_task_config`); **fail-fast validation at startup** (bad cron string,
  unknown task in `spec` via `parse_task_specs`, bad `handoff`/`enabled`
  types — loud like `models.validate_schemas()`)
- [x] `api/executor.py`: add `execute_bot_spec(spec, handoff=True, chat_id=None, on_done=None)` — validates the raw spec with `git_bot.parse_task_specs()`,
  builds argv through `assemble_argv(spec, [])`, shares `_run_bot`;
  `execute_bot_task()` stays for the console/TG (single-task schema path)
  — shared spawn extracted into `_spawn_run()`
- [x] `api/cron.py` scheduler: `AsyncIOScheduler`; one job per enabled entry
  with `CronTrigger.from_crontab(schedule, timezone=…)`; `coalesce=True`,
  `misfire_grace_time=3600`; wrapper = overlap guard (per-job last-run
  RUNNING check) → `execute_bot_spec(spec, handoff)`; exceptions logged,
  never crash the scheduler — `_fire` is `async` (sync jobs run off-loop
  and `execute_bot_spec` needs a running loop)
- [x] `api/lifespan.py`: start the scheduler at startup (after TG init),
  `scheduler.shutdown(wait=False)` at shutdown; in-flight cron runs are
  terminated with the other runs in the existing graceful shutdown
- [x] `api/routers/cron.py` (new): `GET /api/cron` — configured jobs with
  `schedule`/`enabled`/`spec`/`next_run_at`/`last_run` (last run tracked
  in-memory per job — the JSONL history stays the durable record);
  `POST /api/cron/{name}/run` — manual trigger →
  `execute_bot_spec`, returns the standard run response; 404 on unknown job.
  Mounted in `api/server.py`
- [x] `tests/api/test_cron.py`: config load + fail-fast validation (bad cron
  string, unknown task, bad type), `parse_task_specs` acceptance of the two
  pilot specs, overlap guard, `BOT_API_CRON_ENABLED=false` disables, manual
  trigger (monkeypatch `execute_bot_spec` — no real `poe bot`), `GET /api/cron` shape. Keep `api/` ruff-clean (repo-wide `poe fmt`/`lint-py`)
  — 18 tests, full suite 661 passing, ruff clean
- [x] `api/models.py` (small): `_TASK_FIELDS["sync-splits"] = []` so the
  schema endpoint serves it (console/manual runs stay possible) — **not
  needed**: the generic fallback schema already serves zero-arg tasks
  (verified `GET /api/schema/hello` → `{"task":"hello","fields":[]}`)

### Phase 2 — Engine symlink + pilot jobs + smoke test

- [x] `scripts/git_bot.py` (sanctioned engine change, Finding 4): add
  `.running` to `symlink_env()` links, the `remove_worktree()` unlink list,
  and the `commit_workdir()` `git reset --` list; `.running` stays
  git-ignored → nothing new gets staged — done, all three sites
- [x] `mkdocs.yml` `extra.bot.cron`: define the two pilot jobs
  - `daily-sync-running`: `schedule: "45 0 * * *"`, `spec: "sync-running + sync-splits --confirm"`, `handoff: true`
  - `weekly-health-summary`: `schedule: "0 5 * * SAT"`, `spec: "health-summary"`,
    `handoff: true`
    (text names for DOW — see the DOW note below)
  - `smoke-hello` (added 2026-08-21): `schedule: "0 13 * * *"`,
    `spec: "hello"`, `handoff: true` — daily auto-trigger of the hello
    smoke task (every run has a diff → real draft PR; close it manually).
    This exercises the *scheduled* fire path (not just the manual trigger)
- [x] Smoke test (local, real): `poe api-server` →
  `GET /api/cron` shows both jobs + next runs →
  `POST /api/cron/daily-sync-running/run` fires a real handoff PR
  (running.yml updated + splits uploaded to R2 + draft PR link) →
  `POST /api/cron/weekly-health-summary/run` fires a health-summary PR
  (local `pi` CLI). Verify in the console (history pane) and on GitHub
  — done in practice: real fires were observed and debugged live (the
  20:02 commit-guard bug and the 20:10 Garmin timeout — both fixed with
  regression coverage); the end-to-end worktree → CI → draft-PR path was
  proven by the `hello` smoke task (PR #132). `GET /api/cron` verified
  live with correct `next_run_at` (incl. the APScheduler DOW fix).
- [x] Optional (deferred if scope creeps): console UI — small "Cron" pane
  listing jobs + next run + a manual "Run now" button (reuses `/api/cron`
  endpoints; no console change required for the feature to work)
  — **done (2026-08-21)**: `#cron-pane` in the console (second grid row
  under the work pane): job / schedule (spec + timezone in tooltip) / next
  run (localized) / last run (status + PR link) / ▶ Run button. "Run now"
  triggers `POST /api/cron/{name}/run` and streams the run into the live
  output pane (abort button + fast history poll included). Panel refreshes
  on a 30 s timer and right after a trigger. Verified via headless-Chrome
  DOM dump (both pilot jobs render, correct next runs, two ▶ buttons).
- [ ] Optional (deferred, archived as-is): `source: cron|<name>` tag on
  cron-run history records (`api/state.py` `BotRun` + `to_dict`, executor)
  so the history endpoint/console can filter cron runs — not needed in
  practice; last-run attribution via spec match is sufficient

## Notes

- **APScheduler DOW quirk (verified 2026-08-21)**: `CronTrigger.from_crontab`
  maps DOW numbers 0=Monday … 6=Sunday (unlike standard cron's 0=Sunday),
  while text names (`SAT`, `SUN`, …) keep the standard meaning. Always use
  text names in `extra.bot.cron` schedules; the pilot `weekly-health-summary`
  is `"0 5 * * SAT"` (Saturday).

- **hello smoke task** (added 2026-08-21, `extra.bot.tasks.hello`):
  zero-arg task that creates a "hello world" moment via `create_moment.py` —
  non-empty content skips the EDITOR step (create_moment only opens the
  editor when content is empty), and the timestamped filename (`%d-%H%M`)
  guarantees a diff every run, so it always ends in a real draft PR. Fastest
  end-to-end check of the bot flow (worktree → task → CI → PR) and of a
  cron trigger: wired as the `smoke-hello` cron job (daily 13:00, see
  Phase 2) or manual `POST /api/cron/smoke-hello/run`; close the PR after
  each test run.

- **Handoff-only**: cron runs never auto-merge — same dev decision as the
  console and TG (`handoff` default true, engine `--auto-merge` stays a
  manual CLI option).

- **Runtime enable/disable (added 2026-08-21)**: `POST /api/cron/{name}/disable|enable` pauses/resumes a job on the running
  scheduler and persists the override in the git-ignored
  `.bot-api/cron-state.json` (next to the run history; `{name: {disabled_at}}`, atomic tmp+rename write) — survives restarts (a disabled
  job is not scheduled at startup, re-enabling registers it on the fly).
  `GET /api/cron` reports `enabled` (static config), `disabled` (runtime
  override) and `active` (both). Console shows a `(paused)` badge + ⏸/▶
  toggle per row. Manual run-now still works on a disabled job (explicit
  action).

- **Timezone**: `schedule` is interpreted in the server's local timezone by
  default; set `timezone: "Asia/Shanghai"` per job to pin it explicitly.

- **Credentials**: all secrets stay in the host `.env` / `~/.config/rclone/`
  / `~/.pi` — the cron feature adds nothing secret to the repo; the worktree
  gets `.env` via the existing symlink.

- **Incremental by design**: the `.running` symlink keeps the daily Garmin
  fetch incremental (cache lives in the main repo, shared across runs);
  `sync_running_splits` uploads the same cache file, so the R2 payload is
  exactly what the repo's running data references (`extra.bucket.running.data_key`).

- **Failure behavior**: a failed cron run is a normal FAILED run in history
  (log tail, no PR) — no alerting in scope; the TG completion push pattern
  (`on_done`) could later be wired to notify on cron failure.

- **Deployment**: scheduling requires the API process to be up — prod runs
  `poe api-server-prod` under systemd (already the deployment model); a
  machine-level `cron`/`systemd.timer` alternative exists but would bypass
  the mkdocs.yml config (out of scope here).

- **Concurrency**: cron runs use the engine's normal worktree isolation;
  a cron run overlapping a console/TG run is safe (separate worktrees). The
  per-job overlap guard only prevents the *same job* stacking.
