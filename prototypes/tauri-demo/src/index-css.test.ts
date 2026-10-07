import { globSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { contrastRatio, parseOklch, relativeLuminance } from "@/test/contrast";
import { parseCssBlock } from "@/test/css";

// Resolved relative to this file, so the suite does not care about the cwd.
// (`?raw` imports come back empty for `.css` here — the Tailwind plugin owns
// those ids — and Vite rewrites `new URL(..., import.meta.url)`.)
const sourceDirectory = import.meta.dirname;
const css = readFileSync(join(sourceDirectory, "index.css"), "utf8");

const CHART_TOKENS = ["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5"];
/** WCAG 1.4.11: graphics that carry meaning need at least 3:1. */
const MIN_CONTRAST = 3;

/**
 * Every hand-written component that paints with the palette; `components/ui/**`
 * is shadcn-generated and test files carry example strings (e.g. `#1204`), so
 * both are kept out of the scan.
 */
const PALETTE_CONSUMERS = globSync("components/**/*.tsx", { cwd: sourceDirectory })
  .filter((file) => !file.startsWith("components/ui/") && !file.includes(".test."))
  .toSorted();

/** Colour notations that would bypass the theme tokens. */
const COLOUR_LITERALS = [
  { name: "hex colour", pattern: /#[0-9a-fA-F]{3,8}\b/ },
  { name: "colour function", pattern: /\b(?:rgb|rgba|hsl|hsla|oklch|oklab|lch|lab)\(/ },
  {
    name: "Tailwind palette utility",
    pattern:
      /\b(?:bg|text|border|stroke|fill|from|to|via)-(?:slate|gray|grey|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/,
  },
  {
    // Covers JSX attributes (`stroke="red"`) and object literals
    // (`style={{ color: "red" }}`).
    name: "named colour",
    pattern:
      /\b(?:stroke|fill|color|background|backgroundColor)\s*[:=]\s*["'{]?\s*["']?(?:red|green|blue|black|white|gray|grey|orange|purple|pink|yellow|cyan|magenta)\b/,
  },
];

/**
 * The chart palette is the one thing the component tests cannot see: they count
 * SVG elements and paths, never colours. This guard keeps every `--chart-N`
 * readable on the surface it is drawn on — the shadcn preset shipped the same
 * grayscale ramp for both themes, which made the CPU line 1.48:1 on white.
 */
const THEMES = [
  { name: ":root (light)", block: parseCssBlock(css, ":root") },
  { name: ".dark", block: parseCssBlock(css, ".dark") },
];

describe("index.css chart palette", () => {
  it.each(THEMES)("$name keeps every chart colour above 3:1", ({ block }) => {
    const background = parseOklch(block.get("--background") ?? "");
    const card = parseOklch(block.get("--card") ?? "");

    for (const token of CHART_TOKENS) {
      const color = parseOklch(block.get(token) ?? "");
      for (const surface of [background, card]) {
        expect(contrastRatio(color, surface), token).toBeGreaterThanOrEqual(MIN_CONTRAST);
      }
    }
  });

  it("uses a different palette per theme", () => {
    const light = CHART_TOKENS.map((token) => THEMES[0].block.get(token));
    const dark = CHART_TOKENS.map((token) => THEMES[1].block.get(token));

    expect(light).not.toEqual(dark);
  });
});

describe("chart components", () => {
  it("scans every hand-written component", () => {
    // Guards the glob itself: an empty or drifting match set would silently
    // disable the scans below.
    expect(PALETTE_CONSUMERS).toContain("components/charts/cpu-memory-line.tsx");
    expect(PALETTE_CONSUMERS).toContain("components/cores-grid.tsx");
  });

  it.each(PALETTE_CONSUMERS)("%s paints with palette tokens, not literals", (file) => {
    const source = readFileSync(join(sourceDirectory, file), "utf8");

    for (const { name, pattern } of COLOUR_LITERALS) {
      // A tripwire, not a proof: it catches the literal notations we use, so a
      // series that stops following the theme fails here rather than in a
      // screenshot. It also does not reason about context, so prose or a string
      // that merely looks like a colour (e.g. `background: "white"`, or
      // `"red-ish"` because `\b` matches before the hyphen) will trip it —
      // rename or reword rather than weakening the pattern.
      expect(source, name).not.toMatch(pattern);
    }
  });
});

describe("contrast helpers", () => {
  it("matches the sRGB values the browser reports", () => {
    // Chrome renders oklch(0.87 0 0) as rgb(212, 212, 212) → 0.6575 relative
    // luminance on the linear scale.
    expect(relativeLuminance(parseOklch("oklch(0.87 0 0)"))).toBeCloseTo(0.658, 2);
    expect(relativeLuminance(parseOklch("oklch(1 0 0)"))).toBeCloseTo(1, 5);
    expect(contrastRatio(parseOklch("oklch(1 0 0)"), parseOklch("oklch(0 0 0)"))).toBeCloseTo(21, 1);
    // The value the browser probe reports for chart-1 on the dark background.
    expect(contrastRatio(parseOklch("oklch(0.87 0 0)"), parseOklch("oklch(0.145 0 0)"))).toBeCloseTo(
      13.36,
      1,
    );
  });

  it("rejects anything that is not oklch()", () => {
    expect(() => parseOklch("#fff")).toThrow(/not an oklch/);
    expect(() => parseOklch("")).toThrow(/not an oklch/);
  });
});
