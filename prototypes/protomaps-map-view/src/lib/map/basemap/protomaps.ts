import { layers, namedFlavor } from "@protomaps/basemaps";
import type { StyleSpecification } from "maplibre-gl";

export type MapFlavor = "light" | "dark" | "white" | "black" | "grayscale";

export interface ProtomapsBasemapOptions {
  /** pmtiles:// URL of the basemap file (see src/config.ts). */
  url: string;
  flavor?: MapFlavor;
  /** Label language, e.g. "zh". */
  lang?: string;
  /**
   * Glyphs URL template, served locally by the vite glyph-proxy plugin in
   * this repo (default). Embedders can point it at their own font server
   * (or an upstream like `https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf`).
   */
  glyphs?: string;
}

export const PROTOMAPS_ATTRIBUTION = "Learning demo · © OpenStreetMap contributors / Protomaps";

/**
 * Build the full MapLibre style for a Protomaps basemap.
 * - Glyphs are served locally (same origin) by the vite glyph-proxy plugin.
 * - No external `sprite` on purpose: sprite icons (POI glyphs etc.) are
 *   skipped, keeping every non-tile request local. Layer colors still follow
 *   the flavor via namedFlavor().
 */
export function createProtomapsStyle({
  url,
  flavor = "light",
  lang = "zh",
  glyphs = "/glyphs/{fontstack}/{range}.pbf",
}: ProtomapsBasemapOptions): StyleSpecification {
  return {
    version: 8,
    glyphs,
    sources: {
      protomaps: {
        type: "vector",
        url,
        attribution: PROTOMAPS_ATTRIBUTION,
      },
    },
    layers: layers("protomaps", namedFlavor(flavor), { lang }),
  };
}
