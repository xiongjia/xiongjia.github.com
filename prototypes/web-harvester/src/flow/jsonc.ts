/**
 * JSON with comments and trailing commas, for flow files.
 *
 * A flow is read by humans as much as by the host, and "why is this selector
 * first" belongs next to the selector. Instead of a second file format, flow
 * files are JSONC: `//` and `/* *\/` comments are stripped here, before
 * `JSON.parse`.
 *
 * Comments are replaced by spaces rather than deleted, so a `JSON.parse` error
 * still points at the original line and column. Strings are honoured, which is
 * the whole reason this is not a regex: `"https://example.test/a//b"` must not
 * lose its path.
 */
export function stripJsonComments(text: string): string {
  let out = "";
  let index = 0;
  let inString = false;
  let inLine = false;
  let inBlock = false;

  while (index < text.length) {
    const char = text[index];
    const next = text[index + 1];

    if (inLine) {
      if (char === "\n") {
        inLine = false;
        out += char;
      } else {
        out += " ";
      }
      index += 1;
      continue;
    }

    if (inBlock) {
      if (char === "*" && next === "/") {
        inBlock = false;
        out += "  ";
        index += 2;
        continue;
      }
      out += char === "\n" ? "\n" : " ";
      index += 1;
      continue;
    }

    if (inString) {
      out += char;
      if (char === "\\") {
        out += next ?? "";
        index += 2;
        continue;
      }
      if (char === '"') {
        inString = false;
      }
      index += 1;
      continue;
    }

    if (char === '"') {
      inString = true;
      out += char;
      index += 1;
      continue;
    }

    if (char === "/" && next === "/") {
      inLine = true;
      out += "  ";
      index += 2;
      continue;
    }

    if (char === "/" && next === "*") {
      inBlock = true;
      out += "  ";
      index += 2;
      continue;
    }

    out += char;
    index += 1;
  }

  return out;
}

/**
 * Drop a `,` that only precedes `}` or `]`.
 *
 * JSONC allows trailing commas (Prettier writes them), `JSON.parse` does not.
 * Strings are honoured here too, so `", "` inside a value is left alone.
 */
export function stripTrailingCommas(text: string): string {
  let out = "";
  let index = 0;
  let inString = false;

  while (index < text.length) {
    const char = text[index];

    if (inString) {
      out += char;
      if (char === "\\") {
        out += text[index + 1] ?? "";
        index += 2;
        continue;
      }
      if (char === '"') {
        inString = false;
      }
      index += 1;
      continue;
    }

    if (char === '"') {
      inString = true;
      out += char;
      index += 1;
      continue;
    }

    if (char === ",") {
      let ahead = index + 1;
      while (ahead < text.length && /\s/.test(text[ahead])) {
        ahead += 1;
      }
      if (text[ahead] === "}" || text[ahead] === "]") {
        out += " ";
        index += 1;
        continue;
      }
    }

    out += char;
    index += 1;
  }

  return out;
}

/** Parse JSONC; the error message keeps the source name and the position. */
export function parseJsonc(text: string, source = "flow"): unknown {
  try {
    return JSON.parse(stripTrailingCommas(stripJsonComments(text))) as unknown;
  } catch (error) {
    throw new Error(`${source} is not valid JSON${detail(error)}`, {
      cause: error,
    });
  }
}

function detail(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return `: ${message}`;
}
