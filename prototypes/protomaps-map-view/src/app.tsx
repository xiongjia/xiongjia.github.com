import { useState } from "react";
import type { ComponentType } from "react";
import { BasicDemo } from "./demos/basic-demo.tsx";
import { MarkersDemo } from "./demos/markers-demo.tsx";
import { TrackDemo } from "./demos/track-demo.tsx";
import { StyleDemo } from "./demos/style-demo.tsx";
import { RegionDemo } from "./demos/region-demo.tsx";

type DemoId = "basic" | "markers" | "track" | "style" | "region";

const DEMOS: { id: DemoId; label: string; component: ComponentType }[] = [
  { id: "basic", label: "Basic", component: BasicDemo },
  { id: "markers", label: "Markers", component: MarkersDemo },
  { id: "track", label: "Track", component: TrackDemo },
  { id: "region", label: "Region", component: RegionDemo },
  { id: "style", label: "Style", component: StyleDemo },
];

/** Tab switcher: switching unmounts the old demo (map.remove() in cleanup) and mounts the new one. */
export function App() {
  const [active, setActive] = useState<DemoId>("basic");
  const Demo = DEMOS.find((d) => d.id === active)?.component ?? BasicDemo;

  return (
    <div className="flex h-full flex-col">
      <nav className="flex gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
        {DEMOS.map((d) => (
          <button
            key={d.id}
            type="button"
            className={
              d.id === active
                ? "cursor-pointer rounded-md border border-blue-600 bg-blue-600 px-3.5 py-1.5 text-sm text-white"
                : "cursor-pointer rounded-md border border-slate-300 bg-white px-3.5 py-1.5 text-sm text-slate-700 hover:border-slate-400"
            }
            onClick={() => setActive(d.id)}
          >
            {d.label}
          </button>
        ))}
      </nav>
      <main className="min-h-0 flex-1">
        <Demo />
      </main>
    </div>
  );
}
