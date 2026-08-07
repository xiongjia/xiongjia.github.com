/**
 * Warm the local glyph cache (.cache/glyphs/) for the demo viewports.
 *
 * Usage:  pnpm warm:glyphs [-- --source=protomaps|maplibre]
 * (default source: `protomaps` — the smallest cache, but its fonts contain no
 * CJK glyphs; `maplibre` adds real CJK via demotiles.maplibre.org but the
 * cache grows to ~55 MB, and "Noto Sans Medium" is served from Bold.)
 *
 * 1. Scans the local shanghai.pmtiles archive (tiles covering the Shanghai
 *    center) and collects every character used by label properties (name,
 *    name:*, ...), mapped to 256-codepoint glyph ranges.
 * 2. Downloads each needed range per font into the gitignored .cache/glyphs/
 *    dir, which the vite glyph-proxy plugin serves locally — the map then
 *    runs fully offline. A `.source` marker records which upstream filled the
 *    cache; switching sources wipes it first.
 *
 * Needs network on first run (use NODE_USE_ENV_PROXY=1 + HTTPS_PROXY if a
 * proxy is required).
 */
import { config as loadDotenv } from "dotenv";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { VectorTile } from "@mapbox/vector-tile";
import { PbfReader as Pbf } from "pbf";
import { FileSource, PMTiles } from "pmtiles";
import { GLYPH_SOURCES, parseSource, tileXY } from "./glyph-utils.ts";

// tsx does not load .env files — do it explicitly so the script honors the
// same VITE_* knobs as the app (vite loads .env.local automatically).
loadDotenv({ path: [".env.local", ".env"] });

const GLYPHS_DIR = process.env.VITE_GLYPHS_DIR ?? ".cache/glyphs";
// Mirrors src/config.ts / vite.config.ts: honor the env knobs so the script
// works even when the cache is relocated.
const TILES_DIR = process.env.VITE_PMTILES_DIR ?? ".cache/pmtiles";
const TILES_FILE = process.env.VITE_PMTILES_FILE ?? "shanghai.pmtiles";
const TILES_PATH = path.join(TILES_DIR, TILES_FILE);
const MARKER_FILE = path.join(GLYPHS_DIR, ".source");

const source = parseSource(process.argv);
const { upstream, fonts } = GLYPH_SOURCES[source];

// Wipe the cache when the requested source differs from the one that filled it.
let activeSource: string | null = null;
try {
  activeSource = (await readFile(MARKER_FILE, "utf8")).trim();
} catch {
  // no marker yet
}
if (activeSource && activeSource !== source) {
  await rm(GLYPHS_DIR, { recursive: true, force: true });
  console.log(`source switched ${activeSource} -> ${source}; wiped .cache/glyphs/`);
}

const MIN_LNG = 121.3;
const MAX_LNG = 121.7;
const MIN_LAT = 31.05;
const MAX_LAT = 31.4;
const Z_MIN = 10;
const Z_MAX = 14;

// 1. Enumerate needed codepoint ranges from the local tiles.
const chars = new Set<number>();
const buf = await readFile(TILES_PATH);
const archive = new PMTiles(new FileSource(new File([buf], TILES_FILE)));
for (let z = Z_MIN; z <= Z_MAX; z++) {
  const [x1, y1] = tileXY(MIN_LNG, MAX_LAT, z);
  const [x2, y2] = tileXY(MAX_LNG, MIN_LAT, z);
  for (let x = x1; x <= x2; x++) {
    for (let y = y1; y <= y2; y++) {
      const tile = await archive.getZxy(z, x, y);
      if (!tile) continue;
      const vt = new VectorTile(new Pbf(new Uint8Array(tile.data)));
      for (const layerName of Object.keys(vt.layers)) {
        const layer = vt.layers[layerName];
        for (let i = 0; i < layer.length; i++) {
          const props = layer.feature(i).properties ?? {};
          for (const k of Object.keys(props)) {
            if (k === "name" || k.startsWith("name:")) {
              for (const ch of String(props[k])) {
                const cp = ch.codePointAt(0);
                if (cp !== undefined && cp > 31) chars.add(cp);
              }
            }
          }
        }
      }
    }
  }
}
const ranges = new Set<string>();
for (const cp of chars) {
  const start = Math.floor(cp / 256) * 256;
  ranges.add(`${start}-${start + 255}`);
}
console.log(`source=${source} upstream=${upstream}`);
console.log(`need ${chars.size} chars -> ${ranges.size} ranges`);

// 2. Download each range per style-font into .cache/glyphs/<font>/<range>.pbf.
let ok = 0;
let skipped = 0;
for (const [targetFont, upstreamFont] of Object.entries(fonts)) {
  for (const range of ranges) {
    const file = path.join(GLYPHS_DIR, targetFont, `${range}.pbf`);
    try {
      await readFile(file);
      ok++; // already cached
      continue;
    } catch {
      // not cached — download
    }
    const r = await fetch(`${upstream}/${encodeURIComponent(upstreamFont)}/${range}.pbf`);
    if (!r.ok) {
      skipped++;
      continue;
    }
    const data = Buffer.from(await r.arrayBuffer());
    await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, data);
    ok++;
  }
}
await writeFile(MARKER_FILE, `${source}\n`);
console.log(`glyphs (${source}): ${ok} ok, ${skipped} skipped (404)`);
