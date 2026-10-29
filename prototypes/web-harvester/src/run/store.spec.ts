import type { ConfigService } from "@nestjs/config";
import {
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { RunRecord } from "./run";
import { RunStore } from "./store";

function makeConfig(values: Record<string, unknown> = {}): ConfigService {
  return { get: (key: string) => values[key] } as unknown as ConfigService;
}

const meta = {
  url: "",
  userAgent: "",
  usedSelectors: {},
  screenshots: {},
  steps: [],
};

describe("RunStore", () => {
  let dir: string;
  let store: RunStore;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "harvester-runs-"));
    store = new RunStore(
      makeConfig({ HARVEST_RUNS_DIR: dir, HARVEST_RUN_KEEP: 5 }),
    );
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  async function create(id: string, extra: Partial<RunRecord> = {}) {
    return store.create({
      id,
      flow: "demo-visit",
      profile: "main",
      state: "queued",
      input: {},
      ...extra,
    });
  }

  it("writes run.json with a fresh lifecycle", async () => {
    const record = await create("20260101T000000000Z-aaaaaa");

    expect(record).toMatchObject({
      state: "queued",
      startedAt: null,
      finishedAt: null,
      error: null,
      meta: null,
    });
    const raw = await readFile(join(dir, record.id, "run.json"), "utf8");
    expect(JSON.parse(raw)).toMatchObject({
      id: record.id,
      flow: "demo-visit",
    });
  });

  it("patches a record and serves it from cache", async () => {
    const record = await create("20260101T000000000Z-aaaaaa");
    await store.update(record.id, {
      state: "running",
      startedAt: "2026-01-01T00:00:01.000Z",
    });

    const loaded = await store.get(record.id);
    expect(loaded?.state).toBe("running");
    expect(loaded?.startedAt).toBe("2026-01-01T00:00:01.000Z");

    const fresh = new RunStore(makeConfig({ HARVEST_RUNS_DIR: dir }));
    expect((await fresh.get(record.id))?.state).toBe("running");
  });

  it("lists newest first and filters", async () => {
    await create("20260101T000000000Z-aaaaaa");
    await create("20260102T000000000Z-bbbbbb", { flow: "xhs-following" });
    const running = await create("20260103T000000000Z-cccccc");
    await store.update(running.id, { state: "running" });

    expect((await store.list()).map((run) => run.id)).toEqual([
      "20260103T000000000Z-cccccc",
      "20260102T000000000Z-bbbbbb",
      "20260101T000000000Z-aaaaaa",
    ]);
    expect(await store.list({ flow: "xhs-following" })).toHaveLength(1);
    expect(await store.list({ state: ["running"] })).toHaveLength(1);
    expect(await store.list({ profile: "other" })).toHaveLength(0);
    expect(await store.list({ limit: 1 })).toHaveLength(1);
  });

  it("round-trips the output JSON", async () => {
    const record = await create("20260101T000000000Z-aaaaaa");
    expect(await store.readOutput(record.id)).toBeNull();

    await store.writeOutput(record.id, { heading: "hi", rows: [{ a: 1 }] });
    expect(await store.readOutput(record.id)).toEqual({
      heading: "hi",
      rows: [{ a: 1 }],
    });
  });

  it("prunes old finished runs but never an active one", async () => {
    for (let index = 0; index < 8; index += 1) {
      const record = await create(
        `2026010${index + 1}T000000000Z-aaaaa${index}`,
      );
      await store.update(record.id, {
        state: "succeeded",
        finishedAt: "2026-01-01T00:00:00.000Z",
        meta,
      });
    }
    const active = await create("20260109T000000000Z-ffffff");
    await store.update(active.id, { state: "running" });

    const removed = await store.prune();

    expect(removed).toHaveLength(3);
    const left = await readdir(dir);
    expect(left).toContain(active.id);
    expect(left).not.toContain("20260101T000000000Z-aaaaa0");
    expect(left).toHaveLength(6);
  });

  it("refuses ids that are not safe file names", async () => {
    expect(() => store.runDir("../escape")).toThrow(/is not a run id/);
    expect(() => store.runDir(".hidden")).toThrow(/is not a run id/);
    expect(await store.get("../escape")).toBeNull();
  });

  it("resolves artifact names but never leaves the run directory", async () => {
    const id = "20260101T000000000Z-aaaaaa";
    await store.create({
      id,
      flow: "demo-visit",
      profile: "main",
      state: "succeeded",
      input: {},
    });

    expect(store.artifactPath(id, "visit.png")).toBe(
      join(dir, id, "artifacts", "visit.png"),
    );
    expect(store.artifactPath(id, "../run.json")).toBeNull();
    expect(store.artifactPath(id, ".hidden")).toBeNull();
    expect(store.artifactPath(id, "nested/visit.png")).toBeNull();
  });

  it("lists a run's artifacts", async () => {
    const id = "20260101T000000000Z-aaaaaa";
    await store.create({
      id,
      flow: "demo-visit",
      profile: "main",
      state: "succeeded",
      input: {},
    });

    expect(await store.listArtifacts(id)).toEqual([]);

    const file = store.artifactPath(id, "visit.png");
    expect(file).toBeTruthy();
    await mkdir(join(dir, id, "artifacts"), { recursive: true });
    await writeFile(file as string, "png");

    expect(await store.listArtifacts(id)).toEqual(["visit.png"]);
  });

  it("ignores a corrupt run.json instead of crashing the listing", async () => {
    const id = "20260101T000000000Z-aaaaaa";
    await store.create({
      id,
      flow: "demo-visit",
      profile: "main",
      state: "queued",
      input: {},
    });
    await writeFile(join(dir, id, "run.json"), "{ not json");

    const fresh = new RunStore(makeConfig({ HARVEST_RUNS_DIR: dir }));
    expect(await fresh.get(id)).toBeNull();
    expect(await fresh.list()).toEqual([]);
  });
});
