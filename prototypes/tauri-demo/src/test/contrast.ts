/**
 * Minimal colour maths for the palette test.
 *
 * The chart palette lives in `src/index.css` as `oklch()` custom properties, so
 * the guard that keeps them readable has to convert oklch → linear sRGB and
 * compute WCAG contrast. Implemented here (rather than pulling a colour library)
 * because it is ~40 lines of well-defined maths. The matrices are Björn
 * Ottosson's oklab reference implementation.
 */

/** Clamps a channel into the sRGB gamut. */
function clamp(channel: number): number {
  return Math.min(1, Math.max(0, channel));
}

export interface Oklch {
  /** Lightness, 0–1. */
  l: number;
  /** Chroma, 0–0.4 (100% = 0.4). */
  c: number;
  /** Hue angle in degrees. */
  h: number;
}

/** Reads a CSS number, expanding `%` against the scale the spec defines. */
function toNumber(raw: string, percentScale: number): number {
  return raw.endsWith("%") ? (Number(raw.slice(0, -1)) / 100) * percentScale : Number(raw);
}

/** Parses `oklch(L C H)`, accepting `%` for L and C. */
export function parseOklch(value: string): Oklch {
  const match = /^oklch\(\s*([\d.]+%?)\s+([\d.]+%?)\s+([\d.]+)(?:deg)?\s*\)$/.exec(value.trim());
  if (!match) {
    throw new Error(`not an oklch() colour: ${value}`);
  }
  return {
    l: toNumber(match[1], 1),
    c: toNumber(match[2], 0.4),
    h: Number(match[3]),
  };
}

/** WCAG relative luminance (linear sRGB) of an oklch colour, gamut-clamped. */
export function relativeLuminance(color: Oklch): number {
  const hue = (color.h * Math.PI) / 180;
  const a = color.c * Math.cos(hue);
  const b = color.c * Math.sin(hue);

  // oklab → LMS'
  const lPrime = color.l + 0.3963377774 * a + 0.2158037573 * b;
  const mPrime = color.l - 0.1055613458 * a - 0.0638541728 * b;
  const sPrime = color.l - 0.0894841775 * a - 1.291485548 * b;

  // LMS' → LMS
  const l = lPrime ** 3;
  const m = mPrime ** 3;
  const s = sPrime ** 3;

  // LMS → linear sRGB, clamped into gamut
  const red = clamp(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s);
  const green = clamp(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s);
  const blue = clamp(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s);

  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

/** WCAG contrast ratio between two colours (1–21). */
export function contrastRatio(a: Oklch, b: Oklch): number {
  const first = relativeLuminance(a);
  const second = relativeLuminance(b);
  const lighter = Math.max(first, second);
  const darker = Math.min(first, second);
  return (lighter + 0.05) / (darker + 0.05);
}
