import { describe, expect, it } from "vitest";

import { formatBytes, formatClock, formatPercent, formatUptime } from "@/lib/format";

describe("formatBytes", () => {
  it("returns 0 B for non-positive and sub-byte input", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(-5)).toBe("0 B");
    expect(formatBytes(0.5)).toBe("0 B");
  });

  it("returns 0 B for input that is not a finite number", () => {
    expect(formatBytes(Number.NaN)).toBe("0 B");
    expect(formatBytes(Number.POSITIVE_INFINITY)).toBe("0 B");
  });

  it("rounds whole bytes and keeps one decimal from KiB upwards", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1.5)).toBe("2 B");
    expect(formatBytes(1024)).toBe("1.0 KiB");
    expect(formatBytes(1.5 * 1024 ** 2)).toBe("1.5 MiB");
    expect(formatBytes(16 * 1024 ** 3)).toBe("16.0 GiB");
  });

  it("stops at the largest known unit", () => {
    expect(formatBytes(1024 ** 6)).toBe("1024.0 PiB");
  });
});

describe("formatPercent", () => {
  it("rounds to whole numbers by default", () => {
    expect(formatPercent(41.6)).toBe("42%");
    expect(formatPercent(41.64, 1)).toBe("41.6%");
  });
});

describe("formatUptime", () => {
  it("drops leading zero units but always keeps minutes", () => {
    expect(formatUptime(90)).toBe("1m");
    expect(formatUptime(3 * 3600 + 5 * 60)).toBe("3h 5m");
    expect(formatUptime(2 * 86400 + 3 * 3600 + 4 * 60)).toBe("2d 3h 4m");
  });

  it("clamps negative and non-finite input to zero", () => {
    expect(formatUptime(-90)).toBe("0m");
    expect(formatUptime(Number.NaN)).toBe("0m");
  });
});

describe("formatClock", () => {
  it("renders mm:ss with zero padding", () => {
    const timestamp = new Date(2026, 0, 1, 10, 3, 7).getTime();
    expect(formatClock(timestamp)).toBe("03:07");
  });
});
