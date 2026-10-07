import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CpuMemoryLine } from "@/components/charts/cpu-memory-line";
import { historyFixture } from "@/test/fixtures";
import { chartSurfaceCount, lineCurvePaths } from "@/test/recharts";

/** Command letters in an SVG path (`M`/`L`/`C`) approximate the point count. */
function pathCommands(path: Element | null): number {
  const d = path?.getAttribute("d") ?? "";
  return (d.match(/[MLC]/g) ?? []).length;
}

describe("CpuMemoryLine", () => {
  it("draws one line per series with real geometry", () => {
    const { container } = render(<CpuMemoryLine history={historyFixture} />);

    expect(chartSurfaceCount(container)).toBe(1);

    const curves = lineCurvePaths(container);
    expect(curves).toHaveLength(2);
    for (const curve of curves) {
      expect(pathCommands(curve)).toBeGreaterThanOrEqual(historyFixture.length);
    }

    expect(screen.getByText("CPU")).toBeTruthy();
    expect(screen.getByText("Memory")).toBeTruthy();
  });

  it("reports how full the history window is", () => {
    render(<CpuMemoryLine history={historyFixture} capacity={60} />);

    expect(screen.getByText("Last 3 of 60 samples, one every 2 seconds")).toBeTruthy();
  });

  it("still renders with an empty history", () => {
    const { container } = render(<CpuMemoryLine history={[]} />);

    expect(chartSurfaceCount(container)).toBe(1);
    expect(container.textContent).toContain("Last 0 samples");
  });
});
