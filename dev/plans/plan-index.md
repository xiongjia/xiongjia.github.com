# Plan Index

> Track implementation plans, feature work, refactoring, research tasks, and
> their progress. Each plan is a separate file under `dev/plans/`.

## Creating a New Plan

Create `<plan-name>.md` under `dev/plans/` using the template below.

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

- **Plan**: create the `.md` file under `dev/plans/`
- **Done / Cancelled**: delete the file — that's it

## Plan List

<!-- Manually maintained — add new plans here -->

### Site Feature

- [moment-phase2-usability.md](./moment-phase2-usability.md) — Moment Plugin Phase 2: RSS, Archive, OpenGraph
- [moment-phase3-personal.md](./moment-phase3-personal.md) — Moment Plugin Phase 3: Location, Map, Gallery, Search, Stats
- [mkdocs-backlinks-topology.md](./mkdocs-backlinks-topology.md) — MkDocs bidirectional links & link topology graph (backlinks + Mermaid graph)

### Research

- [indie-game-tool-research.md](./indie-game-tool-research.md) — Indie Game Tool Research: Godot, Krita, LDTK, Tiled, Blender
- [maplibre-research.md](./maplibre-research.md) — MapLibre GL JS & Protomaps Research: MapLibre, PMTiles, Tippecanoe
- [hands-on-data-viz-reading.md](./hands-on-data-viz-reading.md) — Hands-On Data Visualization Reading Plan: data viz from spreadsheets to code

### Posts

- [post-weight-track.md](./post-weight-track.md) — Blog post: Weight Track implementation
- [post-retirement-countdown.md](./post-retirement-countdown.md) — Blog post: Retirement Countdown implementation

### Site Feature

- [running-track-health-monitor.md](./running-track-health-monitor.md) — Running Track: health monitor integration with running_page data

### Projects

- [city-log-project.md](./city-log-project.md) — City Log: offline city check-in PWA (MapLibre + PMTiles), with preliminary analysis
- [city-log-design-plan.md](./city-log-design-plan.md) — City Log design document (archived)

### Refactor

- [plugins-scripts-shared-module.md](./plugins-scripts-shared-module.md) — MkDocs plugins & scripts: extract shared utilities, reduce duplication
