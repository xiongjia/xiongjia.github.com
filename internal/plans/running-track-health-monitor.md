---
title: Running Track — Health Monitor Integration
created: 2026-07-31
updated: 2026-08-03
tags: [health, running, health-monitor, integration]
---

# Running Track — Health Monitor Integration

## Goal

Add a **Running Track** page to the Health Monitor section. This repo **does
not sync running data itself** — running data already lives in the deployed
[running_page](https://xiongjia.github.io/running_page/) site (Strava/Garmin
sync → SQLite → JSON → GitHub Pages). We only consume it:

- A **manual sync command** (`uv run poe sync-running`) pulls the data from
  the deployed running_page site (`https://xiongjia.github.io/running_page/`,
  not `/summary` — see Data Source) and stores it into a local data yaml file
  (`docs/notes/health/data/running.yml`).
- The **MkDocs macros read the local yaml only** — no network access at build
  or serve time, and no local `running_page` clone is required.
- **Auto-sync (scheduled/CI) is a later phase**, deliberately split out so the
  manual-sync path (Phase 1) can be completed on its own.

The page should show: monthly/yearly distance stats, recent activities, total
distance/elevation, heart rate trends, and optionally a grid-style running
calendar (like the running_page summary poster).

## Data Source

Single source: the deployed running_page site —
`https://xiongjia.github.io/running_page/summary`.

The `/summary` path is only a human-facing page reference — on GitHub Pages it
returns **HTTP 404** with a custom `404.html` that does a client-side redirect
(running_page's SPA fallback), so it must **not** be used as the fetch URL
(`urllib` raises `HTTPError 404`). Fetch the index instead; the actual
activity data ships inside a **hashed JS asset**:

1. `GET https://xiongjia.github.io/running_page/` → HTML (HTTP 200)
1. Find the `activities-<hash>.js` asset in the HTML — it appears as
   `<link rel="modulepreload" href=".../assets/activities-<hash>.js">`
   (match both `src` and `href`; the filename changes on every data refresh)
1. `GET .../assets/activities-<hash>.js` → contains `JSON.parse('[...]')` —
   the full activities array (JS-string-escaped)
1. Unescape (JS string literal rules: `\\`, `\'`, `\"`, `\uXXXX`, …) and
   parse the JSON array

> The upstream running_page project owns the data itself
> (`.github/workflows/run_data_sync.yml` syncs daily and redeploys GitHub
> Pages). This repo never talks to Strava/Garmin and never runs running_page's
> sync logic — it only downloads the published result.

### Activity fields

| Field                             | Type       | Description                                                                 |
| --------------------------------- | ---------- | --------------------------------------------------------------------------- |
| `run_id`                          | Integer PK | Unique activity ID                                                          |
| `name`                            | String     | Activity name                                                               |
| `distance`                        | Float      | Distance (meters)                                                           |
| `moving_time`                     | Interval   | Moving time, e.g. `"0:19:42.196000"`                                        |
| `type`                            | String     | `"Run"` / `"cycling"` — mixed case in deployment, filter case-insensitively |
| `subtype`                         | String     | Sub-type                                                                    |
| `start_date` / `start_date_local` | String     | Timestamp `"YYYY-MM-DD HH:MM:SS"`                                           |
| `location_country`                | String     | Location description                                                        |
| `average_heartrate`               | Float      | Avg heart rate                                                              |
| `average_speed`                   | Float      | Avg speed (m/s)                                                             |
| `elevation_gain`                  | Float      | Total elevation gain (m)                                                    |
| `summary_polyline`                | String     | Route polyline — heavy, dropped when writing the yaml                       |
| `streak`                          | Int        | running_page per-activity streak (optional)                                 |

## Sync Strategy

- **No fetch at build time**: `mkdocs build` / `mkdocs serve` never touch the
  network. Data is only refreshed when the sync command is run explicitly.
- **Manual sync (Phase 1)**: `uv run poe sync-running` →
  `scripts/sync_running.py` fetches from the deployed site and writes
  `docs/notes/health/data/running.yml` (activities + `synced_at` timestamp).
- **Auto-sync (Phase 4, future)**: a scheduled GitHub Actions workflow that
  runs the same script and commits the yaml when it changes. Deliberately
  split out — Phases 1–3 work with the manual command alone.

## Tasks

### Phase 1: Sync script + local data (standalone — can be completed alone)

- [x] **Create `scripts/sync_running.py`** (snake_case per repo convention)

  - Fetch `https://xiongjia.github.io/running_page/` (NOT `/summary` — that
    path returns HTTP 404 with a client-side redirect page), and locate the
    `activities-<hash>.js` asset URL in the HTML (`src` or `href`)
  - Fetch the bundle, extract and unescape the `JSON.parse('[...]')` payload
  - Filter `type == "Run"` (case-insensitive), drop `summary_polyline`
  - Write `docs/notes/health/data/running.yml`: `synced_at` + activities list
  - Idempotent; prints a short summary (activity count, date range); clean
    error + nonzero exit on network/parse failure

- [x] **Register poe task**

  - `sync-running = { cmd = "python scripts/sync_running.py", help = "Sync running data from running_page into docs/notes/health/data/running.yml" }` in `pyproject.toml`

- [x] **Generate the first data file**

  - `docs/notes/health/data/running.yml` produced by the script (generated; not yet `git commit`ed)

- [x] **Create `docs/notes/health/macros/running_macros.py`** — reads the
  local yaml only (no network)

  - `running_summary()` — card: total runs, total distance (km), total time,
    total elevation gain, avg heart rate
  - `running_year_table()` — yearly table: year, runs, distance, avg pace,
    avg heart rate, elevation
  - `running_monthly_chart()` — merged Mermaid chart: monthly distance bar +
    avg HR line on one plot (see design doc for the single-y-axis constraint)
  - `running_recent()` — table of the last 2 weeks (falls back to last 10)
  - `running_all()` — all activities in a collapsed `???` block
  - `running_synced_at()` — note showing the last `synced_at` timestamp
  - `running_monthly_grid()` — (optional) calendar grid heatmap matching
    running_page poster style (not implemented)
  - Graceful "no data" state if the yaml is missing → show hint to run
    `uv run poe sync-running`

- [x] **Unit tests**

  - `tests/test_sync_running.py`: extractor/unescaper tests with a fixture
    (no network in tests)
  - Macro tests reading a small yaml fixture (sorted newest-first behaviour)

### Phase 2: MkDocs Page

- [x] **Create Running Track health page**

  - Create `docs/notes/health/running.md`
  - Frontmatter: `icon: fontawesome/solid/person-running` (Material icon set has no running icon), `hide: [tags]`
  - Layout: summary cards → yearly table → merged monthly chart → recent (2 weeks) → all activities (collapsed)
  - Show "data synced at `<synced_at>`" note + hint to re-run
    `uv run poe sync-running` for fresher data

- [x] **Register macros in mkdocs.yml**

  - Add `running_macros` to the macros plugin config (via the
    `health_macros.py` loader pattern)

### Phase 3: Update Site Structure

- [x] **Update Health Monitor index**

  - Add running page link and mermaid graph node in `docs/notes/health/index.md`
  - Update the graph: `A --> D["🏃 Running Track"]`

- [x] **Update page tree (mkdocs.yml)**

  - Add `- Running Track: notes/health/running.md` under Health Monitor section

### Phase 4: Auto-sync (future — split out, not required for Phase 1)

- [ ] **Scheduled CI workflow** (e.g. `.github/workflows/sync-running.yml`)
  - Daily/weekly schedule: run `uv run poe sync-running`, commit
    `docs/notes/health/data/running.yml` if changed
  - Uses the same fetch-from-deployed-site logic as Phase 1 — no secrets, no
    cross-repo clone needed
- [ ] **Optional: docs note** on stale-data behavior (page shows last
  `synced_at`)

## Iterations after the initial phases (completed)

Beyond the checklist above, the following product iterations were implemented
and are documented in the [design doc](../running-track-design.md):

- **Heart-rate data**: `Avg HR` column added to activity tables; merged into
  the monthly chart as a `line` series
- **Recent scope**: `running_recent()` shows the last 2 weeks, falling back
  to the last 10 activities when data is older
- **All activities**: added a collapsed-by-default `???` block
- **Merged chart**: monthly distance (`bar`) and avg heart rate (`line`)
  merged into a single Mermaid plot (single y-axis, no null values)
- **Narrower tables**: `Date` / `Time` / `Duration` merged into one column;
  a note above the table explains `Avg HR` and `Pace (/km)` abbreviations

## Non-Goals

- Syncing running data itself (Strava/Garmin) — that lives in running_page
- Fetching data at build/serve time — data updates only via
  `uv run poe sync-running` (or auto-sync in Phase 4)
- Displaying map routes (running_page already has this)
- Heart rate zone analysis (too complex for initial version)
- Writing data back to running_page

## References

- [Running Track — Design Doc](../running-track-design.md) — architecture & rendering decisions
- [Deployed running_page site](https://xiongjia.github.io/running_page/) — data source
- [running_page: run_data_sync.yml](https://github.com/xiongjia/running_page/blob/master/.github/workflows/run_data_sync.yml) — upstream sync schedule
- [running_page: Activity model](https://github.com/xiongjia/running_page/blob/master/run_page/generator/db.py)
- [Health Monitor](../../docs/notes/health/index.md)
- [Weight Track macros](../../docs/notes/health/macros/weight_macros.py) — reference pattern
- [Retirement macros](../../docs/notes/health/macros/retire_macros.py) — reference pattern
- [add_weight_week.py](../../scripts/add_weight_week.py) — script + poe task + test pattern
