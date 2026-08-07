import type { MapFlavor } from "./components/map-view.tsx";

/**
 * Local basemap configuration.
 * - `VITE_PMTILES_DIR`  — tiles directory, relative to the project root
 *   (default `.cache/pmtiles`, gitignored — manually copy your *.pmtiles in).
 * - `VITE_PMTILES_FILE` — basemap file name inside that directory
 *   (default `shanghai.pmtiles`).
 *
 * The pmtiles URL must match the mount path used by the `local-tiles` Vite
 * plugin (vite.config.ts): both derive the URL segment from the same
 * directory name, so the file is served by the dev/preview server itself.
 */
const tilesDir: string = import.meta.env.VITE_PMTILES_DIR ?? ".cache/pmtiles";
const tilesFile: string = import.meta.env.VITE_PMTILES_FILE ?? "shanghai.pmtiles";

const urlSegment = tilesDir.split(/[\\/]/).filter(Boolean).pop() ?? tilesDir;

export const pmtilesUrl = `pmtiles:///${urlSegment}/${tilesFile}`;

export const defaultCenter: [number, number] = [121.47, 31.23];
export const defaultZoom = 11;
export const defaultFlavor: MapFlavor = "light";
export const defaultLang = "zh";

/**
 * A small initial region (Xuhui riverside, 徐汇滨江) so the first load only
 * fetches a handful of tiles instead of the whole Shanghai viewport.
 *
 * Note: deliberately NO maxBounds — MapLibre's maxBounds forces the zoom to
 * the level where the bounds exactly fill the viewport and locks zooming out
 * below it (markers/track demos zoom freely for this reason). The initial
 * center/zoom alone already limits the first tile fetch.
 */
export const smallRegion = {
  center: [121.458, 31.188] as [number, number],
  zoom: 13,
};
