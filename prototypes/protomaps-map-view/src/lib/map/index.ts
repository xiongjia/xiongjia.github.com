export { MapController } from "./map-controller.ts";
export type { CameraTarget, MapControllerOptions } from "./map-controller.ts";

export type { MarkerSpec, TrackSpec } from "./specs.ts";
export { createProtomapsStyle, PROTOMAPS_ATTRIBUTION } from "./basemap/protomaps.ts";
export type { MapFlavor, ProtomapsBasemapOptions } from "./basemap/protomaps.ts";

export { syncMarkerLayer } from "./layers/marker-layer.ts";
export type { MarkerFeature, MarkerFeatureProps } from "./layers/marker-layer.ts";

export { syncTrackLayer } from "./layers/track-layer.ts";
export type { TrackFeature, TrackFeatureProps } from "./layers/track-layer.ts";

export { useMapInstance } from "./hooks/use-map-instance.ts";
