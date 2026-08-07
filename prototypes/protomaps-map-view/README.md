# protomaps-map-view

React + Vite + TypeScript prototype demonstrating a **generic map view
component** (`MapView`) on a local [Protomaps](https://protomaps.com) basemap —
[MapLibre GL JS](https://maplibre.org/maplibre-gl-js/) +
[pmtiles](https://github.com/protomaps/pmtiles) protocol +
[@protomaps/basemaps](https://www.npmjs.com/package/@protomaps/basemaps)
complete basemap style. Package manager: **pnpm**.

Status: `working` (validated locally on dev + preview; user-tested — demos,
basemap switching, embed widget)

## Features

- **Local-only basemap, configured by env vars** — no CDN, no remote tiles, no
  copy/sync scripts. Point `VITE_PMTILES_DIR` / `VITE_PMTILES_FILE` at your own
  `.cache/pmtiles/` (one shared gitignored `.cache/` dir, see
  [Local cache](#local-cache-cache)).
- **MapLibre pinned to v5 (`maplibre-gl@^5.24.0`)** — MapLibre v6 is
  incompatible with the `pmtiles` protocol and leaves the basemap blank; see
  [Known issue](#known-issue-maplibre-v6--pmtiles-protocol) and
  [Upgrading MapLibre](#upgrading-maplibre--pmtiles-guidance).
- **Generic `MapView` component** (`src/components/map-view.tsx`):
  - initial center / zoom, navigation control
  - live center HUD (lng / lat / zoom) — `showCenterHud`
  - external point markers with text labels and popups — `markers`
  - track (polyline) annotations — `tracks`
  - `onMapReady` callback for custom layers
  - event props — `onClick` / `onMove` / `onZoom` / `onIdle`
  - **runtime basemap switching** — changing `basemap.url` (or flavor/glyphs)
    recreates the map with a fresh controller; changing `center`/`zoom` moves
    the camera without a remount (see the `region` demo)
  - pmtiles protocol registered once (module-level guard); `map.remove()` on
    unmount; event listeners cleaned up
- **Map infrastructure is split out** (per the refactor plan, P0+P1):
  - `MapController` (`src/lib/map/map-controller.ts`) — framework-agnostic owner
    of the MapLibre instance (lifecycle, camera helpers `flyTo`/`fitBounds`,
    events, layer/source management)
  - `basemap/protomaps.ts` — builds the Protomaps style
  - `layers/*` — GeoJSON-based layers: `syncMarkerLayer` (points → maplibre
    Markers), `syncTrackLayer` (lines/polygons → line layers)
  - `hooks/use-map-instance.ts` — binds a controller to a React lifecycle
  - `MapView` is a thin wrapper: converts `MarkerSpec`/`TrackSpec` to GeoJSON
    features, syncs layers and event handlers reactively
- **Five demos** (tab switcher, no router):
  - `basic` — plain basemap + nav control + center HUD, started on a **small
    region** (Xuhui riverside, zoom 13) so the first load fetches only a few
    tiles instead of the whole Shanghai viewport (no `maxBounds` — it would
    lock the zoom level, see `src/config.ts`)
  - `markers` — few markers via maplibre `Marker` (label/popup, **emoji
    instead of dots** via `MarkerSpec.emoji`) + ~200 random points rendered as
    a GeoJSON **circle layer** (many-points principle)
  - `track` — **two** line layers (徐汇滨江 + 世纪公园), emoji start markers,
    auto-fit to both routes
  - `style` — flavor switching (light / dark / grayscale / black) on the same
    small region, by remounting the map with a React `key`
  - `region` — switch basemaps at runtime: two Shanghai presets (Xuhui
    riverside ↔ Century Park) plus a **commented Tokyo preset** — changing
    `basemap.url` recreates the map, changing `center`/`zoom` moves the camera
    (MapView handles both; add your tokyo.pmtiles and uncomment to switch files)

## How tiles are served (no extra server)

1. Copy your basemap into the tiles directory (default `.cache/pmtiles/`,
   gitignored):
   ```bash
   mkdir -p .cache/pmtiles && cp /path/to/shanghai.pmtiles .cache/pmtiles/
   ```
2. Copy the env template (both variables are optional — these are the defaults):
   ```bash
   cp .env.example .env.local
   # .env.local
   # VITE_PMTILES_DIR=.cache/pmtiles
   # VITE_PMTILES_FILE=shanghai.pmtiles
   ```
3. `vite.config.ts` contains a small inline plugin (`local-tiles`) that mounts
   the tiles directory on **both the dev and the preview server**, at the same
   URL path as the directory name. `src/config.ts` builds the source URL from
   the same env values, e.g. `pmtiles:///pmtiles/shanghai.pmtiles`. MapLibre's
   pmtiles protocol strips the scheme and issues **HTTP Range requests**
   (byte-range tile reads) against the Vite origin — same origin, no CORS, no
   separate http-server, works identically in dev and preview.
4. Move the tiles elsewhere? Just change `VITE_PMTILES_DIR` (a relative path
   outside the project root works too) — the plugin and the URL derive from the
   same value.

## Local cache (.cache/)

A single gitignored directory holds everything the map needs at runtime, so a
warmed checkout runs **fully offline** (tiles + glyphs; no sprite at all):

```
.cache/
├── pmtiles/   # your basemap files, copied by hand
│   └── shanghai.pmtiles
└── glyphs/    # label-font PBFs, warmed by scripts/warm-glyphs.ts
    └── Noto Sans Regular/0-255.pbf …
```

- **Why gitignored** — the basemap is ~54 MB and the glyph cache ~4 MB; both
  are machine-local artifacts, never committed. A fresh clone must copy its own
  basemap into `.cache/pmtiles/` and run `pnpm warm:glyphs` once.
- **Env knobs** — `VITE_PMTILES_DIR` (default `.cache/pmtiles`) and
  `VITE_GLYPHS_DIR` (default `.cache/glyphs`) relocate the cache; the vite
  plugins and `src/config.ts` all derive from the same values, so URLs stay in
  sync (`pmtiles:///pmtiles/shanghai.pmtiles`, `/glyphs/…`).
- **Warm-up** — `pnpm warm:glyphs [-- --source=protomaps|maplibre]` scans the
  local basemap tiles for every character used by labels (Shanghai center,
  z10–14), maps them to 256-codepoint glyph ranges, and downloads only those
  ranges for the fonts the style uses (~396 files). Needs network on first run
  (use `NODE_USE_ENV_PROXY=1 HTTPS_PROXY=…` if a proxy is required); afterwards
  the glyph-proxy plugin serves everything from cache. A `.source` marker
  records which upstream filled the cache — switching sources wipes it first.

  | source                          | upstream                            | cache size | CJK labels                     |
  | ------------------------------- | ----------------------------------- | ---------- | ------------------------------ |
  | `protomaps` (default, smallest) | protomaps.github.io/basemaps-assets | ~4 MB      | ✗ (fonts have no CJK glyphs)   |
  | `maplibre`                      | demotiles.maplibre.org              | ~72 MB     | ✓ (Medium is served from Bold) |

  `VITE_GLYPHS_SRC` (default `protomaps`) tells the vite glyph-proxy plugin
  which upstream to use for un-cached ranges and must match the source the
  cache was warmed with.

- **First-load speed** — the demo viewports start on a small region
  (`smallRegion`, see `src/config.ts`), so the initial tile fetch is a handful
  of range requests instead of the whole Shanghai viewport (deliberately **no
  `maxBounds`** — it locks the zoom level, see Notes).

## Embeddable widget (plain HTML)

`src/widget.tsx` exposes an imperative `createMapWidget(el, options)` entry,
built as a self-contained ESM bundle:

```bash
pnpm build:widget   # → dist/widget/map-widget.js (+ map-widget.css)
```

Use it from any plain HTML page — no React, no build step:

```html
<link rel="stylesheet" href="dist/widget/map-widget.css" />
<script type="module">
  import { createMapWidget } from "./dist/widget/map-widget.js";
  const w = createMapWidget(document.getElementById("map"), {
    basemapUrl: "pmtiles:///tiles/shanghai.pmtiles",  // host serves the basemap
    glyphsUrl: "/glyphs/{fontstack}/{range}.pbf",     // host serves the fonts
    center: [121.47, 31.23], zoom: 11,
    markers: [{ lng, lat, label, emoji, popupContent }],
    tracks: [{ name, color, coordinates: [[lng, lat], ...] }],
  });
  w.setData({ markers: [...] });   // update coordinates at runtime
  w.setBasemap("pmtiles:///tiles/tokyo.pmtiles", { center: [139.7, 35.66], zoom: 12 }); // switch basemap
  w.flyTo({ center, zoom });       // camera (queued until ready)
  w.destroy();
</script>
```

A live example is at `examples/embed.html` (served by `pnpm dev` →
`http://127.0.0.1:5173/examples/embed.html`).

**Host responsibilities** — the widget takes basemap/glyphs as URL parameters;
the host page must:

- serve the `.pmtiles` basemap with **HTTP Range requests** (any static
  server / R2 / S3 works; presigned URLs do not — they break Range signing)
- serve the glyph PBFs (or point `glyphsUrl` at an upstream font server)
- Note: the widget CSS includes Tailwind preflight, which resets host page
  defaults — acceptable for an embed, worth knowing
- **Sanitize `popupContent`**: it is injected via `Popup.setHTML` — never pass
  untrusted HTML (XSS vector). Escape or whitelist anything user-generated.

Bundle size: ~2.1 MB (react + maplibre bundled in), ~518 KB gzipped.

## Distribution (no npm)

The widget is just a few static files — no npm registry needed to hand it to a
customer.

### 1. Hand over the built files

```bash
pnpm build:widget   # → dist/widget/map-widget.js + map-widget.css
```

Copy those two files to the customer's server and use them from any plain HTML
page (see [Embeddable widget](#embeddable-widget-plain-html)). If the
customer's server also serves the basemap + glyphs, nothing else is needed.

### 2. Ship js/css + pmtiles + glyphs together to S3

Upload everything — the bundle, the basemap and the glyph cache — to a
public-read S3 bucket (or R2 / OSS), then the customer only writes URLs:

```bash
# 1. build the widget
pnpm build:widget
# 2. upload bundle + tiles + glyphs (adjust bucket / prefix / region)
aws s3 sync dist/widget    s3://my-maps/map-widget/     --acl public-read
aws s3 sync .cache/pmtiles s3://my-maps/data/pmtiles/   --acl public-read
aws s3 sync .cache/glyphs  s3://my-maps/data/glyphs/    --acl public-read
```

Customer page:

```html
<script type="module">
  import { createMapWidget } from "https://s3.example.com/my-maps/map-widget/map-widget.js";
  const w = createMapWidget(el, {
    basemapUrl: "pmtiles://https://s3.example.com/my-maps/data/pmtiles/shanghai.pmtiles",
    glyphsUrl: "https://s3.example.com/my-maps/data/glyphs/{fontstack}/{range}.pbf",
    center: [121.47, 31.23],
    zoom: 11,
    markers: [{ lng, lat, label, emoji, popupContent }],
    tracks: [{ name, color, coordinates: [[lng, lat], ...] }],
  });
</script>
```

Requirements:

- **Range requests** — S3 / R2 / OSS support HTTP Range natively (the pmtiles
  reader fetches byte ranges). **Presigned URLs do not work** for the basemap:
  every Range request needs its own signature.
- **CORS** — the widget JS is a cross-origin module and the map fetches
  tiles/glyphs cross-origin, so the bucket must send CORS headers
  (`Access-Control-Allow-Origin: *`) for both the JS and the data files
  (S3: bucket CORS config; R2: CORS policy).
- **Version the bundle** for upgrades, e.g. `map-widget@1.2.0.js`.

## Usage

```bash
pnpm install
pnpm dev        # http://127.0.0.1:5173 — dev server (HMR); serves the pmtiles itself
pnpm typecheck
pnpm test       # vitest unit tests (pure helpers + layer logic + MapView wiring)
pnpm build      # tsc --noEmit + vite build
pnpm preview    # http://127.0.0.1:4173 — production bundle; serves the pmtiles too
```

> **Both `pnpm dev` and `pnpm preview` carry the pmtiles**: the inline
> `local-tiles` plugin in `vite.config.ts` is registered on the dev **and** the
> preview server, so whichever command you run, the map's tile requests hit the
> very same server that serves the page — no separate tile server, no extra
> port, no CORS.

### Testing the embed HTML

The widget demo page (`examples/embed.html`) is served by the dev server — it
imports the **built** bundle, so build it first, then open the page:

```bash
pnpm build:widget        # 1. produce dist/widget/map-widget.js + .css
pnpm dev                 # 2. dev server serves the page + tiles + glyphs
# 3. open http://127.0.0.1:5173/examples/embed.html
```

The page loads the real widget (markers + two tracks, HUD) and the three
buttons exercise the API: ☕ `setData` swaps markers, 📍 `flyTo` moves the
camera to Century Park, 🔄 `setBasemap` re-targets the view.

> Rebuild the widget after changing `src/` — `examples/embed.html` reads
> `dist/widget/map-widget.js`, so an outdated bundle shows old behavior.

Also verify the **built page** (static-server scenario) with:

```bash
pnpm build && pnpm preview
# then open http://127.0.0.1:4173/examples/embed.html
```

Note: `pnpm preview` serves the same `dist/widget/` files and the tiles and
glyphs via the same plugins, so the embed works there too.

`dev` and `preview` are two **alternative** modes — run one at a time, never
both: `dev` serves the source with HMR for everyday work, `preview` serves the
built `dist/` bundle (run `pnpm build` first) to sanity-check the production
artifact.

## Project Layout

```
protomaps-map-view/
├── .env.example        # VITE_PMTILES_DIR/FILE + VITE_GLYPHS_DIR/SRC template
├── .env.local          # your local config (gitignored)
├── .cache/            # local cache, gitignored (see “Local cache” below)
│   ├── pmtiles/        #   your basemap files, copied by hand
│   └── glyphs/         #   label-font PBFs, warmed by scripts/warm-glyphs.ts
├── .gitignore
├── package.json        # pnpm-managed
├── pnpm-workspace.yaml
├── tsconfig.json
├── vite.config.ts      # + inline local-tiles / glyph-proxy plugins (dev & preview)
├── vite.lib.config.ts  # widget library build (pnpm build:widget)
├── vitest.config.ts   # vitest unit tests (pnpm test)
├── index.html
├── compat-check.html   # bare maplibre+pmtiles smoke page (see Upgrading MapLibre)
├── examples/
│   └── embed.html      # plain-HTML embed demo of the widget
├── scripts/
│   └── warm-glyphs.ts  # pre-download label-font PBFs into .cache/glyphs/ (run once, needs network)
└── src/
    ├── main.tsx
    ├── app.tsx         # demo tab switcher (unmount/remount per demo)
    ├── config.ts       # env → pmtiles URL + demo defaults
    ├── styles.css
    ├── lib/
    │   ├── pmtiles.ts      # idempotent pmtiles:// protocol registration
    │   ├── sample-data.ts  # embedded demo markers / track / batch points
    │   └── map/            # map infrastructure (split per refactor plan)
    │       ├── index.ts        # public exports
    │       ├── map-controller.ts   # framework-agnostic MapController
    │       ├── specs.ts            # MarkerSpec / TrackSpec (public API types)
    │       ├── basemap/protomaps.ts # createProtomapsStyle()
    │       ├── layers/marker-layer.ts # GeoJSON point → maplibre Markers
    │       ├── layers/track-layer.ts  # GeoJSON line → line layers
    │       └── hooks/use-map-instance.ts
    ├── components/
    │   └── map-view.tsx    # thin React wrapper (controller + layers + events)
    ├── demos/
    │   ├── basic-demo.tsx
    │   ├── markers-demo.tsx
    │   ├── track-demo.tsx
    │   ├── style-demo.tsx
    │   └── region-demo.tsx
    └── widget.tsx      # createMapWidget() embeddable entry (lib build)
```

File naming is kebab-case (shadcn style); exported component names stay
PascalCase (`MapView`, `BasicDemo`, …).

## Known issue: MapLibre v6 × pmtiles protocol

**Symptom** — the app loads (tabs, controls, HUD, attribution all render) but
the basemap stays blank gray. On the dev server log you only ever see the
initial header read (`GET /pmtiles/shanghai.pmtiles` with
`Range: bytes=0-16383`); no tile byte-range requests follow, and the map's
`load` event never fires.

**Root cause** — `maplibre-gl@6.x` is incompatible with the `pmtiles@4.4.1`
protocol handler. MapLibre v6 successfully fetches the TileJSON through the
custom protocol (a `type: "json"` call), but then never issues any tile
requests (`type: "tile"`) — the pmtiles protocol's compatibility wrapper no
longer matches v6's request flow. Reproduced with a bare maplibre+pmtiles page
(no React involved): v5 requests tiles, v6 is stuck.

**Current state** — this prototype pins `maplibre-gl@^5.24.0` and renders
correctly.

## Upgrading MapLibre — pmtiles guidance

**Official state of play** (checked 2026-08): the `pmtiles` npm package is at
its latest release (4.4.1), and the official reference example
(`pmtiles.io/examples/maplibre.html`, source in `protomaps/PMTiles`
`js/examples/maplibre.html`) pins **`maplibre-gl@5.13.0` + `pmtiles@4.4.1`** —
Protomaps' own demo runs on MapLibre v5. Neither MapLibre v5 nor v6 bundles
built-in pmtiles support, so upgrading `pmtiles` (already latest) does not fix
MapLibre v6, and converting the `.pmtiles` file (ours is already spec v3, the
latest spec; `pmtiles convert` only handles mbtiles↔pmtiles / v2→v3) does not
touch the JS protocol layer that is incompatible.

When you want to move to a newer `maplibre-gl`:

1. **Check the `pmtiles` JS release notes first** — the official package
   tracks MapLibre compatibility. Only upgrade maplibre together with a
   pmtiles version that explicitly claims the new major is supported.
2. **Bump maplibre and pmtiles together**, then open
   `http://127.0.0.1:5173/compat-check.html` (bundled `compat-check.html` — a
   bare maplibre + pmtiles map, no React). The page banner turns
   **green “STACK OK”** when TileJSON + tile requests + `load` all succeed,
   or **red** with the error otherwise. It accepts `?url=pmtiles://…` to test
   a different tile file.
3. **Know the failure fingerprint**: the protocol is called with `type: "json"`
   but zero tile requests follow (maplibre v5 sends tile bytes as
   `type: "arrayBuffer"`) and no `load` event ⇒ protocol incompatibility, not
   a tile-path or CORS problem. On the server side, a lone
   `Range: bytes=0-16383` request with no follow-up tile ranges is the same
   signature.
4. If the newest pmtiles still misbehaves on the newest maplibre, stay on the
   pinned v5 — nothing else in this prototype depends on maplibre v6 features.
5. **Test in a real browser** (hardware WebGL). Headless Chrome needs
   `--enable-unsafe-swiftshader`: the old automatic software-WebGL fallback is
   deprecated and flaky — it can render a blank canvas even when the stack is
   perfectly fine.

## Notes

- **Local cache is never committed**: `.cache/` is gitignored; a fresh clone
  needs the user to copy their basemap in (see above) and run
  `pnpm warm:glyphs` once with network access.
- The tracks in `track-demo` are hand-written sample data (徐汇滨江 riverside
  loop + 世纪公园 park loop), not real GPS tracks — coordinates are plausible
  only.
- **Glyphs are local too**: label fonts are served from the same origin — the
  vite `glyph-proxy` plugin caches `/glyphs/{fontstack}/{range}.pbf` into a
  gitignored `.cache/glyphs/` dir on first request. The cache is pre-warmed by
  `scripts/warm-glyphs.ts` (scans the local tiles for the exact characters
  used, then downloads only those ranges — 396 files, ~4 MB here), so the map
  runs **fully offline**: tiles, sprites (none) and glyphs all come from
  localhost.
- **Font limitation**: the default `protomaps` glyph source (basemaps-assets
  fonts) contains **no CJK glyphs** — Chinese labels render blank with it.
  Re-warm with `pnpm warm:glyphs -- --source=maplibre`
  (demotiles.maplibre.org) for real CJK labels (~72 MB cache; "Noto Sans
  Medium" is served from Bold).
- **`maxBounds` locks the zoom level**: MapLibre constrains the zoom to the
  level where the bounds exactly fill the viewport and blocks zooming out
  below it. The `MapView.maxBounds` prop is available, but the demos avoid it
  (the small initial region is enough for a fast first load).
- UI styling uses **Tailwind CSS v4** (`@tailwindcss/vite` plugin,
  `@import "tailwindcss"` in `src/styles.css`) — no hand-written component
  CSS.
- **Not part of GitHub CI**: prototypes are never built or tested by the repo's
  GitHub Actions workflow. Verify locally with `pnpm typecheck` / `pnpm build`
  (see [AGENTS.md](../../AGENTS.md) → Prototype Convention).
