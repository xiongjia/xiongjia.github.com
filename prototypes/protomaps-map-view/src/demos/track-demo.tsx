import { LngLatBounds } from "maplibre-gl";
import type { Map as MapLibreMap } from "maplibre-gl";
import { MapView } from "../components/map-view.tsx";
import { defaultCenter, pmtilesUrl } from "../config.ts";
import { centuryParkTrack, riversideTrack, trackMarkers } from "../lib/sample-data.ts";
import type { TrackSpec } from "../components/map-view.tsx";

const tracks: TrackSpec[] = [riversideTrack, centuryParkTrack];

/** Track annotations: two line layers + start markers, auto-fit to both routes. */
export function TrackDemo() {
  const handleReady = (map: MapLibreMap) => {
    const bounds = new LngLatBounds();
    for (const track of tracks) {
      for (const [lng, lat] of track.coordinates) {
        bounds.extend([lng, lat]);
      }
    }
    map.fitBounds(bounds, { padding: 60, duration: 0 });
  };

  return (
    <MapView
      basemap={{ url: pmtilesUrl }}
      center={defaultCenter}
      zoom={11}
      tracks={tracks}
      markers={trackMarkers}
      onMapReady={handleReady}
      showCenterHud
    />
  );
}
