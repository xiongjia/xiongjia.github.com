import type { MarkerSpec, TrackSpec } from "../components/map-view.tsx";

/** Build a richer popup body (inline styles — injected as raw HTML). */
function coffeePopup(
  name: string,
  address: string,
  rating: number,
  hours: string,
  tags: string[],
): string {
  const stars = "★".repeat(Math.round(rating)) + "☆".repeat(5 - Math.round(rating));
  return `
    <div style="min-width:230px;font-family:system-ui,sans-serif;font-size:13px;color:#0f172a">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span style="font-size:15px;font-weight:700">${name}</span>
        <span style="font-size:11px;color:#16a34a;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:4px;padding:1px 6px">营业中</span>
      </div>
      <div style="color:#475569;margin-bottom:4px">📍 ${address}</div>
      <div style="color:#f59e0b;margin-bottom:4px;letter-spacing:1px">${stars} <span style="color:#64748b;letter-spacing:0">${rating.toFixed(1)}</span></div>
      <div style="color:#475569;margin-bottom:8px">🕐 ${hours}</div>
      <div>${tags.map((t) => `<span style="display:inline-block;background:#f1f5f9;color:#475569;border-radius:4px;padding:1px 7px;margin:0 4px 4px 0;font-size:12px">${t}</span>`).join(", ")}</div>
    </div>`;
}

/** Demo markers — hand-written sample points (self-contained, no external data). */
export const coffeeMarkers: MarkerSpec[] = [
  {
    lng: 121.47,
    lat: 31.23,
    label: "咖啡A",
    color: "#e11d48",
    emoji: "☕",
    popupContent: coffeePopup("咖啡A", "徐汇区滨江大道 100 号", 4.7, "周一至周日 08:00 - 22:00", [
      "手冲",
      "Wi-Fi",
      "宠物友好",
    ]),
  },
  {
    lng: 121.49,
    lat: 31.21,
    label: "咖啡B",
    color: "#f59e0b",
    emoji: "🧋",
    popupContent: coffeePopup(
      "咖啡B",
      "黄浦区南京东路 50 号 2F",
      4.5,
      "周一至周五 07:30 - 20:00 · 周末 09:00 - 21:00",
      ["澳白", "外带", "可充电"],
    ),
  },
  {
    lng: 121.44,
    lat: 31.26,
    label: "咖啡C",
    color: "#10b981",
    emoji: "🍵",
    popupContent: coffeePopup("咖啡C", "静安区愚园路 218 号", 4.9, "周一至周日 09:00 - 23:00", [
      "特调",
      "精酿",
      "安静",
    ]),
  },
];

/**
 * Demo running track — a hand-written loop along the Xuhui riverside
 * (徐汇滨江), plausible coordinates only (sample data, not a real GPS track).
 */
export const riversideTrack: TrackSpec = {
  name: "徐汇滨江",
  color: "#2563eb",
  coordinates: [
    [121.4602, 31.185],
    [121.4605, 31.1875],
    [121.4592, 31.1902],
    [121.4588, 31.1927],
    [121.458, 31.1952],
    [121.4572, 31.1978],
    [121.4564, 31.2002],
    [121.4556, 31.2028],
    [121.4535, 31.203],
    [121.452, 31.201],
    [121.453, 31.198],
    [121.4542, 31.1955],
    [121.4555, 31.1928],
    [121.4568, 31.19],
    [121.458, 31.1875],
    [121.4602, 31.185],
  ],
};

export const centuryParkTrack: TrackSpec = {
  name: "世纪公园",
  color: "#ea580c",
  coordinates: [
    [121.5485, 31.2135],
    [121.552, 31.2132],
    [121.555, 31.2135],
    [121.5575, 31.2145],
    [121.559, 31.216],
    [121.56, 31.218],
    [121.5595, 31.22],
    [121.558, 31.2215],
    [121.5555, 31.2225],
    [121.5525, 31.223],
    [121.5495, 31.2228],
    [121.547, 31.2218],
    [121.5458, 31.22],
    [121.5455, 31.218],
    [121.546, 31.216],
    [121.547, 31.2148],
    [121.5485, 31.2135],
  ],
};

/** Start markers (emoji) for each track — one per route. */
export const trackMarkers: MarkerSpec[] = [
  {
    lng: 121.4602,
    lat: 31.185,
    label: "起/终",
    emoji: "🏁",
    popupContent: "<b>徐汇滨江</b><br/>跑步起终点",
  },
  {
    lng: 121.5485,
    lat: 31.2135,
    label: "起/终",
    emoji: "🏁",
    popupContent: "<b>世纪公园</b><br/>环湖跑步起终点",
  },
];

/** Batch points around the Shanghai demo center, rendered via a GeoJSON layer (performance principle). */
export function generateRandomPoints(
  count: number,
  center: [number, number],
  spread: number,
): Array<{
  type: "Feature";
  properties: { id: number };
  geometry: { type: "Point"; coordinates: [number, number] };
}> {
  return Array.from({ length: count }, (_, i) => ({
    type: "Feature" as const,
    properties: { id: i },
    geometry: {
      type: "Point" as const,
      coordinates: [
        center[0] + (Math.random() - 0.5) * 2 * spread,
        center[1] + (Math.random() - 0.5) * 2 * spread,
      ],
    },
  }));
}
