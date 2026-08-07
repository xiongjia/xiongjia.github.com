import type { LineString, Point, Polygon } from "geojson";
import type { MarkerSpec, TrackSpec } from "./specs.ts";
import type { MarkerFeature, MarkerFeatureProps } from "./layers/marker-layer.ts";
import type { TrackFeature, TrackFeatureProps } from "./layers/track-layer.ts";

/** Convert a MarkerSpec to a GeoJSON Point feature (Phase 4 model). */
export function toMarkerFeature(spec: MarkerSpec): MarkerFeature {
  const properties: MarkerFeatureProps = {
    label: spec.label,
    popupContent: spec.popupContent,
    color: spec.color,
    emoji: spec.emoji,
  };
  const geometry: Point = { type: "Point", coordinates: [spec.lng, spec.lat] };
  return { type: "Feature", properties, geometry };
}

/** Convert a TrackSpec to a GeoJSON LineString/Polygon feature. */
export function toTrackFeature(spec: TrackSpec): TrackFeature {
  const properties: TrackFeatureProps = { name: spec.name, color: spec.color };
  const geometry: LineString | Polygon = spec.closed
    ? { type: "Polygon", coordinates: [spec.coordinates] }
    : { type: "LineString", coordinates: spec.coordinates };
  return { type: "Feature", properties, geometry };
}
