import type { Map as MapLibreMap } from "maplibre-gl";
import type { Feature, LineString, Polygon } from "geojson";

export interface TrackFeatureProps {
  name: string;
  color: string;
}

export type TrackFeature = Feature<LineString | Polygon, TrackFeatureProps>;

/**
 * Render line/polygon features as GeoJSON-source line layers. Waits for the
 * style to load before adding sources/layers.
 *
 * Layer/source ids are index-based (`track-<i>`). The apply step removes any
 * stale ids first (this instance's previous adds + anything already under the
 * target ids), and the cleanup removes this instance's layers — so re-applying
 * after a tracks change never duplicates a source, and unmount cleans up (the
 * try/catch tolerates the map having been destroyed already).
 */
export function syncTrackLayer(map: MapLibreMap, features: TrackFeature[]): () => void {
  let disposed = false;
  const addedIds: string[] = [];

  const apply = () => {
    const idsToAdd = features.map((_, i) => `track-${i}`);
    for (const id of new Set([...addedIds, ...idsToAdd])) {
      try {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      } catch {
        // map already removed — nothing to clean
      }
    }
    addedIds.length = 0;

    features.forEach((feature, i) => {
      const id = `track-${i}`;
      addedIds.push(id);
      map.addSource(id, { type: "geojson", data: feature });
      map.addLayer({
        id,
        type: "line",
        source: id,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": feature.properties?.color, "line-width": 3 },
      });
    });
  };

  const onLoad = () => {
    if (!disposed) apply();
  };

  if (map.isStyleLoaded()) {
    apply();
  } else {
    map.once("load", onLoad);
  }
  return () => {
    disposed = true;
    map.off("load", onLoad);
    for (const id of addedIds) {
      try {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      } catch {
        // map already removed
      }
    }
  };
}
