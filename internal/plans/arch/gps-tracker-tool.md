---
title: GPS Location Recorder Tool (Notes Tools)
created: 2026-08-13
archived: 2026-08-13
status: completed
tags: [tools, gps, location, map, frontend, notes-tools]
---

# GPS Location Recorder Tool (Notes Tools)

## Goal

Add a pure-frontend tool 「📍 GPS 位置记录」 under **Notes → Tools**
(`docs/notes/tools/`): temporarily record the current GPS position from a phone
(typical use: recording metro stations / waypoints while commuting), with multiple
location marks, one-click clear, and copy/export of coordinates for later creating
Moments (`poe create-moment --lng --lat`) or curating a city footprint.

Reuse the moments Geo/Map approach (see `internal/moment-design.md` → Geo / Map
Features): browser Geolocation API for WGS-84 coordinates + region bbox probing +
the vine map widget (`createMapWidget`) for map rendering. Data stays in browser
localStorage, never uploaded (consistent with the Tools page motto:
「数据不会离开浏览器」).

Requirements source: `internal/local-draft.md` (366B — this plan is its
implementation plan).

## Requirements

1. Temporarily record the current GPS position from a phone
1. Reuse the same GPS approach as moments (see moment-design)
1. Special handling for locations outside the map regions (e.g. metro stations
   outside any configured region): show 「暂时没有 region 地图，只记录 GPS 信息」
1. Support multiple location marks; user can clear all; when there are no records,
   default to showing the current position
1. (Added 2026-08-13 per user) **Not limited to the current position** — also allow
   "specifying a position": map click pick / center crosshair pick / manual
   coordinate entry (WGS-84 or GCJ-02)

## Tasks

### Page & Entry

- [x] Create `docs/notes/tools/gps-tracker.md` (frontmatter: `icon: material/map-marker`,
  `hide: [tags]`, same as existing tools)
- [x] Add a row to the tools table in `docs/notes/tools/index.md`
  (e.g. `:material-map-marker: GPS 位置记录` → 手机临时记录 GPS 位置，多标记 + 清空 + 地图展示)
- [x] Page structure: title + map container + action bar (获取位置 / 记录 / 清空) +
  current-position status line + record list + usage notes
- [x] Usage notes include the coordinate hint: 「从高德/百度 App 复制的是 GCJ-02/BD-09
  加密坐标，手动输入时请选择对应坐标系，否则地图上会偏移几百米」(browser
  geolocation is unaffected — native WGS-84)

### Geolocation & Recording (Req 1 / 2)

- [x] `navigator.geolocation.getCurrentPosition` with `enableHighAccuracy: true`;
  requires HTTPS (GitHub Pages ✅ / localhost dev ✅)
- [x] Per-scenario error handling with Chinese messages: permission denied,
  timeout, no GPS signal / fix failure
- [x] Coordinate system: the browser natively returns **WGS-84**, matching moment's
  default `crs: wgs84` (no conversion; display with 5–6 decimals)
- [x] **No conversion for geolocation, only show accuracy**: phone positioning
  "inaccuracy" is a GPS signal precision issue (random 10–50m+ error indoors /
  urban canyons) — conversion neither applies nor helps; the geolocation path
  stays WGS-84 end-to-end, naturally aligned with the basemap. Show `accuracy`
  (meters) so the user can judge reliability. Fully decoupled from coordinate
  conversion (only needed for manual entry, Req 5)
- [x] 「记录当前位置」: save `{ name?, lng, lat, ts, accuracy?, region }` to
  localStorage, refresh the list immediately
- [x] 「指定位置」capability lives in the 「指定位置（需求 5）」 section below

### Region Probing & Out-of-Region Handling (Req 3)

- [x] JS region bbox probe ported from `plugins/mkdocs_moment/plugin.py`
  `_probe_region`: iterate `regions` `bbox [minLng,minLat,maxLng,maxLat]`,
  return the region name on hit, `null` on miss
- [x] ⚠️ **Difference from the moment plugin**: moment falls back to
  `default_region` on miss; this tool returns explicit 「无 region」 to trigger
  out-of-region handling
- [x] Out-of-region points: still saved (coords + time), but the list shows a
  「⚠️ 暂无 region 地图（仅记录 GPS）」 badge; not rendered on the map (or only
  within its own region); provide an external map link (e.g. OSM
  `https://www.openstreetmap.org/?mlat={lat}&mlon={lng}`) for quick inspection

### Specifying a Position (Req 5)

> The vine widget **natively supports** the following APIs (confirmed 2026-08-13 via
> shallow clone, `packages/ui/src/widget.tsx`): `onClick` (maplibre click event with
> `e.lngLat`), `showCenterHud` (center crosshair), `onMove`/`onIdle` (camera
> callbacks), `flyTo`, `popupText` (plain text, auto-escaped). No need to hack into
> the maplibre instance.

- [x] **Map click pick** (primary): widget `onClick` callback → `e.lngLat.lng/lat`,
  drop a temporary marker + fill the form (name/coords), record on confirm;
  clicking again moves the temporary marker
- [x] **Center crosshair pick** (optional, more precise on mobile):
  `showCenterHud: true`, read current center via `onIdle`, 「以中心点记录」 button
  drops the point (reference moment map `flyTo` interactions)
- [x] **Manual coordinate entry** (fallback, most reliable): lng/lat form + crs
  selector (`wgs84` default / `gcj02`); JS port of `shared/gcj02.py`
  `gcj02_to_wgs84` (verified `121.48,31.16 → 121.475504,31.161994`);
  **GCJ-02 only, no Baidu BD-09** (consistent with the moment plugin)
- [x] **Paste parsing**: auto-detect pasted text from external apps — Google Maps
  format `lat, lng` (WGS-84), Amap format (GCJ-02); show a hint on parse failure
- [x] Specified positions go through the same region probe: out-of-region shows the
  「暂无 region 地图（仅记录 GPS）」 badge + OSM link; if the point is outside the
  current region's viewport, hint or guide the user to switch regions

### Map (reuse moment's vine widget)

- [x] Lazy-load the widget: `import(widget_js)` → `createMapWidget` (reference
  `plugins/mkdocs_moment/assets/js/moment-dialog.js` lazy import + destroy
  pattern) so the page doesn't pull the whole bundle on load
- [x] Init: `basemapUrl = pmtiles_prefix + region + '.pmtiles'`, `glyphsUrl`,
  `attribution`, center/zoom from region config
- [x] Marker rendering: records → widget MarkerSpec
  `{ lng, lat, emoji: '📍', label, popupText }`; **use `popupText` (plain text,
  auto-escaped by the widget) instead of `popupContent` + hand-rolled `esc()`**
  (moment pages need HTML for images/links; tool data is simpler and popupText
  is safer)
- [x] Distinguish the temporary pick marker from recorded markers (e.g. different
  color/emoji); `flyTo` to focus after picking
- [x] Multi-region behavior: records grouped by region; the map shows markers within
  the current region; switch regions or show only the current region's markers
- [x] Config source: inline page constants mirroring `mkdocs.yml extra.moment.map`
  (`widget_js` / `widget_css` / `pmtiles_prefix` / `glyphs_url` / `regions` /
  `default_region`), with a comment 「keep in sync with mkdocs.yml — update on
  vine release hash changes」
  \- Alternative (deferred, noted): if a second map-based tool appears, extract
  a macros module to inject this config and remove duplication

### Multiple Marks / Clear / Default Position (Req 4)

- [x] Multiple-mark list (newest first): time, name, coords, region badge or
  out-of-region badge, per-item 「复制坐标」 (`lng,lat` text)
- [x] 「清空全部」 button: clear localStorage and refresh map/list (mis-tap
  protection: confirm or undo)
- [x] localStorage schema: key `gps_tracker_v1` (following the `med_tracker_v1`
  snake_case + version-suffix convention), value
  `[{ name?, lng, lat, ts, accuracy?, region? }]`
- [x] **No records → default to current position**: map initially focuses the
  current fix (auto-locate once when authorized; otherwise show a
  「点击获取位置」 prompt)

### Quality & Verification

- [x] `poe server` local verification: headless Chrome `--dump-dom` to check page
  elements/buttons exist (AGENTS.md: **prefer DOM verification over
  screenshots**)
- [x] Geolocation chain: headless needs a CDP-injected mock; the 「指定位置」 chain
  uses the manual-entry path to cover 「input → record → list → map marker」;
  map click pick is verified by CDP `Input.dispatchMouseEvent` to exercise
  `onClick` → drop → record
- [x] Pure functions kept testable: region probe, gcj02 conversion (if done) as
  dependency-free pure functions; if inlined, at least manual cases covering
  inside/outside the Shanghai & Tokyo bboxes
- [x] `poe fmt` / `poe lint-py` / `poe test` — no regressions (skip lint when there
  are no Python changes)
- [x] Mobile UX: large tap targets, map height adapted for small screens (reference
  `moment_map.html` 480px canvas + small-screen media queries); verify the
  iPhone Safari / Chrome permission flow
- [x] **Final deliverable: write `internal/gps-tracker-design.md`** — a design doc
  in the style of `internal/moment-design.md` / `internal/med-tracker-design.md`
  (architecture, page structure, data schema, widget usage, config, design
  decisions), documenting the tool's design outside the plan

### Post-review additions (2026-08-13, user feedback) ✅

- [x] Remarks: the 名称 box is now a shared remark field on all record paths
  (record current / record center / add pick), cleared after recording
- [x] Hidden map attribution (refer to moment `hide_attribution` CSS approach)
- [x] Paste input placeholder carries an example (`如 31.2304, 121.4737`)
- [x] Current-position marker distinct from recorded pins (🟢 green dot via
  `color: "#22c55e"` vs 📍 pins vs 🎯 temp pick); legend added to the page
- [x] Per-item ✏️ rename (inline edit: Enter/blur saves, Esc cancels; syncs list +
  localStorage + map marker)
- [x] Per-item 🗑 delete (confirm; syncs list + localStorage + markers)
- [x] Per-item 🧭 focus-to (flyTo; auto region switch when cross-region;
  out-of-region → hint + OSM link)
- [x] Sidebar entry: `GPS Tracker` under Tools nav in `mkdocs.yml`
- [x] Root-cause fix: load `widget_css` (missing stylesheet collapsed the map
  layout and mis-rendered markers — the "drift" symptom)

## Notes

- **References**:
  - `internal/moment-design.md` → Geo / Map Features (coordinate system, region
    probing, widget config)
  - `plugins/mkdocs_moment/templates/moment_map.html` (widget usage, region
    switching, init params)
  - `plugins/mkdocs_moment/assets/js/moment-dialog.js` (lazy load + fresh host per
    open + destroy, avoiding duplicate maps / stacked attribution)
  - `shared/gcj02.py` (source for the JS port of gcj02 → WGS-84)
  - vine widget API (confirmed 2026-08-13 via shallow clone): `onClick` /
    `showCenterHud` / `onMove` / `onIdle` / `flyTo` / `popupText` (plain text,
    auto-escaped, XSS-safe) / `popupIndex`, see `packages/ui/src/widget.tsx` and
    `lib/map/specs.ts`
  - Existing tools inline-script style: `docs/notes/tools/ramen-timer.md` /
    `med-tracker.md` / `fitness.md`
- **Differences from the moment plugin**: region probe fallback differs (moment →
  `default_region`; this tool → explicit 「无 region」); tools pages are plain
  markdown + inline scripts, so widget config can't be injected by a hook like
  `moment_map.html` — the page carries inline constants kept in sync with
  `mkdocs.yml`
- **Data positioning**: 「临时记录」 = localStorage persistence + one-click clear +
  copy/export; records can later become moments (`poe create-moment --place --lng --lat --crs --region` already supports these fields)
- **External deps**: widget / pmtiles / glyphs come from the vine R2 bucket; CORS
  allow-list must include the site origin and `http://localhost:8000` (already
  configured for moments — no change needed)
- Iteration details that conflict with this plan follow the
  `internal/moment-map-draft.md` precedent (git-ignored draft → folded back into
  the plan / design doc)
- **Design doc**: the last implementation step writes
  `internal/gps-tracker-design.md` (listed as a task above; authored at
  implementation time, lives next to the other `*-design.md` files)

## Acceptance Criteria

- On a phone (or an authorized desktop browser) one tap gets and records the
  current position; the list shows the new record
- **A position can be specified via map click / center crosshair / manual entry
  and recorded**; out-of-region specified positions show the 「暂无 region 地图
  （仅记录 GPS）」 badge + OSM link
- Multiple marks can be recorded; after 「清空全部」 the list and map return to the
  initial state
- With no records, the map defaults to the current position
- Points inside the Shanghai/Tokyo regions show map markers; out-of-region points
  show 「暂无 region 地图（仅记录 GPS）」 + OSM link
- Records survive a page reload (localStorage); data never leaves the browser
- `internal/gps-tracker-design.md` exists, documenting the tool's design
