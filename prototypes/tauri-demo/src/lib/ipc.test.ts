import { describe, expect, it } from "vitest";

import { fetchHistory, fetchSnapshot, isDesktopApp } from "@/lib/ipc";

describe("browser mock", () => {
  it("is used when there is no Tauri runtime (jsdom)", () => {
    expect(isDesktopApp()).toBe(false);
  });

  it("returns a snapshot shaped like the Rust struct", async () => {
    const snapshot = await fetchSnapshot();

    expect(snapshot.cpuUsage).toBeGreaterThanOrEqual(0);
    expect(snapshot.cpuUsage).toBeLessThanOrEqual(100);
    expect(snapshot.cores.length).toBeGreaterThan(0);
    expect(snapshot.memoryUsed).toBeGreaterThan(0);
    expect(snapshot.memoryTotal).toBeGreaterThan(snapshot.memoryUsed);
    expect(snapshot.swapUsed).toBeGreaterThanOrEqual(0);
    expect(snapshot.disks.length).toBeGreaterThan(0);
    expect(snapshot.disks[0]).toMatchObject({
      name: expect.any(String),
      mountPoint: expect.any(String),
      total: expect.any(Number),
      available: expect.any(Number),
      used: expect.any(Number),
    });
    expect(snapshot.topProcesses.length).toBeGreaterThan(0);
    expect(snapshot.topProcesses[0]).toMatchObject({
      pid: expect.any(Number),
      name: expect.any(String),
      memory: expect.any(Number),
    });
    expect(snapshot.uptimeSecs).toBeGreaterThan(0);
    expect(snapshot.timestampMs).toBeGreaterThan(0);
    expect(snapshot.historyCapacity).toBeGreaterThan(0);
  });

  it("hands out copies, so callers cannot mutate the fixtures", async () => {
    const first = await fetchSnapshot();
    first.topProcesses[0].name = "mutated";
    first.disks[0].name = "mutated";

    const second = await fetchSnapshot();
    expect(second.topProcesses[0].name).not.toBe("mutated");
    expect(second.disks[0].name).not.toBe("mutated");
  });

  it("appends one history point per snapshot, capped at the reported capacity", async () => {
    const capacity = (await fetchSnapshot()).historyCapacity;
    // The mock keeps a module-level buffer, so measure deltas instead of
    // assuming a fresh module.
    const before = (await fetchHistory()).length;

    await fetchSnapshot();
    expect(await fetchHistory()).toHaveLength(Math.min(before + 1, capacity));

    for (let index = 0; index < capacity + 20; index += 1) {
      await fetchSnapshot();
    }
    const capped = await fetchHistory();
    expect(capped).toHaveLength(capacity);
    // The oldest points are the ones that got dropped.
    expect(capped[capped.length - 1].timestampMs).toBeGreaterThanOrEqual(capped[0].timestampMs);
  });
});
