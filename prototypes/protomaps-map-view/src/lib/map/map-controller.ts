import { Map as MapLibreMap, NavigationControl } from "maplibre-gl";
import type {
  FitBoundsOptions,
  LayerSpecification,
  LngLatBoundsLike,
  MapEventType,
  SourceSpecification,
} from "maplibre-gl";
import { ensurePmtilesProtocol } from "../pmtiles.ts";
import { createProtomapsStyle } from "./basemap/protomaps.ts";
import type { ProtomapsBasemapOptions } from "./basemap/protomaps.ts";

export interface MapControllerOptions {
  basemap: ProtomapsBasemapOptions;
  center: [number, number];
  zoom: number;
  /** Constrain panning/zooming to this [[minLng, minLat], [maxLng, maxLat]] box. */
  maxBounds?: [[number, number], [number, number]];
  navControl?: boolean;
  /** Live HUD showing current center / zoom in the top-left corner. */
  showCenterHud?: boolean;
}

export interface CameraTarget {
  center?: [number, number];
  zoom?: number;
  duration?: number;
}

/**
 * Framework-agnostic owner of the MapLibre instance: lifecycle (create /
 * destroy), camera helpers, event wiring and layer/source management. The
 * React layer (MapView / useMapInstance) only binds it to a component
 * lifecycle; business code never touches MapLibre directly.
 */
export class MapController {
  readonly map: MapLibreMap;

  private hudEl: HTMLDivElement | null = null;
  private disposed = false;

  constructor(container: HTMLElement, options: MapControllerOptions) {
    ensurePmtilesProtocol();
    this.map = new MapLibreMap({
      container,
      style: createProtomapsStyle(options.basemap),
      center: options.center,
      zoom: options.zoom,
      maxBounds: options.maxBounds,
    });

    if (options.navControl !== false) {
      this.map.addControl(new NavigationControl(), "top-right");
    }
    if (options.showCenterHud) {
      this.setupHud();
    }
  }

  get isDisposed(): boolean {
    return this.disposed;
  }

  /**
   * Register a ready callback that fires when the style has loaded — called
   * immediately if the map already loaded (avoids the listener race between
   * map creation and the React effect that wires callbacks).
   *
   * The callback fires only on successful load; a failed load is not reported
   * (no error channel — callers that care should also listen to map `error`
   * events). This is what MapView's `onMapReady` prop delegates to.
   */
  onReady(callback: (controller: MapController) => void): void {
    if (this.map.loaded()) {
      callback(this);
    } else {
      this.map.once("load", () => callback(this));
    }
  }

  destroy(): void {
    if (this.disposed) return;
    this.map.remove();
    // map.remove() does not clean arbitrary children appended to the
    // container (e.g. the HUD) — remove them explicitly.
    this.hudEl?.remove();
    this.hudEl = null;
    this.disposed = true;
  }

  // -- camera ---------------------------------------------------------------

  flyTo(target: CameraTarget): void {
    this.map.flyTo(target);
  }

  fitBounds(bounds: LngLatBoundsLike, fitOptions?: FitBoundsOptions): void {
    this.map.fitBounds(bounds, fitOptions);
  }

  getCenter() {
    return this.map.getCenter();
  }

  getZoom(): number {
    return this.map.getZoom();
  }

  // -- events ---------------------------------------------------------------

  on<K extends keyof MapEventType>(type: K, listener: (ev: MapEventType[K]) => void): void {
    this.map.on(type, listener);
  }

  off<K extends keyof MapEventType>(type: K, listener: (ev: MapEventType[K]) => void): void {
    this.map.off(type, listener);
  }

  // -- layers / sources ------------------------------------------------------

  addSource(id: string, source: SourceSpecification): void {
    const apply = () => this.map.addSource(id, source);
    if (this.map.isStyleLoaded()) {
      apply();
    } else {
      this.map.once("load", apply);
    }
  }

  removeSource(id: string): void {
    if (this.map.getSource(id)) this.map.removeSource(id);
  }

  addLayer(layer: LayerSpecification, beforeId?: string): void {
    const apply = () => this.map.addLayer(layer, beforeId);
    if (this.map.isStyleLoaded()) {
      apply();
    } else {
      this.map.once("load", apply);
    }
  }

  removeLayer(id: string): void {
    if (this.map.getLayer(id)) this.map.removeLayer(id);
  }

  // -- internals --------------------------------------------------------------

  private setupHud(): void {
    const el = document.createElement("div");
    el.className =
      "pointer-events-none absolute left-2 top-2 z-10 rounded bg-slate-900/80 px-2 py-1 font-mono text-xs leading-5 text-white";
    this.map.getContainer().appendChild(el);
    this.hudEl = el;

    const update = () => {
      const c = this.map.getCenter();
      el.textContent = `center ${c.lng.toFixed(5)}, ${c.lat.toFixed(5)} · zoom ${this.map.getZoom().toFixed(2)}`;
    };
    this.map.on("move", update);
    update();
  }
}
