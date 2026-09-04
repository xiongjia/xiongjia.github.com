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

- [moment-phase3-personal.md](./moment-phase3-personal.md) — Moment Plugin Phase 3: Location ✅ + Map ✅ + multi-image ✅ + lightbox grouping ✅ + EXIF camera/date ✅ + Stats ✅; cancelled: Grid/Masonry (G1); parked: search filter, City-Log (G5/G6); open: JSON Feed, auto-tag, streak stat
- [tools-assets-externalize.md](./tools-assets-externalize.md) — Notes Tools: extract inline JS/CSS from tool pages into standalone assets (deferred)
- [mkdocs-media-archive.md](./mkdocs-media-archive.md) — MkDocs Media Archive: 用 MkDocs 归档看过的书/影片/游戏（调研方案 → 数据模型 → 索引页）
- [collection-scrape.md](./arch/collection-scrape.md) — Collection Scrape: 日常随手收集（poe collect-add/todo/idea）+ AI 整理 + Plans 面板 ✅

### Research

- [indie-game-tool-research.md](./indie-game-tool-research.md) — Indie Game Tool Research: Godot, Krita, LDTK, Tiled, Blender
- [maplibre-research.md](./maplibre-research.md) — MapLibre GL JS & Protomaps Research: MapLibre, PMTiles, Tippecanoe
- [hands-on-data-viz-reading.md](./hands-on-data-viz-reading.md) — Hands-On Data Visualization Reading Plan: data viz from spreadsheets to code
- [cloudflare-kv-research.md](./cloudflare-kv-research.md) — Cloudflare KV Database Research/Prototype: 读写模型、TTL、缓存语义、限制定价、wrangler demo
- [tauri-ui-research.md](./tauri-ui-research.md) — Tauri UI Research/Prototype: Tauri 2 桌面 + 移动端（架构、IPC、插件、打包）
- [improve-lux-research.md](./improve-lux-research.md) — Improve Lux Research: 核对上游更新、补全缺失、修正过时内容
- [improve-trip-research.md](./improve-trip-research.md) — Improve TRIP Research: 核对上游、补全前后端机制与实操说明

### Posts

- [post-weight-track.md](./post-weight-track.md) — Blog post: Weight Track implementation
- [post-fitness-counter.md](./post-fitness-counter.md) — Blog post: Fitness Counter implementation
- [post-retirement-countdown.md](./post-retirement-countdown.md) — Blog post: Retirement Countdown implementation

### Projects

- [city-log-project.md](./city-log-project.md) — City Log: offline city check-in PWA (MapLibre + PMTiles), with preliminary analysis
- [raft-db.md](./raft-db.md) — Raft + LevelDB 分布式高可用 KV 数据库原型：raft（etcd-io/raft 或 raft-rs）+ LevelDB，选主/日志复制/故障转移（内容落在 `docs/notes/research/topics/raft-db/`，实现落 `prototypes/raft-db/`）

### Reading

- [reading-list.md](./reading-list.md) — 阅读计划（定期维护清单）：理解 CloudFlare-ImgBed、阅读 Python for GIS 等
- [reading-items.md](./reading-items.md) — Reading Items 队列文件：机器可读阅读条目 + 完成/失败记录（独立于已归档的 reading-assist 开发计划，见 `arch/reading-assist.md`；`poe reading-assist list` 读取，`cache`/`read`/`run` 处理）

### Learning

- [hollow-knight-english-learning.md](./hollow-knight-english-learning.md) — Hollow Knight 英语阅读主题（内容落在 `docs/notes/research/topics/english/hollow-knight/`；词汇积累走 English Scraps）
- [english-scraps.md](./english-scraps.md) — English Scraps：日常英语碎片（生词/语法/难句/搭配）随手收集 + AI 归档（内容落在 `docs/notes/research/topics/english/scraps/`）
- [duckdb-internals-learning.md](./duckdb-internals-learning.md) — DuckDB Internals 学习计划（Greybeam 系列）：查询生命周期、列式存储、向量化执行（内容落在 `docs/notes/research/topics/duckdb/`）
- [pgsimcity-learning.md](./pgsimcity-learning.md) — PGSimCity 学习计划：PostgreSQL 内部机制 3D 可视化（缓冲池、WAL、检查点、autovacuum、复制）（内容落在 `docs/notes/research/topics/pgsimcity/`）
- [tsdb-from-scratch.md](./tsdb-from-scratch.md) — TSDB from scratch 学习计划：精读 write-tsdb-from-scratch 系列 + 自己实现基本 TSDB（内容落在 `docs/notes/research/topics/tsdb/`，实现落 `prototypes/tsdb-from-scratch/`）
