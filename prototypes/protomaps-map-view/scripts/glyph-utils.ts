/** Upstream fonts per source: style-font-name -> upstream-font-name. */
export const GLYPH_SOURCES = {
  protomaps: {
    upstream: "https://protomaps.github.io/basemaps-assets/fonts",
    fonts: {
      "Noto Sans Regular": "Noto Sans Regular",
      "Noto Sans Medium": "Noto Sans Medium",
      "Noto Sans Italic": "Noto Sans Italic",
    },
  },
  maplibre: {
    upstream: "https://demotiles.maplibre.org/font",
    fonts: {
      // demotiles has no "Noto Sans Medium" — serve Bold in its place.
      "Noto Sans Regular": "Noto Sans Regular",
      "Noto Sans Medium": "Noto Sans Bold",
      "Noto Sans Italic": "Noto Sans Italic",
    },
  },
} as const;

export type GlyphSourceName = keyof typeof GLYPH_SOURCES;

/** Resolve `--source=<name>` (or `--source <name>`) from CLI args; default `protomaps`. */
export function parseSource(argv: string[]): GlyphSourceName {
  const eq = argv.find((a) => a.startsWith("--source="));
  if (eq) {
    const v = eq.slice("--source=".length) as GlyphSourceName;
    if (v in GLYPH_SOURCES) return v;
  }
  const i = argv.indexOf("--source");
  if (i >= 0 && argv[i + 1] && argv[i + 1] in GLYPH_SOURCES) return argv[i + 1] as GlyphSourceName;
  return "protomaps";
}

/** Slippy-map tile coordinates (x, y) for a lng/lat at zoom z. */
export function tileXY(lng: number, lat: number, z: number): [number, number] {
  const n = 2 ** z;
  const x = Math.floor(((lng + 180) / 360) * n);
  const y = Math.floor(
    ((1 -
      Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) /
      2) *
      n,
  );
  return [x, y];
}
