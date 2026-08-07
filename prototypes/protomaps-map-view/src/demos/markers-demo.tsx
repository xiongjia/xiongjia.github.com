import type { Map as MapLibreMap } from "maplibre-gl";
import { MapView } from "../components/map-view.tsx";
import { defaultCenter, pmtilesUrl } from "../config.ts";
import { coffeeMarkers, generateRandomPoints } from "../lib/sample-data.ts";

/**
 * External markers + text (few points → maplibre Marker with label/popup),
 * plus a batch of ~200 random points rendered as a GeoJSON circle layer
 * (many points → Layer, not Marker — performance principle).
 */
export function MarkersDemo() {
  const handleReady = (map: MapLibreMap) => {
    const points = generateRandomPoints(200, defaultCenter, 0.12);
    map.addSource("batch-points", {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: points,
      },
    });
    map.addLayer({
      id: "batch-circles",
      type: "circle",
      source: "batch-points",
      paint: {
        "circle-radius": 3,
        "circle-color": "#0ea5e9",
        "circle-stroke-width": 1,
        "circle-stroke-color": "#ffffff",
      },
    });
  };

  return (
    <MapView
      basemap={{ url: pmtilesUrl }}
      center={defaultCenter}
      zoom={11}
      markers={coffeeMarkers}
      onMapReady={handleReady}
      showCenterHud
    />
  );
}
