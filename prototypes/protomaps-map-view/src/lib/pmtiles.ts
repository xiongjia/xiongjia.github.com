import { addProtocol } from "maplibre-gl";
import { Protocol } from "pmtiles";

let registered = false;

/**
 * Register the `pmtiles://` custom protocol exactly once (module-level guard).
 * MapLibre routes tile requests whose URL starts with `pmtiles://` through the
 * protocol handler, which reads the file via HTTP Range requests.
 */
export function ensurePmtilesProtocol(): void {
  if (registered) return;
  const protocol = new Protocol();
  addProtocol("pmtiles", protocol.tile);
  registered = true;
}
