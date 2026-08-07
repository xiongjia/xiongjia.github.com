import { MapView } from "../components/map-view.tsx";
import { pmtilesUrl, smallRegion } from "../config.ts";

/**
 * Minimal basemap demo. Starts on a small region (Xuhui riverside) at zoom 13
 * so the first load fetches only a few tiles; keep the HUD + nav control to
 * show center/zoom behavior. No maxBounds on purpose — it would lock the
 * zoom (see src/config.ts smallRegion).
 */
export function BasicDemo() {
  return (
    <MapView
      basemap={{ url: pmtilesUrl }}
      center={smallRegion.center}
      zoom={smallRegion.zoom}
      showCenterHud
      navControl
    />
  );
}
