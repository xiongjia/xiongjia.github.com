# Plan Index

> Track implementation plans, feature work, refactoring, research tasks, and
> their progress. Each plan is a separate file under `internal/plans/`.

## Creating a New Plan

Create `<plan-name>.md` under `internal/plans/` using the template below.

## Template

```markdown
---
title: Plan Title
created: 2025-01-01
tags: [tag1, tag2]
---

# Plan Title

## Goal

Brief description of what this plan aims to achieve.

## Tasks

- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

## Notes

Additional context, references, etc.
```

## Lifecycle

- **Plan**: create the `.md` file under `internal/plans/`
- **Done / Cancelled**: move the file to `internal/plans/arch/` (git mv keeps history)
  and remove its entry from the Plan List below

### Archive Convention

Archived plans live in `internal/plans/arch/<plan-name>.md` and carry frontmatter
for future auditing:

```yaml
---
created: 2026-07-31        # when the plan was created
archived: 2026-08-01       # when it was archived
status: completed          # completed | cancelled
tags: [refactor, mkdocs]
---
```

- `status: completed` — all tasks done
- `status: cancelled` — abandoned / superseded (note the reason in the body)

## Plan List

<!-- Manually maintained — add new plans here -->

### Site Feature

- [moment-phase3-personal.md](./moment-phase3-personal.md) — Moment Plugin Phase 3: Location, Map, Gallery, Search, Stats
- [running-track-health-monitor.md](./running-track-health-monitor.md) — Running Track: health monitor integration with running_page data

### Research

- [indie-game-tool-research.md](./indie-game-tool-research.md) — Indie Game Tool Research: Godot, Krita, LDTK, Tiled, Blender
- [maplibre-research.md](./maplibre-research.md) — MapLibre GL JS & Protomaps Research: MapLibre, PMTiles, Tippecanoe
- [hands-on-data-viz-reading.md](./hands-on-data-viz-reading.md) — Hands-On Data Visualization Reading Plan: data viz from spreadsheets to code

### Posts

- [post-weight-track.md](./post-weight-track.md) — Blog post: Weight Track implementation
- [post-retirement-countdown.md](./post-retirement-countdown.md) — Blog post: Retirement Countdown implementation
- [post-rtk-token-saving.md](./post-rtk-token-saving.md) — Blog post: RTK usage & token saving

### Projects

- [city-log-project.md](./city-log-project.md) — City Log: offline city check-in PWA (MapLibre + PMTiles), with preliminary analysis

### Reading

- [reading-list.md](./reading-list.md) — 阅读计划（定期维护清单）：理解 CloudFlare-ImgBed、阅读 Python for GIS 等

### Learning

- [hollow-knight-english-learning.md](./hollow-knight-english-learning.md) — Hollow Knight 英语学习计划：阅读、词汇、发音、Shadowing、口语、写作（内容落在 `docs/notes/research/topics/english/`）
- [duckdb-internals-learning.md](./duckdb-internals-learning.md) — DuckDB Internals 学习计划（Greybeam 系列）：查询生命周期、列式存储、向量化执行（内容落在 `docs/notes/research/topics/duckdb/`）
- [pgsimcity-learning.md](./pgsimcity-learning.md) — PGSimCity 学习计划：PostgreSQL 内部机制 3D 可视化（缓冲池、WAL、检查点、autovacuum、复制）（内容落在 `docs/notes/research/topics/pgsimcity/`）
