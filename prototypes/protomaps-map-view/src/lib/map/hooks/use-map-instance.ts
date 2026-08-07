import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { MapController } from "../map-controller.ts";
import type { MapControllerOptions } from "../map-controller.ts";

/**
 * Create a MapController bound to the given container for the lifetime of the
 * component (destroyed on unmount).
 *
 * `resetKey` controls when the map is recreated: changing it (e.g. a different
 * basemap URL) destroys the current map and creates a fresh one with the
 * latest options — this is how switching basemaps works (shanghai.pmtiles ↔
 * tokyo.pmtiles). Camera moves for plain center/zoom changes are handled by
 * the MapView layer, not here.
 */
export function useMapInstance(
  containerRef: RefObject<HTMLDivElement | null>,
  options: MapControllerOptions,
  resetKey: string,
): MapController | null {
  const [controller, setController] = useState<MapController | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const instance = new MapController(container, optionsRef.current);
    setController(instance);
    return () => instance.destroy();
  }, [resetKey]);

  return controller;
}
