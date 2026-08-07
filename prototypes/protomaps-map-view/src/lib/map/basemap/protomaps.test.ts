import { describe, expect, it } from "vitest";
import { createProtomapsStyle, PROTOMAPS_ATTRIBUTION } from "./protomaps.ts";

describe("createProtomapsStyle", () => {
  it("builds a style with the protomaps vector source and no external sprite", () => {
    const style = createProtomapsStyle({ url: "pmtiles:///pmtiles/shanghai.pmtiles" });
    expect(style.version).toBe(8);
    expect(style.sprite).toBeUndefined();
    expect(style.glyphs).toBe("/glyphs/{fontstack}/{range}.pbf");
    const source = style.sources.protomaps;
    expect(source.type).toBe("vector");
    if (source.type === "vector") {
      expect(source.url).toBe("pmtiles:///pmtiles/shanghai.pmtiles");
      expect(source.attribution).toBe(PROTOMAPS_ATTRIBUTION);
    }
    expect(style.layers.length).toBeGreaterThan(0);
  });

  it("honors custom glyphs / flavor / lang options", () => {
    const style = createProtomapsStyle({
      url: "pmtiles:///x.pmtiles",
      glyphs: "https://fonts.example/{fontstack}/{range}.pbf",
      flavor: "dark",
      lang: "en",
    });
    expect(style.glyphs).toBe("https://fonts.example/{fontstack}/{range}.pbf");
    // layers are built from the flavor — spot-check that fill layers exist
    expect(style.layers.some((l) => l.type === "fill")).toBe(true);
  });
});
