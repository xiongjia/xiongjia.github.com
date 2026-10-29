import { HttpException } from "@nestjs/common";
import type { ConfigService } from "@nestjs/config";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Page } from "playwright-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BrowserService } from "../browser/browser.service";
import { FlowLoader } from "../flow/loader";
import { ProfileRegistry } from "../profile/registry";
import { QueueFullError, RunQueue } from "../run/queue";
import { isTerminal } from "../run/run";
import { RunStore } from "../run/store";
import { FlowService } from "./flow.service";
import { BadRequestException, NotFoundException } from "@nestjs/common";

const UA = "Mozilla/5.0 (Macintosh) Firefox/156.0";

const DEMO_ELEMENTS: Record<string, string> = {
  "#title": "harvester demo page",
  "#delayed": "delayed-ready",
  "#status": "clicked",
  "#bump": "",
};

function makePage(elements: Record<string, string> = DEMO_ELEMENTS): Page {
  return {
    goto: vi.fn(async () => null),
    waitForTimeout: vi.fn(async () => undefined),
    url: () => "http://127.0.0.1:8765/api/v1/demo",
    keyboard: { press: vi.fn(async () => undefined) },
    screenshot: vi.fn(async ({ path }: { path: string }) => {
      const { writeFile } = await import("node:fs/promises");
      await writeFile(path, "png");
    }),
    locator: (selector: string) => {
      const present = selector in elements;
      const locator = {
        count: async () => (present ? 1 : 0),
        click: async () => {
          if (!present) throw new Error(`no element ${selector}`);
        },
        fill: async () => {
          if (!present) throw new Error(`no element ${selector}`);
        },
        press: async () => undefined,
        textContent: async () => (present ? elements[selector] : null),
        isVisible: async () => present,
        waitFor: async () => {
          if (!present) throw new Error("Timeout exceeded");
        },
        screenshot: async ({ path }: { path: string }) => {
          const { writeFile } = await import("node:fs/promises");
          await writeFile(path, "png");
        },
      };
      return { first: () => locator };
    },
    evaluate: vi.fn(async (fn: unknown, arg?: unknown) => {
      if (arg && typeof arg === "object" && "itemSelectors" in arg) {
        return [
          {
            text: "Stable, offline target used to verify the browser pipeline.",
          },
        ];
      }
      return String(fn).includes("innerText") ? "" : UA;
    }),
  } as unknown as Page;
}

function makeBrowser(page: Page | (() => Promise<Page>)): BrowserService {
  return {
    withPage: async <T>(fn: (page: Page) => Promise<T>): Promise<T> => {
      const resolved = typeof page === "function" ? await page() : page;
      return fn(resolved);
    },
  } as unknown as BrowserService;
}

describe("FlowService", () => {
  let dir: string;
  let config: ConfigService;
  let store: RunStore;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "harvester-flow-"));
    const values: Record<string, unknown> = {
      HARVEST_RUNS_DIR: join(dir, "runs"),
      HARVEST_PROFILES_DIR: join(dir, "profiles"),
      HARVEST_PROFILE_DIR: join(dir, "profile"),
      HARVEST_FLOWS_DIR: join(dir, "flows"),
      HARVEST_RUN_KEEP: 50,
      HARVEST_QUEUE_DEPTH: 2,
      HARVEST_HOST: "127.0.0.1",
      HARVEST_PORT: 8765,
      HARVEST_PROFILE: "main",
    };
    config = { get: (key: string) => values[key] } as unknown as ConfigService;
    store = new RunStore(config);
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  function makeService(page: Page | (() => Promise<Page>)): FlowService {
    return new FlowService(
      new FlowLoader(config),
      store,
      new RunQueue(config),
      makeBrowser(page),
      new ProfileRegistry(config),
      config,
    );
  }

  it("runs the built-in demo flow and stores its output", async () => {
    const service = makeService(makePage());

    const { record, settled } = await service.submit("demo-visit", {
      profile: "main",
      waitMs: 5_000,
    });

    expect(settled).toBe(true);
    expect(record.state).toBe("succeeded");
    expect(record.input).toEqual({ url: "http://127.0.0.1:8765/api/v1/demo" });
    expect(record.meta?.screenshots.visit).toBe("artifacts/visit.png");
    expect(record.meta?.usedSelectors["3.click"]).toBe("#bump");
    // The demo flow's own sentences are the run's scenario log: 6 steps, of which
    // one (`use`) runs a 4-step fragment, plus the screenshot inside the `if`.
    expect(record.meta?.steps).toHaveLength(11);
    expect(record.meta?.steps[3]).toMatchObject({
      step: "4.include",
      fragment: "demo-read-page",
    });
    expect(record.meta?.steps[2]).toMatchObject({
      step: "3.click",
      action: "click",
      desc: "click the button (candidate selectors, first hit wins)",
      ok: true,
    });

    expect(await service.output(record.id)).toMatchObject({
      heading: "harvester demo page",
      clickResult: "clicked",
      delayedText: "delayed-ready",
    });
    const png = await readFile(
      join(dir, "runs", record.id, "artifacts", "visit.png"),
      "utf8",
    );
    expect(png).toBe("png");
  });

  it("returns as soon as the run is queued when no wait is asked for", async () => {
    const service = makeService(makePage());

    const { record, settled } = await service.submit("demo-visit", {
      profile: "main",
    });
    expect(settled).toBe(false);
    expect(isTerminal(record.state)).toBe(false);

    const finished = await waitForTerminal(service, record.id);
    expect(finished.state).toBe("succeeded");
  });

  it("records a failed run with the flow error code", async () => {
    const service = makeService(
      makePage({
        "#title": "harvester demo page",
        "#delayed": "x",
        "#status": "y",
      }),
    );

    const { record } = await service.submit("demo-visit", {
      profile: "main",
      waitMs: 5_000,
    });

    expect(record.state).toBe("failed");
    expect(record.error).toMatchObject({ code: "selector-not-found" });
    // A failed run keeps the log up to the failure.
    expect(record.meta?.steps.at(-1)).toMatchObject({
      step: "3.click",
      ok: false,
      error: { code: "selector-not-found" },
    });
    expect(await store.readOutput(record.id)).toBeNull();
  });

  it("lists the flows with their kind and include edges", async () => {
    const service = makeService(makePage());

    const catalogue = await service.catalogue();
    const byName = new Map(catalogue.map((entry) => [entry.name, entry]));

    expect(byName.get("demo-read-page")).toMatchObject({
      kind: "fragment",
      includes: [],
    });
    expect(byName.get("demo-visit")).toMatchObject({
      kind: "flow",
      includes: ["demo-read-page"],
    });
    expect(byName.get("xhs-login-qr")).toMatchObject({ kind: "flow" });
  });

  it("runs a sync flow and returns its output in one call", async () => {
    const service = makeService(makePage());

    const { record, output } = await service.runSync("xhs-login-qr", {
      profile: "main",
      waitMs: 10_000,
    });

    expect(record.state).toBe("succeeded");
    expect(record.flow).toBe("xhs-login-qr");
    expect(output).toEqual({});
  });

  it("honours a flow's own throttle without slowing other flows", async () => {
    // A throwaway flow with a 120ms gap, in the writable flows directory.
    await mkdir(join(dir, "flows"), { recursive: true });
    await writeFile(
      join(dir, "flows", "paced.jsonc"),
      `{
        "name": "paced",
        "apiVersion": 1,
        "throttle": { "scope": "paced", "minIntervalMs": 120 },
        "steps": [{ "action": "goto", "url": "{{self}}/api/v1/demo" }]
      }`,
    );
    const service = makeService(makePage());

    const first = await service.submit("paced", {
      profile: "main",
      waitMs: 5_000,
    });
    const second = await service.submit("paced", {
      profile: "main",
      waitMs: 5_000,
    });
    const demo = await service.submit("demo-visit", {
      profile: "main",
      waitMs: 5_000,
    });

    expect(first.record.meta?.throttleMs).toBeUndefined();
    expect(second.record.meta?.throttleMs).toBeGreaterThanOrEqual(80);
    // A flow without `throttle` never waits.
    expect(demo.record.meta?.throttleMs).toBeUndefined();
  });

  it("refuses an async flow on the sync entry point", async () => {
    const service = makeService(makePage());

    await expect(
      service.runSync("demo-visit", { profile: "main" }),
    ).rejects.toThrow(/not a sync flow/);
  });

  it("reports a failed sync flow instead of a run id", async () => {
    const service = makeService(makePage({ "#title": "x" }));

    const error = await service
      .runSync("xhs-login-check", { profile: "main", waitMs: 10_000 })
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(HttpException);
    expect((error as HttpException).getStatus()).toBeGreaterThanOrEqual(500);
  });

  it("refuses to run a fragment on its own", async () => {
    const service = makeService(makePage());

    await expect(
      service.submit("demo-read-page", { profile: "main" }),
    ).rejects.toThrow(/is a fragment/);
  });

  it("rejects an unknown flow and a bad input", async () => {
    const service = makeService(makePage());

    await expect(
      service.submit("nope", { profile: "main" }),
    ).rejects.toBeInstanceOf(BadRequestException);
    await expect(
      service.submit("demo-visit", { profile: "main", input: { typo: true } }),
    ).rejects.toBeInstanceOf(BadRequestException);
    await expect(
      service.submit("demo-visit", { profile: "Bad Name" }),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it("404s the output of a run that has not produced one", async () => {
    const service = makeService(makePage({ "#title": "x" }));
    const { record } = await service.submit("demo-visit", {
      profile: "main",
      waitMs: 5_000,
    });
    await expect(service.output(record.id)).rejects.toBeInstanceOf(
      NotFoundException,
    );
  });

  it("cancels a run that is still waiting in the queue", async () => {
    const gate = deferred();
    const service = makeService(async () => {
      await gate.promise;
      return makePage();
    });

    const first = await service.submit("demo-visit", { profile: "main" });
    const second = await service.submit("demo-visit", { profile: "main" });
    expect(service.queueSnapshot("main").queued).toEqual([second.record.id]);

    const cancelled = await service.cancel(second.record.id);
    expect(cancelled.state).toBe("cancelled");

    gate.release();
    await waitForTerminal(service, first.record.id);
    expect((await service.get(second.record.id)).state).toBe("cancelled");
  });

  it("refuses work beyond the queue depth", async () => {
    const gate = deferred();
    const service = makeService(async () => {
      await gate.promise;
      return makePage();
    });

    const first = await service.submit("demo-visit", { profile: "main" });
    const second = await service.submit("demo-visit", { profile: "main" });
    await expect(
      service.submit("demo-visit", { profile: "main" }),
    ).rejects.toBeInstanceOf(QueueFullError);

    gate.release();
    // Both queued runs have to finish, otherwise the temp dir is still in use.
    await waitForTerminal(service, first.record.id);
    await waitForTerminal(service, second.record.id);
  });

  it("exposes the profile used when none is named", () => {
    expect(makeService(makePage()).defaultProfile).toBe("main");
  });
});

function deferred() {
  let release: () => void = () => undefined;
  const promise = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

async function waitForTerminal(service: FlowService, id: string) {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    const record = await service.get(id);
    if (isTerminal(record.state)) {
      return record;
    }
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error(`run ${id} did not finish`);
}
