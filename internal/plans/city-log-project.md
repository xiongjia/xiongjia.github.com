---
title: City Log — Offline City Check-in App (Project Plan)
created: 2026-07-31
tags: [city-log, pwa, maplibre, pmtiles, offline-first, project]
---

# City Log — Offline City Check-in App

## Goal

Build **City Log**, a personal city-footprint recorder (Web App / PWA): photos + map
dual core, fully offline-capable, no account needed, data owned entirely by the user.
Open the app → see the map → tap to mark a check-in → view it on map, timeline, and
photo grid.

Design document (archived): [city-log-design-plan.md](./arch/city-log-design-plan.md)

______________________________________________________________________

## Preliminary Analysis (初步分析)

### Strengths — the plan is solid

1. **Stack overlaps the existing knowledge base** — MapLibre GL JS + PMTiles +
   Protomaps is exactly the combination researched in
   [maplibre-research.md](./maplibre-research.md) and the
   [Maps collection](../../docs/notes/collection/maps.md): `pmtiles` protocol
   registration, `@protomaps/basemaps` style generation with `lang` support (中文标签),
   Tippecanoe, `pmtiles extract` bbox clipping. Findings are reusable → faster Phase 1.
1. **SW Range caching design is the documented PMTiles pattern** — cache the whole
   `.pmtiles` as one blob and serve 206 Range slices from it is the official
   recommendation; at city scale (5–15 MB) Cache-First is correct.
1. **Well-scoped & testable** — clear acceptance criteria per phase (DevTools Offline
   render, full offline use after "Add to Home Screen"), no account/auth complexity.
1. **Reasonable roadmap** — 4 phases / ~4 weeks with a clean dependency order
   (map base → check-in core → views → polish/PWA).
1. **Simple data model** — IndexedDB + Dexie is more than enough for thousands of
   check-ins; `lat/lng/visitedAt/*tags` indexes cover the main queries.

### Gaps & risks

1. **Photos are the biggest data-loss risk** — IndexedDB quota and browser eviction
   (especially Safari) can silently wipe Blob data. Must evaluate OPFS and, more
   importantly, **pull data export/backup forward** (v1.3 → v1.0/1.1). Photos + JSON
   export is not a nice-to-have; it is the safety net for an offline-only app.
1. **EXIF parsing is missing** — `takenAt` comes from EXIF but no parsing lib is in the
   stack (e.g. `exifr`). Add to Phase 2.
1. **Photo ↔ check-in relation is redundant** — `CheckIn.photos[]` vs `Photo.checkInId`
   both exist; needs a single data-access layer to avoid inconsistency.
1. **Add-check-in interaction is ambiguous** — flow diagram says FAB → "click a map
   position", while 4.4 says long-press map OR FAB. Decide one canonical flow in
   Phase 2 (recommend: long-press adds, FAB just opens a hint — or pick one).
1. **Framework undecided** — "Vanilla / Vue 3 / React (any)" but the file structure is
   already Vue components (`MapView.vue`…). Lock **Vue 3 + Vite** before Phase 1.
1. **SW ↔ Vite integration point unspecified** — `src/sw.js` needs a build-time story
   (`vite-plugin-pwa` vs static `public/sw.js` + manual registration + version bump
   strategy for map cache). Spike in Phase 1.
1. **Pre-cache vs on-demand are two coexisting strategies** — pre-caching the whole
   PMTiles gives full offline at install cost; fine at city scale, but the update
   mechanism (cache version bump + `skipWaiting` + prompt) must be defined.
1. **Chinese labels depend on basemaps `lang` config** — the style must be generated
   with `lang: "zh"` and kept in sync with the data file version (add a style build
   script next to `extract-city.js`).
1. **Clustering / trajectory performance unproven** — DOM Marker clustering caps at
   ~hundreds of markers; for dense cities consider `symbol`/`circle` layers +
   `geojson-source` clustering (already covered in the maplibre research plan).
1. **"Navigate" action undefined** — detail sheet's navigation button needs a concrete
   implementation (system map URI, e.g. `geo:`/`maps:` links).
1. **Repo location undecided** — design assumes a standalone app; recommend a separate
   repo (e.g. `~/Work/self/city-log`) rather than living inside this site repo.

### Decisions needed (before/early in Phase 1)

| #   | Decision          | Recommendation                                                        |
| --- | ----------------- | --------------------------------------------------------------------- |
| D1  | Framework         | Vue 3 + Vite (structure already implies it)                           |
| D2  | Photo storage     | IndexedDB Blob first, evaluate OPFS; add quota/eviction handling      |
| D3  | Add-check-in flow | Long-press map adds; FAB shows hint — or single canonical flow        |
| D4  | Export/backup     | Pull into v1.0 scope (JSON + photos, import/export)                   |
| D5  | Repo location     | New standalone repo, e.g. `~/Work/self/city-log`                      |
| D6  | SW strategy       | `vite-plugin-pwa` + manual range-cache SW; version-bump update policy |

### Scope recommendation

Keep Phase 1–2 strictly as designed (map base + check-in core). Fold the **export/
backup** and **EXIF parsing** into Phase 2. Defer multi-city (v1.1), trajectory
animation, social sharing, and native packaging — all confirmed non-critical.

______________________________________________________________________

## Tasks

### Phase 0: Decisions & skeleton (0.5 week)

- [ ] Lock D1–D6; init repo + Vite + Vue 3 skeleton
- [ ] Spike: SW + Vite integration (`vite-plugin-pwa` vs `public/sw.js`), Range-cache
  handler against a real PMTiles file
- [ ] Spike: OPFS vs IndexedDB Blob for photo storage (write/read 20+ MB, quota check)
- [ ] Finalize data model in code (Dexie schema, single data-access layer for photos)
- [ ] Deliverable: README with decided architecture; spike notes appended here

### Phase 1: Map base (map offline) — per design doc

- [ ] Integrate MapLibre GL JS + `pmtiles` protocol (reuse research notes findings)
- [ ] Download & `pmtiles extract` target city (Shanghai bbox), ~5–15 MB
- [ ] Style build script: generate `city-style.json` from `@protomaps/basemaps`
  (`lang: "zh"`), committed/pinned to the data file version
- [ ] Register Service Worker; pre-cache PMTiles; serve 206 Range slices from cache
- [ ] Verify: DevTools Offline → map still renders & pans
- [ ] Deliverable: offline map milestone (acceptance per design doc §6 Phase 1)

### Phase 2: Check-in core — per design doc, plus gaps

- [ ] IndexedDB schema (Dexie): checkIns, photos, settings
- [ ] Add-check-in flow (D3 decision): long-press map / FAB → form
  (title, note, tags, rating, photo upload)
- [ ] Photo pipeline: EXIF parse (`exifr`) → `takenAt`; compress (1200px/0.85) +
  thumbnail generation (Canvas)
- [ ] Custom DOM marker (44px photo thumbnails, selected pulse state)
- [ ] Detail Bottom Sheet: gallery, title/rating, tags, notes, meta, actions
  (navigate via system map URI, edit, delete)
- [ ] **Export/import (D4)** — GeoJSON/JSON + photos bundle; restore path
- [ ] Verify: add → view → edit → delete closed loop; data survives reload
- [ ] Deliverable: check-in core milestone

### Phase 3: Timeline, grid & filtering — per design doc

- [ ] Bottom horizontal timeline (recent check-ins, desc)
- [ ] Timeline ↔ map marker two-way highlight/flyTo
- [ ] Full-screen timeline (month-grouped) via sheet expand
- [ ] Grid view (month-grouped photo wall) + view switch animation
- [ ] Filter panel (tags / time range) with map+list sync
- [ ] Empty states
- [ ] Deliverable: three views milestone

### Phase 4: Polish & PWA — per design doc, plus backup

- [ ] PWA manifest, icons, theme color, installability
- [ ] All resources offline-capable (SW asset caching)
- [ ] Lazy photo loading (IntersectionObserver)
- [ ] Marker clustering (symbol-layer clustering for dense data)
- [ ] Dark mode; gesture handling (map vs bottom-sheet scroll conflict)
- [ ] Lighthouse > 90; manual offline audit on mobile
- [ ] Data safety pass: export reminder / periodic backup prompt
- [ ] Deliverable: installable, fully-offline v1.0

## Non-Goals

- Multi-city switching (v1.1), trajectory animation (v1.2)
- Cloud sync / E2E encryption (v2.0), social share cards (v2.1)
- Native packaging (v3.0 — Capacitor/Tauri)
- Social feed, accounts, or any server-side component

## Notes

- Synergy: `maplibre-research.md` plan covers exactly this stack (pmtiles protocol,
  basemaps lang, clustering, tippecanoe) — work through it first, then implement
- Protomaps daily builds are archived to a date-stamped file (e.g. `20260727.pmtiles`);
  pin the data version and regenerate style from the same version
- Chinese labels require `lang` support at style-generation time, not runtime

## References

- [city-log-design-plan.md](./arch/city-log-design-plan.md) — archived design document
- [maplibre-research.md](./maplibre-research.md) — MapLibre/PMTiles/Protomaps research plan
- [Maps collection](../../docs/notes/collection/maps.md) — MapLibre, Protomaps, PMTiles links
- [PMTiles docs](https://docs.protomaps.com/pmtiles/) — format & SW range caching
- [Dexie.js](https://dexie.org/) — IndexedDB wrapper
