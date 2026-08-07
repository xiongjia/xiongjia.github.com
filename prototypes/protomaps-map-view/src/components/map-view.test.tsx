// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { MapView } from "./map-view.tsx";

vi.mock("../lib/map/hooks/use-map-instance.ts", () => ({
  useMapInstance: vi.fn(),
}));
vi.mock("../lib/map/layers/marker-layer.ts", () => ({
  syncMarkerLayer: vi.fn(() => () => {}),
}));
vi.mock("../lib/map/layers/track-layer.ts", () => ({
  syncTrackLayer: vi.fn(() => () => {}),
}));

import { useMapInstance } from "../lib/map/hooks/use-map-instance.ts";
import { syncMarkerLayer, type MarkerFeature } from "../lib/map/layers/marker-layer.ts";
import { syncTrackLayer, type TrackFeature } from "../lib/map/layers/track-layer.ts";

const useMapInstanceMock = vi.mocked(useMapInstance);
const syncMarkerLayerMock = vi.mocked(syncMarkerLayer);
const syncTrackLayerMock = vi.mocked(syncTrackLayer);

beforeEach(() => {
  useMapInstanceMock.mockClear();
  syncMarkerLayerMock.mockClear();
  syncTrackLayerMock.mockClear();
});

function makeController(center: [number, number] = [1, 2], zoom = 3) {
  return {
    map: {},
    getCenter: vi.fn(() => ({ lng: center[0], lat: center[1] })),
    getZoom: vi.fn(() => zoom),
    flyTo: vi.fn(),
    onReady: vi.fn(),
  };
}

describe("MapView", () => {
  it("renders the map container div", () => {
    useMapInstanceMock.mockReturnValue(makeController() as never);
    const { container } = render(
      <MapView basemap={{ url: "pmtiles:///x" }} center={[1, 2]} zoom={3} />,
    );
    expect(container.querySelector("div")?.className).toContain("relative h-full w-full");
  });

  it("passes the basemap identity as the controller reset key", () => {
    useMapInstanceMock.mockReturnValue(makeController() as never);
    const { rerender } = render(
      <MapView basemap={{ url: "pmtiles:///shanghai" }} center={[1, 2]} zoom={3} />,
    );
    expect(useMapInstanceMock.mock.calls[0][2]).toBe("pmtiles:///shanghai|light|");

    rerender(<MapView basemap={{ url: "pmtiles:///tokyo" }} center={[1, 2]} zoom={3} />);
    expect(useMapInstanceMock.mock.calls[1][2]).toBe("pmtiles:///tokyo|light|");
  });

  it("syncs markers as GeoJSON point features", () => {
    useMapInstanceMock.mockReturnValue(makeController() as never);
    render(
      <MapView
        basemap={{ url: "pmtiles:///x" }}
        center={[1, 2]}
        zoom={3}
        markers={[{ lng: 121.47, lat: 31.23, label: "A", emoji: "☕" }]}
      />,
    );
    expect(syncMarkerLayerMock).toHaveBeenCalledTimes(1);
    const features = syncMarkerLayerMock.mock.calls[0][1] as MarkerFeature[];
    expect(features).toHaveLength(1);
    expect(features[0].geometry).toEqual({ type: "Point", coordinates: [121.47, 31.23] });
    expect(features[0].properties).toMatchObject({ label: "A", emoji: "☕" });
  });

  it("syncs tracks as GeoJSON line features", () => {
    useMapInstanceMock.mockReturnValue(makeController() as never);
    render(
      <MapView
        basemap={{ url: "pmtiles:///x" }}
        center={[1, 2]}
        zoom={3}
        tracks={[
          {
            name: "T",
            color: "#111111",
            coordinates: [
              [1, 2],
              [3, 4],
            ],
          },
        ]}
      />,
    );
    expect(syncTrackLayerMock).toHaveBeenCalledTimes(1);
    const features = syncTrackLayerMock.mock.calls[0][1] as TrackFeature[];
    expect(features[0].geometry.type).toBe("LineString");
  });

  it("moves the camera when center/zoom change, and no-ops on equal values", () => {
    const controller = makeController([1, 2], 3);
    useMapInstanceMock.mockReturnValue(controller as never);
    const { rerender } = render(
      <MapView basemap={{ url: "pmtiles:///x" }} center={[1, 2]} zoom={3} />,
    );
    expect(controller.flyTo).not.toHaveBeenCalled();

    // same values → still no camera move
    rerender(<MapView basemap={{ url: "pmtiles:///x" }} center={[1, 2]} zoom={3} />);
    expect(controller.flyTo).not.toHaveBeenCalled();

    // new center → flyTo
    rerender(<MapView basemap={{ url: "pmtiles:///x" }} center={[10, 20]} zoom={3} />);
    expect(controller.flyTo).toHaveBeenCalledWith({ center: [10, 20], zoom: 3, duration: 0 });
  });

  it("registers prop event handlers on the map and removes them on change", () => {
    const controller = makeController();
    const map = { on: vi.fn(), off: vi.fn() };
    controller.map = map;
    useMapInstanceMock.mockReturnValue(controller as never);
    const onClick = vi.fn();
    const { rerender } = render(
      <MapView basemap={{ url: "pmtiles:///x" }} center={[1, 2]} zoom={3} onClick={onClick} />,
    );
    expect(map.on).toHaveBeenCalledWith("click", onClick);

    rerender(
      <MapView basemap={{ url: "pmtiles:///x" }} center={[1, 2]} zoom={3} onClick={undefined} />,
    );
    expect(map.off).toHaveBeenCalledWith("click", onClick);
  });
});
