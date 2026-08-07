// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";

// Mock maplibre Marker/Popup so the layer logic can be tested without WebGL.
// vi.hoisted: the mock factory is hoisted above the class declarations, so the
// shared state must be created there too.
const { MarkerMock, PopupMock, createdMarkers } = vi.hoisted(() => {
  const createdMarkers: Array<{ element: HTMLElement; remove: () => void; popup: unknown }> = [];
  class MarkerMock {
    element: HTMLElement;
    popup: unknown = null;
    constructor(opts: { element: HTMLElement }) {
      this.element = opts.element;
      createdMarkers.push(
        this as unknown as { element: HTMLElement; remove: () => void; popup: unknown },
      );
    }
    setLngLat() {
      return this;
    }
    setPopup(popup: unknown) {
      this.popup = popup;
      return this;
    }
    addTo() {
      return this;
    }
    remove = vi.fn();
  }
  class PopupMock {
    html = "";
    constructor(_opts: { offset?: number }) {}
    setHTML(html: string) {
      this.html = html;
      return this;
    }
  }
  return { MarkerMock, PopupMock, createdMarkers };
});

vi.mock("maplibre-gl", () => ({ Marker: MarkerMock, Popup: PopupMock }));

import { syncMarkerLayer } from "./marker-layer.ts";
import type { MarkerFeature } from "./marker-layer.ts";

function marker(overrides: Partial<MarkerFeature["properties"]> = {}): MarkerFeature {
  return {
    type: "Feature",
    properties: {
      label: undefined,
      popupContent: undefined,
      color: undefined,
      emoji: undefined,
      ...overrides,
    },
    geometry: { type: "Point", coordinates: [121.47, 31.23] },
  };
}

describe("syncMarkerLayer", () => {
  it("renders an emoji glyph (no dot) when emoji is set", () => {
    createdMarkers.length = 0;
    syncMarkerLayer({} as never, [marker({ emoji: "☕", label: "咖啡A" })]);
    const el = createdMarkers[0].element;
    expect(el.querySelector("span.text-xl")?.textContent).toBe("☕");
    expect(el.querySelector("span.h-3\\.5")).toBeNull();
    expect(el.querySelector("span.text-xs")?.textContent).toBe("咖啡A");
  });

  it("renders a colored dot when no emoji is set", () => {
    createdMarkers.length = 0;
    syncMarkerLayer({} as never, [marker({ color: "#e11d48" })]);
    const el = createdMarkers[0].element;
    const dot = el.querySelector("span.h-3\\.5") as HTMLElement;
    expect(dot).not.toBeNull();
    // jsdom normalizes the background shorthand to rgb()
    expect(dot.style.background).toBe("rgb(225, 29, 72)");
    expect(el.querySelector("span.text-xl")).toBeNull();
  });

  it("attaches a popup when popupContent is set", () => {
    createdMarkers.length = 0;
    syncMarkerLayer({} as never, [marker({ popupContent: "<b>x</b>" })]);
    expect(createdMarkers[0].popup).not.toBeNull();
  });

  it("cleanup removes every created marker", () => {
    createdMarkers.length = 0;
    const cleanup = syncMarkerLayer({} as never, [marker({}), marker({ emoji: "🏁" })]);
    cleanup();
    for (const m of createdMarkers) expect(m.remove).toHaveBeenCalled();
  });
});
