---
title: Running Track — Health Monitor Integration
created: 2026-07-31
tags: [health, running, health-monitor, integration]
---

# Running Track — Health Monitor Integration

## Goal

Add a **Running Track** page to the Health Monitor section, pulling running
activity data from the existing [running_page](https://github.com/xiongjia/running_page)
project (Strava/Garmin sync → SQLite → JSON export). No cross-repo CI needed —
the macro reads data directly from the running_page project at build time.

The page should show: monthly/yearly distance stats, recent activities,
total distance/elevation, heart rate trends, and optionally a grid-style
running calendar (like the running_page summary poster).

## Data Source Strategy

The MkDocs macro fetches running data at **macro expansion time** (i.e. during
`mkdocs serve` or `mkdocs build`), not via CI. Two approaches, both viable:

| Approach                               | How                                                                                             | When it works                                                 |
| -------------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **activities.json** (local, preferred) | `running_macros.py` reads `../running_page/src/static/activities.json` relative to project root | Both repos cloned, local sync has been run                    |
| **SQLite DB** (fallback)               | `running_macros.py` reads `../running_page/run_page/data.db` and queries the Activity table     | Both repos cloned (DB always has data even without full sync) |

The macro tries `activities.json` first (fast, pre-aggregated), falls back
to querying the SQLite database directly (always has data locally). If neither
is available, shows a friendly "no data" state (graceful degradation).

> Note: `raw.githubusercontent.com` is not used as fallback because
> `activities.json` is a build artifact (~3B placeholder in repo),
> not committed with real data.

## Existing Data Source

`running_page` generates `src/static/activities.json` (from SQLite `Activity` table):

| Field                             | Type       | Description                 |
| --------------------------------- | ---------- | --------------------------- |
| `run_id`                          | Integer PK | Unique activity ID          |
| `name`                            | String     | Activity name               |
| `distance`                        | Float      | Distance (meters)           |
| `moving_time`                     | Interval   | Moving time                 |
| `type`                            | String     | Run / Cycling / Hiking etc. |
| `start_date` / `start_date_local` | String     | Timestamp                   |
| `location_country`                | String     | Location description        |
| `average_heartrate`               | Float      | Avg heart rate              |
| `average_speed`                   | Float      | Avg speed                   |
| `elevation_gain`                  | Float      | Total elevation gain        |

## Tasks

### Phase 1: Data Access Layer

- [ ] **Create `running_macros.py` with data loader**

  - Create `docs/notes/health/macros/running_macros.py`
  - Implement data loader that:
    1. Tries `../running_page/src/static/activities.json` (path relative to project root)
    1. Falls back to `../running_page/run_page/data.db` — query via SQLite
    1. Returns empty dict gracefully if neither available
  - Filter activities to `type == "Run"` (ignore Cycling, Hiking, etc.)
  - Parse timestamps, distances, heart rate into Python objects

- [ ] **Implement macro functions**

  - `running_summary()` — card with: total runs, total distance (km), total time, total elevation gain, avg heart rate
  - `running_year_table()` — yearly table: year, runs, distance, avg pace, avg heart rate, elevation
  - `running_monthly_chart()` — Mermaid bar chart: monthly distance for current year
  - `running_recent()` — table of last 10 activities: date, name, distance, duration, pace
  - `running_monthly_grid()` — (optional) calendar grid heatmap matching running_page poster style

### Phase 2: MkDocs Page

- [ ] **Create Running Track health page**

  - Create `docs/notes/health/running.md`
  - Frontmatter: `icon: material/run-stroke`, `hide: [tags]`
  - Layout: summary cards → yearly table → monthly chart → recent activities

- [ ] **Register macros in mkdocs.yml**

  - Add `running_macros` to `force_render_paths` in the macros plugin config
  - Ensure the module path is discoverable

### Phase 3: Update Site Structure

- [ ] **Update Health Monitor index**

  - Add running page link and mermaid graph node in `docs/notes/health/index.md`
  - Update the graph: `A --> D["🏃 Running Track"]`

- [ ] **Update page tree (mkdocs.yml)**

  - Add `- Running Track: notes/health/running.md` under Health Monitor section

### Phase 4: Polish

- [ ] **Document data source note**

  - Add a comment in `running_macros.py` header explaining data source and fallback strategy
  - Running data is live during `mkdocs serve` — no manual sync needed

- [ ] **Verify & iterate**

  - Run `mkdocs serve` — verify all stats render correctly
  - Test with local clone of running_page present
  - Test graceful degradation when running_page repo is not cloned locally

## Non-Goals

- Displaying map routes (running_page already has this)
- Heart rate zone analysis (too complex for initial version)
- Cross-repo CI / GitHub Actions sync (data is read live from running_page)
- Writing data back to running_page

## References

- [running_page: Activity model](https://github.com/xiongjia/running_page/blob/master/run_page/generator/db.py)
- [running_page: Generated JSON](https://github.com/xiongjia/running_page/blob/master/src/static/activities.json)
- [running_page: data export](https://github.com/xiongjia/running_page/blob/master/run_page/data_to_csv.py)
- [Health Monitor](../../docs/notes/health/index.md)
- [Weight Track macros](../../docs/notes/health/macros/weight_macros.py) — reference pattern
- [Retirement macros](../../docs/notes/health/macros/retire_macros.py) — reference pattern
