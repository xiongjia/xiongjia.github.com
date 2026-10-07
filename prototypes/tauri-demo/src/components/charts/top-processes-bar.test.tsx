import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TopProcessesBar } from "@/components/charts/top-processes-bar";
import { snapshotFixture } from "@/test/fixtures";
import { barRectangleCount } from "@/test/recharts";

describe("TopProcessesBar", () => {
  it("renders one bar per process", () => {
    const { container } = render(<TopProcessesBar processes={snapshotFixture.topProcesses} />);

    expect(barRectangleCount(container)).toBe(snapshotFixture.topProcesses.length);
    expect(screen.getByText("3 processes, sorted by resident memory")).toBeTruthy();
    // The label shows up both on the Y axis and in the (screen-reader) legend.
    expect(screen.getAllByText("tauri-demo").length).toBeGreaterThan(0);
  });

  it("truncates long process names", () => {
    render(
      <TopProcessesBar
        processes={[{ pid: 1, name: "a-very-long-process-name-here", memory: 1024 }]}
      />,
    );

    expect(screen.getAllByText("a-very-long-proce…").length).toBeGreaterThan(0);
  });

  it("disambiguates names that collide after truncation", () => {
    render(
      <TopProcessesBar
        processes={[
          { pid: 1204, name: "Google Chrome Helper", memory: 1024 },
          { pid: 1205, name: "Google Chrome Helper", memory: 512 },
        ]}
      />,
    );

    expect(screen.getAllByText("Google Chrome Hel… #1204").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Google Chrome Hel… #1205").length).toBeGreaterThan(0);
  });

  it("never emits a lone surrogate when truncating", () => {
    render(<TopProcessesBar processes={[{ pid: 7, name: "🚀".repeat(30), memory: 1024 }]} />);

    // A code-unit slice would cut the surrogate pair and leave a lone half.
    const loneSurrogate = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?:[^\uD800-\uDBFF]|^)[\uDC00-\uDFFF]/;
    const labels = screen.getAllByText(/🚀/).map((element) => element.textContent ?? "");
    expect(labels.length).toBeGreaterThan(0);
    expect(labels.some((label) => loneSurrogate.test(label))).toBe(false);
    expect(screen.getAllByText("🚀".repeat(17) + "…").length).toBeGreaterThan(0);
  });

  it("shows a placeholder while no process data arrived", () => {
    render(<TopProcessesBar processes={[]} />);

    expect(screen.getByText("Waiting for data")).toBeTruthy();
  });
});
