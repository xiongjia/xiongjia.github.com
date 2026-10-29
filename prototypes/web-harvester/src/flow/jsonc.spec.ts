import { describe, expect, it } from "vitest";
import { parseJsonc, stripJsonComments, stripTrailingCommas } from "./jsonc";

describe("stripJsonComments", () => {
  it("removes line and block comments", () => {
    const text = `{
      // leading
      "a": 1, /* trailing */
      "b": 2
    }`;
    expect(JSON.parse(stripJsonComments(text))).toEqual({ a: 1, b: 2 });
  });

  it("keeps comment-like text inside strings", () => {
    const text = `{ "url": "https://example.test/a//b", "glob": "/*not-a-comment*/" }`;
    expect(JSON.parse(stripJsonComments(text))).toEqual({
      url: "https://example.test/a//b",
      glob: "/*not-a-comment*/",
    });
  });

  it("handles escaped quotes without losing the string state", () => {
    const text = `{ "a": "say \\"// hi\\"", "b": 1 } // done`;
    expect(JSON.parse(stripJsonComments(text))).toEqual({
      a: 'say "// hi"',
      b: 1,
    });
  });

  it("keeps offsets and newlines so a parse error still points at the right spot", () => {
    const text = '{\n  // note\n  "a":\n}';
    const stripped = stripJsonComments(text);

    expect(stripped).toHaveLength(text.length);
    expect(stripped.indexOf("}")).toBe(text.indexOf("}"));
    expect(stripped.split("\n")).toHaveLength(text.split("\n").length);
  });

  it("leaves a document without comments untouched", () => {
    const text = '{"a":1}\n';
    expect(stripJsonComments(text)).toBe(text);
  });
});

describe("stripTrailingCommas", () => {
  it("drops trailing commas, which JSONC allows and JSON.parse rejects", () => {
    const text = '{\n  "a": [1, 2,],\n  "b": 1,\n}';
    expect(JSON.parse(stripTrailingCommas(text))).toEqual({ a: [1, 2], b: 1 });
  });

  it("leaves commas inside strings alone", () => {
    expect(JSON.parse(stripTrailingCommas('{"a": "x,}"}'))).toEqual({
      a: "x,}",
    });
  });
});

describe("parseJsonc", () => {
  it("accepts comments and trailing commas together", () => {
    expect(parseJsonc('{\n  // note\n  "a": 1,\n}')).toEqual({ a: 1 });
  });

  it("names the source in the error", () => {
    expect(() => parseJsonc("{", "flows/broken.jsonc")).toThrow(
      /^flows\/broken\.jsonc is not valid JSON/,
    );
  });
});
