# GPS Location Recorder Tool — Design Document

> Pure-frontend tool 「📍 GPS 位置记录」 under **Notes → Tools**: temporarily record the
> current GPS position from a phone (typical use: metro stations / waypoints), with
> multiple marks, per-item rename / delete / copy, one-click clear, and map display.
> Positions can also be *specified* (map click / center crosshair / manual entry).
> Data stays in browser localStorage, never uploaded. The map reuses the moments
> vine widget (MapLibre + Protomaps pmtiles) — no API keys, fully static.

## Overview

A single tool page (`docs/notes/tools/gps-tracker.md`), pure Markdown + inline
CSS/JS like ramen-timer / med-tracker — zero build dependencies:

- **Record current position**: `navigator.geolocation` (WGS-84, no conversion,
  only shows ±accuracy)
- **Specify a position**: map click pick / center crosshair pick / manual
  coordinate entry (WGS-84 or GCJ-02 with auto conversion)
- **Region-aware**: probes the `extra.moment.map.regions` bboxes; out-of-region
  points get special handling
- **Multiple marks + clear**: localStorage persistence (`gps_tracker_v1`),
  per-item ✏️ rename / 🗑 delete / 📋 copy / 🧭 focus, one-click clear (confirmed)
- **Export**: copy `经度, 纬度` per record for later
  `poe create-moment --lng --lat`

## Requirements (source `internal/local-draft.md` + user follow-ups)

1. Temporarily record the current GPS position from a phone
1. Reuse the moments GPS approach (coordinate system / region probing / vine map widget)
1. Out-of-region locations (e.g. metro stations outside any configured region):
   special handling — 「暂时没有 region 地图，只记录 GPS 信息」
1. Multiple marks, user can clear all; no records → default to showing the
   current position
1. (Added) **Not limited to the current position** — specify a position via map
   click / center crosshair / manual entry (WGS-84 or GCJ-02); support remarks
   when recording
1. (Added, post-review) remark support on all record paths, per-item
   rename / delete / focus-to, current-position marker distinct from recorded
   pins, hidden attribution, sidebar entry

## Page Structure

```
Title + intro
Map container #gps-map-host (480px, 360px on mobile, center crosshair)
Region buttons #gps-regions (上海 / 东京, active highlighted)
Status line #gps-status (coords + ±accuracy + time / error messages)
Action bar:
  📍 获取当前位置   ➕ 记录当前位置   🎯 以地图中心记录   🗑 清空全部
Specify-position form (details open):
  名称（备注）   粘贴坐标（如 31.2304, 121.4737，自动识别）
  纬度 lat  经度 lng  坐标系 [WGS-84 | GCJ-02]   ✅ 记录此位置
  hint: 高德/百度复制的是 GCJ-02/BD-09，选对应坐标系否则偏移几百米
Record list (newest first): time / name / coords / region badge or out-of-region
  badge / buttons 🧭 ✏️ 📋 🗑 / OSM link (out-of-region)
Toast (fixed bottom center)
```

Marker legend (in the page): 🟢 green dot = current position; 📍 pin = recorded;
🎯 target = temporary map-click pick (cleared after recording).

## Coordinate Systems

| Scenario                                | CRS              | Conversion                                    |
| --------------------------------------- | ---------------- | --------------------------------------------- |
| Browser geolocation                     | WGS-84 (native)  | none, only show `accuracy` (±m)               |
| Map click / center crosshair            | WGS-84 (basemap) | none                                          |
| Manual entry / paste (Google Maps, OSM) | WGS-84 (default) | none                                          |
| Manual entry / paste (Amap)             | GCJ-02           | JS port of `shared/gcj02.py` `gcj02_to_wgs84` |

Design note: phone positioning "inaccuracy" is a GPS signal precision issue
(random error, not fixable by conversion); the geolocation path is WGS-84
end-to-end and matches the basemap, so no conversion there. Conversion only
serves manual entry of external CRS (Amap GCJ-02 offset ~300–600m if treated as
WGS-84). GCJ-02 only, no Baidu BD-09 (consistent with the moment plugin).

## Region Probing & Out-of-Region Handling

`probeRegion(lng, lat)`: iterate `regions` `bbox [minLng,minLat,maxLng,maxLat]`,
return the region name on hit, `null` on miss. **Difference from the moment
plugin**: moment's `_probe_region` falls back to `default_region` on miss; this
tool returns explicit 「无 region」 to trigger out-of-region handling.

Out-of-region points (e.g. recorded in Beijing):

- still saved (coords + time + remark)
- list shows a 「⚠️ 暂无区域地图」 badge + OSM link
  (`https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=16/{lat}/{lng}`)
- not rendered on the map (no basemap data outside the region tiles)

## Map (vine widget)

Loaded on page init via `import(widget_js)` → `createMapWidget(host, options)`
(the tool page is map-centric, so the widget loads immediately rather than
lazily-on-demand like the moment dialog; `import()` is async so it never blocks
rendering):

```js
widget = createMapWidget(mapHost, {
  basemapUrl: MAP.pmtiles_prefix + currentRegion + ".pmtiles",
  glyphsUrl: MAP.glyphs_url,
  attribution: "© recycle.bin · Protomaps",
  center: focus ? [focus.lng, focus.lat] : regionCfg.center,
  zoom: focus ? POI_ZOOM : regionCfg.zoom,
  markers: [],
  showCenterHud: true,   // crosshair for center-pick on mobile
  navControl: true,
  onClick: (e) => pickPoint(e.lngLat.lng, e.lngLat.lat),  // click to pick
  onIdle: (e) => { centerPick = e.target.getCenter(); },  // crosshair center
});
widget.setData({ markers });    // update markers
widget.setBasemap(url, opts);   // region switch
widget.flyTo({ center, zoom }); // focus (queued across basemap swaps)
```

Key points:

- **`popupText` (plain text, auto-escaped by the widget) instead of
  `popupContent` + hand-rolled `esc()`** — moment pages need HTML (images/links);
  tool data is simpler and popupText is XSS-safe
- **The widget stylesheet (`widget_css`) MUST be loaded** (the page injects a
  `<link>` in `initMap`; moment pages load it in `<head>` via the hook). Without
  it the map layout collapses (canvas height balloons) and markers render
  off-position — this was the root cause of a "markers drift" symptom found in
  testing
- Markers: 🟢 `color: "#22c55e"` dot for the current position, 📍 pin for
  recorded points, 🎯 target for the temporary click-pick — visually distinct
- Attribution hidden via CSS (`.gps-map-host .maplibregl-ctrl-attrib { display: none }`) — same approach as moment pages
  (`extra.moment.map.hide_attribution`)
- Initial focus: latest record (POI_ZOOM=14); with no records, auto-locate once
  when the browser already holds geolocation permission
  (`permissions.query` → `granted`), otherwise stay at `default_region` center

## Data Schema (localStorage)

Key `gps_tracker_v1` (following the `med_tracker_v1` snake_case + version
convention):

```json
[{ "name": "龙华中路站", "lng": 121.4692, "lat": 31.2323, "ts": 1786605600000, "accuracy": 5, "region": "shanghai" }]
```

- `name`: remark (optional, ≤100 chars)
- `lng/lat`: WGS-84
- `ts`: epoch ms
- `accuracy`: fix accuracy in meters (geolocation records only)
- `region`: probe result; missing = out-of-region

Records are sanitized on load (coordinate ranges, parseable `ts`); corrupt
entries are dropped.

## Interactions

| Operation         | Behavior                                                                                                                    |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 📍 获取当前位置   | `getCurrentPosition` (`enableHighAccuracy`, 15s timeout); status shows coords + ±accuracy + time                            |
| ➕ 记录当前位置   | saves the latest fix; the 名称 remark box is included, then cleared; auto-locates first if never located                    |
| 🎯 以地图中心记录 | saves the map center read on `onIdle` (align the target under the crosshair); remark included                               |
| Map click pick    | `onClick` → fills the form + temporary 🎯 marker; out-of-region hint 「仅记录 GPS」                                         |
| Manual entry      | lat/lng + CRS selector; GCJ-02 auto-converted to WGS-84; Enter submits                                                      |
| Paste detect      | extracts two numbers, fills as `纬度, 经度` (Google Maps convention), prompts to verify                                     |
| 🧭 定位           | `flyTo` the record; auto-switches region basemap first when the point is in another region; out-of-region → hint + OSM link |
| ✏️ 改名           | inline edit: name becomes an input; Enter / blur saves, Esc cancels; syncs list + localStorage + map marker label/popup     |
| 🗑 删除            | single-record delete with `confirm`; syncs list + localStorage + map markers                                                |
| 📋 复制           | `navigator.clipboard` copies `经度, 纬度`, degrades to a hint on failure                                                    |
| 🗑 清空全部        | `confirm` then clears localStorage + refreshes list/map                                                                     |

Geolocation errors (permission denied / timeout / no signal) show distinct
Chinese messages; `localStorage` unavailable degrades to session-only with a
warning (med-tracker pattern). List buttons use one delegated click handler.

## Config (mirror of mkdocs.yml)

Inline page constants `MAP` mirror `extra.moment.map` (widget_js / widget_css /
pmtiles_prefix / glyphs_url / attribution / default_region / regions), with a
「KEEP IN SYNC: update both on vine release hash changes」 comment. Tools pages
are plain markdown — config can't be hook-injected like `moment_map.html`, so
inline + comment convention; if a second map-based tool appears, extract a
macros module to inject the config and remove duplication.

## Design Decisions

| Decision                                        | Rationale                                                                    |
| ----------------------------------------------- | ---------------------------------------------------------------------------- |
| Pure-frontend inline page (no build)            | consistent with ramen-timer / med-tracker; zero deps, works offline          |
| Reuse vine widget instead of Leaflet            | consistent with moments: pmtiles basemap, no API keys, static deploy         |
| No conversion for geolocation, only accuracy    | browser WGS-84 matches the basemap; "inaccuracy" is GPS precision            |
| GCJ-02 only for manual entry                    | Amap/Baidu encrypted coords need conversion; BD-09 skipped like moments      |
| Out-of-region points not on the map             | no basemap tiles outside regions; badge + OSM link instead                   |
| `popupText` over `popupContent`                 | widget auto-escapes, avoids hand-rolled `esc()` XSS risk                     |
| Region probe returns null, not default fallback | explicit 「无 region」 semantics → out-of-region handling                    |
| localStorage key `gps_tracker_v1`               | med-tracker naming convention, version suffix for migration                  |
| Widget loads on page init (not click-lazy)      | the map is the tool's primary surface; async `import()` doesn't block render |
| Distinct markers (🟢/📍/🎯)                     | current position vs recorded vs temp pick must be visually separable         |
| Sidebar entry `GPS Tracker`                     | registered in `mkdocs.yml` nav → Tools                                       |

## Verification (2026-08-13, headless Chrome + CDP)

Environment: `--headless=new --use-angle=swiftshader --enable-unsafe-swiftshader`
(headless needs software WebGL or maplibre fails to create its context) + CDP
`Emulation.setGeolocationOverride` (Shanghai mock) + `Browser.grantPermissions`.

| Case                                                                                          | Result |
| --------------------------------------------------------------------------------------------- | ------ |
| Get current position (mock 121.4737,31.2304) → status shows coords + ±5 m                     | ✅     |
| Record current position with remark → list + localStorage + map marker                        | ✅     |
| Manual out-of-region point (济南) → list + 「暂无区域地图」 badge + OSM link                  | ✅     |
| GCJ-02 → WGS-84 conversion (121.4737,31.2304 → 121.4692,31.2323, ~400m)                       | ✅     |
| Map click pick (CDP `Input.dispatchMouseEvent`, `mouseMoved` first) → form filled             | ✅     |
| Click-picked coords vs recorded coords consistency (no drift)                                 | ✅     |
| Clear all → localStorage emptied                                                              | ✅     |
| 🎯 以地图中心记录: disabled → enabled on idle → records the center                            | ✅     |
| ✏️ rename: input appears → Enter saves → Esc cancels                                          | ✅     |
| 🗑 single delete → list + localStorage + markers sync                                          | ✅     |
| 🧭 focus: same-region flyTo; cross-region auto basemap switch (上海→东京); out-of-region hint | ✅     |
| Attribution hidden (`display: none`)                                                          | ✅     |
| No records → auto-locate shows the green current-position dot                                 | ✅     |

Headless notes: map clicks need `mouseMoved` before press/release; clicks during
a `flyTo` animation are treated as drags by maplibre (wait for idle);
`--dump-dom` hangs on this site's external resources — use CDP
`Page.navigate` + `Runtime.evaluate` polling instead.

## Files

- `docs/notes/tools/gps-tracker.md` — the tool page (new)
- `docs/notes/tools/index.md` — tools table row (modified)
- `mkdocs.yml` — sidebar entry `GPS Tracker` under Tools nav (modified)
- This design doc (`internal/gps-tracker-design.md`)
- Implementation plan: `internal/plans/arch/gps-tracker-tool.md` (archived, completed)
