import type { Map as MapLibreMap } from "maplibre-gl";
import { Marker, Popup } from "maplibre-gl";
import type { Feature, Point } from "geojson";

export interface MarkerFeatureProps {
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

export type MarkerFeature = Feature<Point, MarkerFeatureProps>;

/**
 * Render point features as maplibre Markers (DOM element + optional label and
 * popup). Returns a cleanup that removes every marker it created.
 */
export function syncMarkerLayer(map: MapLibreMap, features: MarkerFeature[]): () => void {
  const markers: Marker[] = [];
  for (const feature of features) {
    const [lng, lat] = feature.geometry.coordinates;
    const props = feature.properties ?? {};

    const el = document.createElement("div");
    // maplibre positions the element itself (inline transform), so no
    // transform utilities here — use anchor "bottom" and order [label, glyph]
    // so the glyph's bottom sits exactly on the coordinate.
    el.className = "flex flex-col items-center";
    if (props.label) {
      const label = document.createElement("span");
      label.className =
        "mb-0.5 whitespace-nowrap rounded bg-slate-900/75 px-1.5 py-px text-xs text-white";
      label.textContent = props.label;
      el.appendChild(label);
    }
    if (props.emoji) {
      const glyph = document.createElement("span");
      glyph.className = "-mb-1 text-xl leading-none drop-shadow";
      glyph.textContent = props.emoji;
      el.appendChild(glyph);
    } else {
      const dot = document.createElement("span");
      dot.className = "h-3.5 w-3.5 rounded-full border-2 border-white shadow";
      dot.style.background = props.color ?? "#e11d48";
      el.appendChild(dot);
    }

    const marker = new Marker({ element: el, anchor: "bottom" }).setLngLat([lng, lat]);
    if (props.popupContent) {
      marker.setPopup(new Popup({ offset: 24 }).setHTML(props.popupContent));
    }
    marker.addTo(map);
    markers.push(marker);
  }
  return () => {
    for (const marker of markers) marker.remove();
  };
}
