import { describe, expect, it } from "vitest";
import { parseSource, tileXY } from "./glyph-utils.ts";

describe("tileXY", () => {
  it("maps the origin to tile (0,0) at z0", () => {
    expect(tileXY(0, 0, 0)).toEqual([0, 0]);
  });

  it("matches known slippy-tile coordinates (Shanghai at z11)", () => {
    // 121.47, 31.23 @ z11 → (1715, 836) — matches the tiles MapLibre requested
    expect(tileXY(121.47, 31.23, 11)).toEqual([1715, 836]);
  });

  it("wraps lng at the antimeridian and handles negative lat", () => {
    const x = tileXY(-179, 0, 1)[0];
    expect(x).toBe(0);
    const [x2, y2] = tileXY(0, -45, 1);
    expect(x2).toBe(1);
    expect(y2).toBeGreaterThan(0);
  });
});

describe("parseSource", () => {
  it("parses --source=NAME", () => {
    expect(parseSource(["--source=maplibre"])).toBe("maplibre");
    expect(parseSource(["--source=protomaps"])).toBe("protomaps");
  });

  it("parses --source NAME", () => {
    expect(parseSource(["--source", "maplibre"])).toBe("maplibre");
  });

  it("falls back to protomaps for unknown / missing source", () => {
    expect(parseSource(["--source=bogus"])).toBe("protomaps");
    expect(parseSource([])).toBe("protomaps");
    expect(parseSource(["--source"])).toBe("protomaps");
  });
});
