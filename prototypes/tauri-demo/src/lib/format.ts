/** Formatting helpers shared by the dashboard cards and charts. */

const BYTE_UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];

/**
 * Human readable byte size, e.g. `1.4 GiB`.
 *
 * Values below one byte (and non-positive input) render as `0 B`. Whole bytes
 * are rounded to integers — `fractionDigits` only applies from KiB upwards,
 * since a fractional byte is meaningless.
 */
export function formatBytes(bytes: number, fractionDigits = 1): string {
  if (!Number.isFinite(bytes) || bytes < 1) {
    return "0 B";
  }
  const exponent = Math.max(
    0,
    Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), BYTE_UNITS.length - 1),
  );
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(exponent === 0 ? 0 : fractionDigits)} ${BYTE_UNITS[exponent]}`;
}

export function formatPercent(value: number, digits = 0): string {
  return `${value.toFixed(digits)}%`;
}

/**
 * Uptime as `3d 4h 5m`, dropping the leading zero units.
 *
 * Negative input clamps to `0m` so a clock skew cannot render `-1m`.
 */
export function formatUptime(seconds: number): string {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  const days = Math.floor(safeSeconds / 86_400);
  const hours = Math.floor((safeSeconds % 86_400) / 3_600);
  const minutes = Math.floor((safeSeconds % 3_600) / 60);
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (days > 0 || hours > 0) parts.push(`${hours}h`);
  parts.push(`${minutes}m`);
  return parts.join(" ");
}

/** `mm:ss` clock label for the chart X axis. */
export function formatClock(timestampMs: number): string {
  const date = new Date(timestampMs);
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${minutes}:${seconds}`;
}
