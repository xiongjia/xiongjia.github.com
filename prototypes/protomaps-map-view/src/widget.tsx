/**
 * Embeddable map widget — a plain-JS entry point that mounts the React
 * MapView into any element, with basemap / glyphs passed as parameters.
 *
 * Built via `pnpm build:widget` (vite lib mode) into `dist/widget/map-widget.js`
 * (+ `map-widget.css`), then usable from a plain HTML page:
 *
 *   <script type="module">
 *     import { createMapWidget } from "./dist/widget/map-widget.js";
 *     const w = createMapWidget(el, { basemapUrl, glyphsUrl, markers, tracks });
 *     w.setData({ markers: [...] }); // update coordinates at runtime
 *     w.destroy();
 *   </script>
 *
 * The host page is responsible for serving the basemap (.pmtiles, HTTP Range
 * required) and the glyph PBFs — both are plain URL parameters.
 */
import { createRoot } from "react-dom/client";
import { createElement } from "react";
import type { Map as MapLibreMap, MapEventType } from "maplibre-gl";
import { MapView } from "./components/map-view.tsx";
import type { MarkerSpec, TrackSpec } from "./components/map-view.tsx";
import "./styles.css";

export type { MarkerSpec, TrackSpec, MapFlavor } from "./components/map-view.tsx";

export interface MapWidgetOptions {
  /** pmtiles:// URL of the basemap — the host must serve the file (HTTP Range). */
  basemapUrl: string;
  /** Glyphs URL template, e.g. "/glyphs/{fontstack}/{range}.pbf" or an upstream URL. */
  glyphsUrl?: string;
  center?: [number, number];
  zoom?: number;
  maxBounds?: [[number, number], [number, number]];
  markers?: MarkerSpec[];
  tracks?: TrackSpec[];
  showCenterHud?: boolean;
  navControl?: boolean;
  onClick?: (e: MapEventType["click"]) => void;
  onMove?: (e: MapEventType["move"]) => void;
  onZoom?: (e: MapEventType["zoom"]) => void;
  onIdle?: (e: MapEventType["idle"]) => void;
}

export interface MapWidget {
  /** Replace markers/tracks at runtime. */
  setData(data: { markers?: MarkerSpec[]; tracks?: TrackSpec[] }): void;
  /**
   * Switch the basemap at runtime (e.g. shanghai.pmtiles → tokyo.pmtiles).
   * Changing the URL recreates the map; the new center/zoom are applied.
   */
  setBasemap(basemapUrl: string, opts?: { center?: [number, number]; zoom?: number }): void;
  /** Fly the camera (queued until the map is ready). */
  flyTo(target: { center?: [number, number]; zoom?: number; duration?: number }): void;
  /** Unmount the widget and release the map. */
  destroy(): void;
}

interface WidgetState {
  markers: MarkerSpec[];
  tracks: TrackSpec[];
}

const DEFAULT_CENTER: [number, number] = [121.47, 31.23];
const DEFAULT_ZOOM = 12;

function WidgetRoot({
  options,
  state,
  onReady,
}: {
  options: MapWidgetOptions;
  state: WidgetState;
  onReady: (map: MapLibreMap) => void;
}) {
  return createElement(MapView, {
    basemap: { url: options.basemapUrl, glyphs: options.glyphsUrl },
    center: options.center ?? DEFAULT_CENTER,
    zoom: options.zoom ?? DEFAULT_ZOOM,
    maxBounds: options.maxBounds,
    markers: state.markers,
    tracks: state.tracks,
    showCenterHud: options.showCenterHud,
    navControl: options.navControl,
    onMapReady: onReady,
    onClick: options.onClick,
    onMove: options.onMove,
    onZoom: options.onZoom,
    onIdle: options.onIdle,
  });
}

export function createMapWidget(container: HTMLElement, options: MapWidgetOptions): MapWidget {
  const root = createRoot(container);
  const mapRef: { current: MapLibreMap | null } = { current: null };
  const pendingFly: Array<{ center?: [number, number]; zoom?: number; duration?: number }> = [];
  const state: WidgetState = { markers: options.markers ?? [], tracks: options.tracks ?? [] };
  // Mutable copy so setBasemap can swap the basemap/center/zoom at runtime.
  const liveOptions: MapWidgetOptions = { ...options };

  const render = () =>
    root.render(
      createElement(WidgetRoot, {
        options: liveOptions,
        state,
        onReady: (map) => {
          mapRef.current = map;
          while (pendingFly.length) map.flyTo(pendingFly.shift()!);
        },
      }),
    );
  render();

  return {
    setData(next) {
      if (next.markers) state.markers = next.markers;
      if (next.tracks) state.tracks = next.tracks;
      render();
    },
    setBasemap(basemapUrl, opts) {
      liveOptions.basemapUrl = basemapUrl;
      if (opts?.center) liveOptions.center = opts.center;
      if (opts?.zoom !== undefined) liveOptions.zoom = opts.zoom;
      render();
    },
    // Pending flyTo targets are replayed once the map becomes ready; note they
    // would also apply to a NEW map after setBasemap (queued before the swap).
    flyTo(target) {
      const map = mapRef.current;
      if (map) {
        map.flyTo(target);
      } else {
        pendingFly.push(target);
      }
    },
    destroy() {
      root.unmount();
    },
  };
}
