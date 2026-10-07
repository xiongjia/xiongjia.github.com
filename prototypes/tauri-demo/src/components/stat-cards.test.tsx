import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatCards } from "@/components/stat-cards";
import { snapshotFixture } from "@/test/fixtures";

describe("StatCards", () => {
  it("shows skeletons while the first snapshot is pending", () => {
    render(<StatCards snapshot={null} />);

    expect(screen.getByTestId("stat-cards-loading")).toBeTruthy();
    expect(screen.queryByTestId("stat-cpu")).toBeNull();
  });

  it("renders one card per metric with a progress bar", () => {
    render(<StatCards snapshot={snapshotFixture} />);

    expect(screen.getByTestId("stat-cpu-value").textContent).toBe("42%");
    expect(screen.getByTestId("stat-cpu").textContent).toContain("2 cores");

    expect(screen.getByTestId("stat-memory-value").textContent).toBe("50%");
    expect(screen.getByTestId("stat-memory").textContent).toContain("8.0 GiB / 16.0 GiB");

    expect(screen.getByTestId("stat-disk-value").textContent).toBe("60%");
    expect(screen.getByTestId("stat-uptime-value").textContent).toBe("2d 3h 4m");
    expect(screen.getByTestId("stat-uptime").textContent).toContain("Swap 512.0 MiB / 2.0 GiB");

    const bar = screen.getByTestId("stat-cpu-bar");
    expect(bar.style.width).toBe("41.6%");
  });

  it("exposes the meters to assistive technology", () => {
    render(<StatCards snapshot={snapshotFixture} />);

    const cpuMeter = screen.getByRole("progressbar", { name: "CPU usage" });
    expect(cpuMeter.getAttribute("aria-valuenow")).toBe("42");
    expect(cpuMeter.getAttribute("aria-valuemin")).toBe("0");
    expect(cpuMeter.getAttribute("aria-valuemax")).toBe("100");

    // Uptime has no meter, the other three metrics do.
    expect(screen.getAllByRole("progressbar")).toHaveLength(3);
  });

  it("clamps progress bars into 0-100%", () => {
    render(<StatCards snapshot={{ ...snapshotFixture, cpuUsage: 140 }} />);

    expect(screen.getByTestId("stat-cpu-bar").style.width).toBe("100%");
    expect(screen.getByRole("progressbar", { name: "CPU usage" }).getAttribute("aria-valuenow")).toBe(
      "100",
    );
  });
});
