import { useState } from "react";
import { MapView } from "../components/map-view.tsx";
import type { MapFlavor } from "../components/map-view.tsx";
import { pmtilesUrl, smallRegion } from "../config.ts";

const FLAVORS: { id: MapFlavor; label: string }[] = [
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
  { id: "grayscale", label: "Grayscale" },
  { id: "black", label: "Black" },
];

/** Flavor switching: the MapView is remounted via `key` so each flavor gets a fresh map. */
export function StyleDemo() {
  const [flavor, setFlavor] = useState<MapFlavor>("light");

  return (
    <div className="flex h-full flex-col">
      <div className="flex gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
        {FLAVORS.map((f) => (
          <button
            key={f.id}
            type="button"
            className={
              flavor === f.id
                ? "cursor-pointer rounded-md border border-blue-600 bg-blue-600 px-3.5 py-1.5 text-sm text-white"
                : "cursor-pointer rounded-md border border-slate-300 bg-white px-3.5 py-1.5 text-sm text-slate-700 hover:border-slate-400"
            }
            onClick={() => setFlavor(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        <MapView
          key={flavor}
          basemap={{ url: pmtilesUrl, flavor }}
          center={smallRegion.center}
          zoom={smallRegion.zoom}
          showCenterHud
        />
      </div>
    </div>
  );
}
