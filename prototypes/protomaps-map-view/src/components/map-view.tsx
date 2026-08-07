import { useEffect, useRef } from "react";
import type { Map as MapLibreMap, MapEventType } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useMapInstance } from "../lib/map/hooks/use-map-instance.ts";
import { toMarkerFeature, toTrackFeature } from "../lib/map/geojson.ts";
import { syncMarkerLayer } from "../lib/map/layers/marker-layer.ts";
import { syncTrackLayer } from "../lib/map/layers/track-layer.ts";
import type { MapFlavor } from "../lib/map/basemap/protomaps.ts";
import type { MarkerSpec, TrackSpec } from "../lib/map/specs.ts";

// Public API kept here for backwards compatibility (specs live in lib/map).
export type { MarkerSpec, TrackSpec } from "../lib/map/specs.ts";
export type { MapFlavor } from "../lib/map/basemap/protomaps.ts";

export interface MapViewProps {
  basemap: {
    /** pmtiles:// URL of the basemap file (see src/config.ts). */
    url: string;
    flavor?: MapFlavor;
    /** Label language, e.g. "zh". */
    lang?: string;
    /** Glyphs URL template (default: local `/glyphs/...`, see basemap/protomaps.ts). */
    glyphs?: string;
  };
  center: [number, number];
  zoom: number;
  /** Constrain panning/zooming to this [[minLng, minLat], [maxLng, maxLat]] box. */
  maxBounds?: [[number, number], [number, number]];
  /** External point markers with optional labels / popups. */
  markers?: MarkerSpec[];
  /** Track (line) annotations. */
  tracks?: TrackSpec[];
  /** Live HUD showing current center / zoom in the top-left corner. */
  showCenterHud?: boolean;
  navControl?: boolean;
  /** Extra class for the map container (controls its size). */
  className?: string;
  /** Called once the style has loaded (good for adding custom layers). */
  onMapReady?: (map: MapLibreMap) => void;
  // Event API (Phase 7): business code listens through props, not MapLibre.
  onClick?: (e: MapEventType["click"]) => void;
  onMove?: (e: MapEventType["move"]) => void;
  onZoom?: (e: MapEventType["zoom"]) => void;
  onIdle?: (e: MapEventType["idle"]) => void;
}

/**
 * Thin React wrapper around MapController + layer modules. The controller is
 * created once; switching the basemap (url / flavor / glyphs) recreates it via
 * useMapInstance's resetKey, and center/zoom changes move the camera. Markers
 * / tracks / event handlers are synced reactively.
 */
export function MapView({
  basemap,
  center,
  zoom,
  maxBounds,
  markers = [],
  tracks = [],
  showCenterHud = false,
  navControl = true,
  className,
  onMapReady,
  onClick,
  onMove,
  onZoom,
  onIdle,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // Basemap identity: changing url / flavor / glyphs recreates the map with a
  // fresh controller (useMapInstance resetKey) — this is how a user switches
  // between shanghai.pmtiles / tokyo.pmtiles at runtime.
  const basemapKey = `${basemap.url}|${basemap.flavor ?? "light"}|${basemap.glyphs ?? ""}`;
  const controller = useMapInstance(
    containerRef,
    { basemap, center, zoom, maxBounds, navControl, showCenterHud },
    basemapKey,
  );
  const map = controller?.map ?? null;

  const onMapReadyRef = useRef(onMapReady);
  onMapReadyRef.current = onMapReady;

  // Camera sync: move the camera when center/zoom props change (no remount).
  // Guarded by value comparison so re-renders with identical values are no-ops.
  useEffect(() => {
    if (!controller) return;
    const c = controller.getCenter();
    if (c.lng === center[0] && c.lat === center[1] && controller.getZoom() === zoom) return;
    controller.flyTo({ center, zoom, duration: 0 });
  }, [controller, center[0], center[1], zoom]);

  // onMapReady: fire once the style has loaded (controller handles the
  // already-loaded case so the callback is never missed).
  useEffect(() => {
    if (!controller) return;
    controller.onReady(() => onMapReadyRef.current?.(controller.map));
  }, [controller]);

  // Markers: rebuild on change (few points → maplibre Marker with DOM label).
  useEffect(() => {
    if (!map) return;
    return syncMarkerLayer(map, markers.map(toMarkerFeature));
  }, [map, markers]);

  // Tracks: GeoJSON source + line layer (waits for style load internally).
  useEffect(() => {
    if (!map) return;
    return syncTrackLayer(map, tracks.map(toTrackFeature));
  }, [map, tracks]);

  // Event API: forward prop handlers to the map.
  useEffect(() => {
    if (!map) return;
    if (onClick) map.on("click", onClick);
    if (onMove) map.on("move", onMove);
    if (onZoom) map.on("zoom", onZoom);
    if (onIdle) map.on("idle", onIdle);
    return () => {
      if (onClick) map.off("click", onClick);
      if (onMove) map.off("move", onMove);
      if (onZoom) map.off("zoom", onZoom);
      if (onIdle) map.off("idle", onIdle);
    };
  }, [map, onClick, onMove, onZoom, onIdle]);

  return <div ref={containerRef} className={`relative h-full w-full ${className ?? ""}`} />;
}
