import { useState } from "react";
import { MapView } from "../components/map-view.tsx";
import type { MarkerSpec, TrackSpec } from "../components/map-view.tsx";
import { pmtilesUrl } from "../config.ts";

interface RegionConfig {
  id: string;
  label: string;
  basemapUrl: string;
  center: [number, number];
  zoom: number;
  markers?: MarkerSpec[];
  tracks?: TrackSpec[];
}

/**
 * Multiple basemaps at different coordinates. MapView recreates the map
 * whenever `basemap.url` (basemapKey) changes and moves the camera on
 * center/zoom changes — so switching regions is just a prop change.
 *
 * With a `tokyo.pmtiles` file served next to shanghai.pmtiles, uncomment the
 * Tokyo preset: `basemapUrl: "pmtiles:///pmtiles/tokyo.pmtiles"` with Tokyo
 * coordinates — everything else works unchanged.
 */
const REGIONS: RegionConfig[] = [
  {
    id: "xuhui",
    label: "上海 · 徐汇滨江",
    basemapUrl: pmtilesUrl,
    center: [121.458, 31.188],
    zoom: 13,
    markers: [{ lng: 121.458, lat: 31.188, label: "徐汇滨江", emoji: "📍" }],
  },
  {
    id: "century",
    label: "上海 · 世纪公园",
    basemapUrl: pmtilesUrl,
    center: [121.5535, 31.218],
    zoom: 13,
    markers: [{ lng: 121.5535, lat: 31.218, label: "世纪公园", emoji: "🌳" }],
  },
  // 有 tokyo.pmtiles 后取消注释：
  // {
  //   id: "tokyo",
  //   label: "东京 · 涩谷",
  //   basemapUrl: "pmtiles:///pmtiles/tokyo.pmtiles",
  //   center: [139.7, 35.66],
  //   zoom: 12,
  //   markers: [{ lng: 139.7, lat: 35.66, label: "涩谷", emoji: "🗼" }],
  // },
];

/** Region switching: same basemap file at different coordinates (camera path), ready for multi-file basemaps. */
export function RegionDemo() {
  const [active, setActive] = useState<RegionConfig>(REGIONS[0]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
        {REGIONS.map((r) => (
          <button
            key={r.id}
            type="button"
            className={
              r.id === active.id
                ? "cursor-pointer rounded-md border border-blue-600 bg-blue-600 px-3.5 py-1.5 text-sm text-white"
                : "cursor-pointer rounded-md border border-slate-300 bg-white px-3.5 py-1.5 text-sm text-slate-700 hover:border-slate-400"
            }
            onClick={() => setActive(r)}
          >
            {r.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        <MapView
          basemap={{ url: active.basemapUrl }}
          center={active.center}
          zoom={active.zoom}
          markers={active.markers}
          showCenterHud
        />
      </div>
    </div>
  );
}
