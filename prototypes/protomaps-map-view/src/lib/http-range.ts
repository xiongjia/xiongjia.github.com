export interface ByteRange {
  start: number;
  end: number;
}

export type ParseRangeResult =
  { status: "ok"; start: number; end: number } | { status: "unsatisfiable" } | { status: "ignore" };

/**
 * Parse a single-range HTTP `Range: bytes=start-end` header against a known
 * file size. Returns:
 * - `ok` — a satisfiable single range (caller replies 206)
 * - `unsatisfiable` — start beyond the file end (caller replies 416)
 * - `ignore` — missing/empty/unparseable or multi-range header; per RFC 7233 a
 *   server may ignore the Range header and return the full 200 response
 */
export function parseRange(range: string | undefined, size: number): ParseRangeResult {
  if (!range) return { status: "ignore" };
  const m = /^bytes=(\d*)-(\d*)$/.exec(range);
  if (!m) return { status: "ignore" };

  const total = size;
  let start = m[1] === "" ? -1 : Number(m[1]);
  let end = m[2] === "" ? -1 : Number(m[2]);

  if (start === -1) {
    // Suffix range: last N bytes (`bytes=-500`).
    const length = end === -1 ? total : end;
    start = Math.max(total - length, 0);
    end = total - 1;
  } else {
    if (end === -1) end = total - 1;
    end = Math.min(end, total - 1);
  }

  if (start > end || start >= total) {
    return { status: "unsatisfiable" };
  }
  return { status: "ok", start, end };
}
