import type { ConfigService } from "@nestjs/config";
import { describe, expect, it, vi } from "vitest";
import { QueueFullError, RunQueue } from "./queue";

function makeQueue(depth = 8): RunQueue {
  return new RunQueue({
    get: (key: string) => (key === "HARVEST_QUEUE_DEPTH" ? depth : undefined),
  } as unknown as ConfigService);
}

/** A task that resolves when `release()` is called. */
function hold() {
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { gate, release };
}

describe("RunQueue", () => {
  it("runs tasks for one profile one at a time, in order", async () => {
    const queue = makeQueue();
    const order: string[] = [];
    const first = hold();

    const one = queue.submit("main", "run-1", async () => {
      order.push("start-1");
      await first.gate;
      order.push("end-1");
    });
    const two = queue.submit("main", "run-2", async () => {
      order.push("start-2");
    });

    await Promise.resolve();
    expect(order).toEqual(["start-1"]);
    expect(queue.snapshot("main")).toEqual({
      running: "run-1",
      queued: ["run-2"],
    });

    first.release();
    await Promise.all([one, two]);
    expect(order).toEqual(["start-1", "end-1", "start-2"]);
    expect(queue.snapshot("main")).toEqual({ running: null, queued: [] });
  });

  it("lets two profiles run in parallel", async () => {
    const queue = makeQueue();
    const a = hold();
    const b = hold();
    const started: string[] = [];

    const one = queue.submit("main", "run-1", async () => {
      started.push("main");
      await a.gate;
    });
    const two = queue.submit("second", "run-2", async () => {
      started.push("second");
      await b.gate;
    });

    await Promise.resolve();
    expect(started.sort()).toEqual(["main", "second"]);
    a.release();
    b.release();
    await Promise.all([one, two]);
  });

  it("refuses more work than the profile may hold", async () => {
    const queue = makeQueue(1);
    const gate = hold();
    const running = queue.submit("main", "run-1", () => gate.gate);

    expect(() => queue.submit("main", "run-2", async () => undefined)).toThrow(
      QueueFullError,
    );
    gate.release();
    await running;
    expect(queue.depth("main")).toBe(0);
  });

  it("keeps the chain alive after a failing task", async () => {
    const queue = makeQueue();
    const failing = queue.submit("main", "run-1", async () => {
      throw new Error("boom");
    });
    await expect(failing).rejects.toThrow("boom");

    const next = vi.fn(async () => undefined);
    await queue.submit("main", "run-2", next);
    expect(next).toHaveBeenCalled();
  });

  it("drops a run cancelled while it waits", async () => {
    const queue = makeQueue();
    const gate = hold();
    const running = queue.submit("main", "run-1", () => gate.gate);
    const queued = queue.submit("main", "run-2", async () => undefined);

    expect(queue.drop("main", "run-2")).toBe(true);
    expect(queue.drop("main", "run-2")).toBe(false);
    expect(queue.snapshot("main").queued).toEqual([]);

    gate.release();
    await Promise.all([running, queued]);
  });
});
