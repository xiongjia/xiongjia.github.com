import { describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { syncTrackLayer } from "./track-layer.ts";
import type { TrackFeature } from "./track-layer.ts";

interface MockMap {
  addSource: Mock;
  removeSource: Mock;
  getSource: Mock;
  addLayer: Mock;
  removeLayer: Mock;
  getLayer: Mock;
  isStyleLoaded: Mock;
  once: Mock;
  off: Mock;
  fire: (event: string) => void;
}

function createMockMap(styleLoaded = true): MockMap {
  const sources = new Map<string, unknown>();
  const layers = new Map<string, unknown>();
  const listeners = new Map<string, Array<() => void>>();
  return {
    addSource: vi.fn((id: string, src: unknown) => sources.set(id, src)),
    removeSource: vi.fn((id: string) => sources.delete(id)),
    getSource: vi.fn((id: string) => sources.get(id)),
    addLayer: vi.fn((l: { id: string }) => layers.set(l.id, l)),
    removeLayer: vi.fn((id: string) => layers.delete(id)),
    getLayer: vi.fn((id: string) => layers.get(id)),
    isStyleLoaded: vi.fn(() => styleLoaded),
    once: vi.fn((event: string, cb: () => void) => {
      const list = listeners.get(event) ?? [];
      list.push(cb);
      listeners.set(event, list);
    }),
    off: vi.fn((event: string, cb: () => void) => {
      listeners.set(
        event,
        (listeners.get(event) ?? []).filter((f) => f !== cb),
      );
    }),
    fire: (event: string) => {
      for (const cb of listeners.get(event) ?? []) cb();
    },
  };
}

function track(name: string, color: string): TrackFeature {
  return {
    type: "Feature",
    properties: { name, color },
    geometry: {
      type: "LineString",
      coordinates: [
        [121.46, 31.185],
        [121.45, 31.19],
      ],
    },
  };
}

describe("syncTrackLayer", () => {
  it("adds one source + line layer per track with index-based ids", () => {
    const map = createMockMap();
    const cleanup = syncTrackLayer(map as never, [track("A", "#111111"), track("B", "#222222")]);

    expect(map.addSource).toHaveBeenCalledTimes(2);
    expect(map.addSource.mock.calls[0][0]).toBe("track-0");
    expect(map.addSource.mock.calls[1][0]).toBe("track-1");
    expect(map.addLayer).toHaveBeenCalledTimes(2);
    const firstLayer = map.addLayer.mock.calls[0][0] as {
      id: string;
      type: string;
      paint: { "line-color": string };
    };
    expect(firstLayer.id).toBe("track-0");
    expect(firstLayer.type).toBe("line");
    expect(firstLayer.paint["line-color"]).toBe("#111111");
    // geometry data passed through to the source
    expect((map.addSource.mock.calls[0][1] as { data: TrackFeature }).data.geometry.type).toBe(
      "LineString",
    );

    cleanup();
  });

  it("keeps ids distinct even when track names collide", () => {
    const map = createMockMap();
    syncTrackLayer(map as never, [track("same", "#111111"), track("same", "#222222")]);
    expect(map.addLayer.mock.calls.map((c) => (c[0] as { id: string }).id)).toEqual([
      "track-0",
      "track-1",
    ]);
  });

  it("waits for the style to load and re-applies on load", () => {
    const map = createMockMap(false);
    syncTrackLayer(map as never, [track("A", "#111111")]);
    expect(map.addSource).not.toHaveBeenCalled();

    map.fire("load");
    expect(map.addSource).toHaveBeenCalledTimes(1);
  });

  it("re-apply removes the previous sources/layers (idempotent)", () => {
    const map = createMockMap(false);
    syncTrackLayer(map as never, [track("A", "#111111")]);
    map.fire("load");
    // second call while style now loaded → previous layers removed first
    map.isStyleLoaded.mockReturnValue(true);
    syncTrackLayer(map as never, [track("B", "#222222")]);

    expect(map.removeLayer).toHaveBeenCalledWith("track-0");
    expect(map.removeSource).toHaveBeenCalledWith("track-0");
    expect(map.addSource.mock.calls.map((c) => c[0])).toEqual(["track-0", "track-0"]);
    expect(
      (map.addLayer.mock.calls[1][0] as { paint: { "line-color": string } }).paint["line-color"],
    ).toBe("#222222");
  });

  it("cleanup stops pending load work", () => {
    const map = createMockMap(false);
    const cleanup = syncTrackLayer(map as never, [track("A", "#111111")]);
    cleanup();
    map.fire("load");
    expect(map.addSource).not.toHaveBeenCalled();
  });
});
