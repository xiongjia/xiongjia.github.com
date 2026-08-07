import { describe, expect, it } from "vitest";
import { toMarkerFeature, toTrackFeature } from "./geojson.ts";

describe("toMarkerFeature", () => {
  it("converts a full MarkerSpec to a Point GeoJSON feature", () => {
    const feature = toMarkerFeature({
      lng: 121.47,
      lat: 31.23,
      label: "咖啡A",
      emoji: "☕",
      color: "#e11d48",
      popupContent: "<b>咖啡A</b>",
    });
    expect(feature.type).toBe("Feature");
    expect(feature.geometry).toEqual({ type: "Point", coordinates: [121.47, 31.23] });
    expect(feature.properties).toEqual({
      label: "咖啡A",
      emoji: "☕",
      color: "#e11d48",
      popupContent: "<b>咖啡A</b>",
    });
  });

  it("handles a minimal spec (undefined optional props)", () => {
    const feature = toMarkerFeature({ lng: 0, lat: 0 });
    expect(feature.properties).toEqual({
      label: undefined,
      popupContent: undefined,
      color: undefined,
      emoji: undefined,
    });
    expect(feature.geometry.coordinates).toEqual([0, 0]);
  });
});

describe("toTrackFeature", () => {
  it("converts an open track to a LineString feature", () => {
    const feature = toTrackFeature({
      name: "徐汇滨江",
      color: "#2563eb",
      coordinates: [
        [121.46, 31.185],
        [121.45, 31.19],
      ],
    });
    expect(feature.geometry.type).toBe("LineString");
    expect(feature.geometry.coordinates).toEqual([
      [121.46, 31.185],
      [121.45, 31.19],
    ]);
    expect(feature.properties).toEqual({ name: "徐汇滨江", color: "#2563eb" });
  });

  it("converts a closed track to a Polygon feature (ring wrapped)", () => {
    const feature = toTrackFeature({
      name: "世纪公园",
      color: "#ea580c",
      coordinates: [
        [121.5485, 31.2135],
        [121.56, 31.218],
        [121.5485, 31.2135],
      ],
      closed: true,
    });
    expect(feature.geometry.type).toBe("Polygon");
    expect(feature.geometry.coordinates).toHaveLength(1);
    expect(feature.geometry.coordinates[0]).toHaveLength(3);
  });
});
