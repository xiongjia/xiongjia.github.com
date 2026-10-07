import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";

/**
 * Smoke test over the browser mock: the app boots, the header appears, the KPI
 * cards fill in and the first chart paints. The per-component behaviour is
 * covered by the more focused test files.
 *
 * Fake timers keep the 2s polling interval from firing (and mutating state
 * outside `act`) on a slow machine.
 */
describe("App", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the dashboard from the browser mock", async () => {
    const { container } = render(<App />);

    expect(screen.getByText("Tauri Demo")).toBeTruthy();
    expect(screen.getByTestId("runtime-badge").textContent).toBe("Browser mock");
    // Nothing is timestamped until the first snapshot lands.
    expect(screen.queryByTestId("last-updated")).toBeNull();
    // The first snapshot resolves after mount, so the cards start as skeletons.
    expect(screen.getByTestId("stat-cards-loading")).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.queryByTestId("stat-cards-loading")).toBeNull();
    expect(screen.getByTestId("stat-cpu-value").textContent).toMatch(/%$/);
    expect(screen.getByTestId("last-updated").textContent).toMatch(/^updated /);
    expect(container.querySelectorAll(".recharts-surface").length).toBeGreaterThan(0);
    expect(screen.getByTestId("cores-grid")).toBeTruthy();
    expect(screen.queryByTestId("stats-error")).toBeNull();
  });
});
