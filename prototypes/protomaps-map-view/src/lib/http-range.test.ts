import { describe, expect, it } from "vitest";
import { parseRange } from "./http-range.ts";

describe("parseRange", () => {
  const SIZE = 1000;

  it("parses a normal start-end range", () => {
    expect(parseRange("bytes=0-99", SIZE)).toEqual({ status: "ok", start: 0, end: 99 });
  });

  it("clamps an open-ended range to the file end", () => {
    expect(parseRange("bytes=900-", SIZE)).toEqual({ status: "ok", start: 900, end: 999 });
  });

  it("parses a suffix range (last N bytes)", () => {
    expect(parseRange("bytes=-100", SIZE)).toEqual({ status: "ok", start: 900, end: 999 });
  });

  it("clamps an end beyond the file size", () => {
    expect(parseRange("bytes=0-9999", SIZE)).toEqual({ status: "ok", start: 0, end: 999 });
  });

  it("marks start beyond the file as unsatisfiable", () => {
    expect(parseRange("bytes=1000-", SIZE)).toEqual({ status: "unsatisfiable" });
    expect(parseRange("bytes=5000-6000", SIZE)).toEqual({ status: "unsatisfiable" });
  });

  it("returns ignore for missing / malformed / multi-range headers", () => {
    expect(parseRange(undefined, SIZE)).toEqual({ status: "ignore" });
    expect(parseRange("", SIZE)).toEqual({ status: "ignore" });
    expect(parseRange("bytes=abc", SIZE)).toEqual({ status: "ignore" });
    expect(parseRange("bytes=0-99,200-299", SIZE)).toEqual({ status: "ignore" });
    expect(parseRange("items=0-99", SIZE)).toEqual({ status: "ignore" });
  });
});
