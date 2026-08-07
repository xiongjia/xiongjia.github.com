import type { MapFlavor } from "./basemap/protomaps.ts";

/**
 * Convenience specs for map users (converted to GeoJSON features by
 * lib/map/geojson.ts). Kept as the public, backward-compatible API of
 * MapView / the widget; the core layer only ever sees GeoJSON.
 */
export interface MarkerSpec {
  lng: number;
  lat: number;
  /** Text label rendered next to the marker. */
  label?: string;
  /**
   * HTML content injected via Popup.setHTML — **caller must sanitize**
   * untrusted input (XSS vector; see README → Embeddable widget).
   */
  popupContent?: string;
  /** Background color for the default dot marker (ignored when `emoji` is set). */
  color?: string;
  /** Render an emoji glyph instead of the colored dot (e.g. "☕", "🏁", "⭐"). */
  emoji?: string;
}

export interface TrackSpec {
  name: string;
  color: string;
  /** [lng, lat][] polyline; when `closed` it renders as a ring. */
  coordinates: [number, number][];
  closed?: boolean;
}

export type { MapFlavor };
