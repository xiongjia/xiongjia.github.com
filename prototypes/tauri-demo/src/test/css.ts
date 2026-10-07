/**
 * Tiny CSS readers for the palette tests.
 *
 * Kept separate from `contrast.ts` (colour maths) so each module does one thing.
 */

/** Collects the `--custom-property` declarations of one CSS rule block. */
export function parseCssBlock(css: string, selector: string): Map<string, string> {
  const selectorIndex = css.indexOf(`${selector} {`);
  if (selectorIndex === -1) {
    throw new Error(`CSS selector not found: ${selector}`);
  }
  const open = css.indexOf("{", selectorIndex);
  const close = css.indexOf("}", open);
  const body = css.slice(open + 1, close);

  const properties = new Map<string, string>();
  for (const line of body.split("\n")) {
    const match = /^\s*(--[\w-]+):\s*([^;]+);/.exec(line);
    if (match) {
      properties.set(match[1], match[2].trim());
    }
  }
  return properties;
}
