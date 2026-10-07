import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSystemStats } from "@/hooks/use-system-stats";
import { fetchHistory, fetchSnapshot, type Snapshot } from "@/lib/ipc";
import { historyFixture, snapshotFixture } from "@/test/fixtures";

vi.mock("@/lib/ipc", () => ({
  isDesktopApp: () => false,
  fetchSnapshot: vi.fn(),
  fetchHistory: vi.fn(),
}));

/** Lets the pending promise callbacks run without advancing the clock. */
async function flush() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("useSystemStats", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(fetchSnapshot).mockResolvedValue(snapshotFixture);
    vi.mocked(fetchHistory).mockResolvedValue(historyFixture);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches a snapshot and the history on mount", async () => {
    const { result } = renderHook(() => useSystemStats());
    await flush();

    expect(result.current.snapshot).toEqual(snapshotFixture);
    expect(result.current.history).toEqual(historyFixture);
    expect(result.current.error).toBeNull();
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
  });

  it("polls again after each interval", async () => {
    renderHook(() => useSystemStats());
    await flush();
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);

    await advance(2_000);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);

    await advance(2_000);
    expect(fetchSnapshot).toHaveBeenCalledTimes(3);
  });

  it("skips ticks while a request is still in flight", async () => {
    let resolveSnapshot!: (snapshot: Snapshot) => void;
    vi.mocked(fetchSnapshot).mockReturnValue(
      new Promise<Snapshot>((resolve) => {
        resolveSnapshot = resolve;
      }),
    );

    const { result } = renderHook(() => useSystemStats());
    await flush();
    await advance(4_000);

    // Two interval ticks came and went without queueing extra requests.
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);

    resolveSnapshot(snapshotFixture);
    await flush();
    expect(result.current.snapshot).toEqual(snapshotFixture);

    await advance(2_000);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
  });

  it("abandons a request that never settles and retries later", async () => {
    vi.mocked(fetchSnapshot).mockReturnValue(new Promise<Snapshot>(() => {}));

    const { result } = renderHook(() => useSystemStats());
    await flush();
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);

    // The 10s request timeout fires, surfaces an error and frees the guard.
    await advance(10_000);
    expect(result.current.error).toContain("No response from the metrics backend");

    // The next interval tick is allowed through again.
    await advance(2_000);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
  });

  it("ignores a late result from an abandoned request", async () => {
    let resolveStale!: (snapshot: Snapshot) => void;
    vi.mocked(fetchSnapshot)
      .mockReturnValueOnce(
        new Promise<Snapshot>((resolve) => {
          resolveStale = resolve;
        }),
      )
      // Later attempts stay pending too, so only the stale resolve can paint.
      .mockReturnValue(new Promise<Snapshot>(() => {}));

    const { result } = renderHook(() => useSystemStats());
    await flush();
    await advance(10_000);
    expect(result.current.error).toContain("No response from the metrics backend");

    resolveStale({ ...snapshotFixture, cpuUsage: 99 });
    await flush();

    expect(result.current.snapshot).toBeNull();
  });

  it("scales the request timeout above a long poll interval", async () => {
    vi.mocked(fetchSnapshot).mockReturnValue(new Promise<Snapshot>(() => {}));

    const { result } = renderHook(() => useSystemStats(30_000));
    await flush();

    // interval * 2 = 60s, so 59s is still a live request, not a timeout.
    await advance(59_000);
    expect(result.current.error).toBeNull();

    await advance(1_000);
    expect(result.current.error).toContain("after 60s");
  });

  it("clears the pending request timeout on unmount", async () => {
    vi.mocked(fetchSnapshot).mockReturnValue(new Promise<Snapshot>(() => {}));

    const { unmount } = renderHook(() => useSystemStats());
    await flush();
    expect(vi.getTimerCount()).toBeGreaterThan(0);

    unmount();

    // Neither the poll interval nor the request timeout outlives the hook.
    expect(vi.getTimerCount()).toBe(0);
  });

  it("clamps a too-small poll interval instead of busy-polling", async () => {
    renderHook(() => useSystemStats(0));
    await flush();
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);

    // 250ms is the floor, so a 0ms interval must not fire before then.
    await advance(249);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);

    await advance(1);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
  });

  it("falls back to the default interval for nonsensical input", async () => {
    renderHook(() => useSystemStats(Number.NaN));
    await flush();
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);

    // NaN would reach setInterval as 0; the default interval must win instead.
    await advance(1_999);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);

    await advance(1);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
  });

  it("surfaces an Error message", async () => {
    vi.mocked(fetchSnapshot).mockRejectedValue(new Error("ipc down"));
    const { result } = renderHook(() => useSystemStats());
    await flush();

    expect(result.current.error).toBe("ipc down");
  });

  it("stringifies non-Error rejections", async () => {
    vi.mocked(fetchSnapshot).mockRejectedValue("boom");
    const { result } = renderHook(() => useSystemStats());
    await flush();

    expect(result.current.error).toBe("boom");
  });

  it("stops polling once unmounted", async () => {
    const { unmount } = renderHook(() => useSystemStats());
    await flush();
    const callsBeforeUnmount = vi.mocked(fetchSnapshot).mock.calls.length;

    unmount();
    await advance(6_000);

    expect(fetchSnapshot).toHaveBeenCalledTimes(callsBeforeUnmount);
  });
});
