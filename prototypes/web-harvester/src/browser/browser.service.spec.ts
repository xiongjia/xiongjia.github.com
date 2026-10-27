import type { ConfigService } from "@nestjs/config";
import type { BrowserContext, Page } from "playwright-core";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BackendLaunchOptions, BrowserBackend } from "./backends/backend";
import { BrowserService } from "./browser.service";

interface FakePage {
  close: ReturnType<typeof vi.fn>;
  screenshot: ReturnType<typeof vi.fn>;
}

function makePage(): FakePage {
  return {
    close: vi.fn(async () => undefined),
    screenshot: vi.fn(async ({ path }: { path: string }) => {
      await write(path);
      return Buffer.from("png");
    }),
  };
}

async function write(path: string): Promise<void> {
  const { writeFile } = await import("node:fs/promises");
  await writeFile(path, "png");
}

function makeContext(): { context: BrowserContext; pages: FakePage[] } {
  const pages: FakePage[] = [];
  const context = {
    newPage: vi.fn(async () => {
      const page = makePage();
      pages.push(page);
      return page;
    }),
    close: vi.fn(async () => undefined),
    setDefaultTimeout: vi.fn(),
  };
  return { context: context as unknown as BrowserContext, pages };
}

function makeBackend(overrides: Partial<BrowserBackend> = {}) {
  const launch = vi.fn(
    async (_options: BackendLaunchOptions) => makeContext().context,
  );
  const backend: BrowserBackend = {
    name: "camoufox",
    launch: launch as unknown as BrowserBackend["launch"],
    ...overrides,
  };
  return { backend, launch };
}

function makeConfig(values: Record<string, unknown> = {}): ConfigService {
  const defaults: Record<string, unknown> = {
    HARVEST_BROWSER: "camoufox",
    HARVEST_HEADLESS: true,
    HARVEST_CHANNEL: "chrome",
    HARVEST_SLOWMO: 0,
    HARVEST_EXCLUDE_ADDONS: ["UBO"],
    HARVEST_LOCALE: "zh-CN",
    HARVEST_TIMEZONE: "Asia/Shanghai",
    HARVEST_PROFILE_DIR: ".cache/profile",
    HARVEST_DATA_DIR: "data",
    HARVEST_VIEWPORT_WIDTH: 1280,
    HARVEST_VIEWPORT_HEIGHT: 800,
    ...values,
  };
  return { get: (key: string) => defaults[key] } as unknown as ConfigService;
}

describe("BrowserService", () => {
  let dataDir: string;

  beforeEach(async () => {
    dataDir = await mkdtemp(join(tmpdir(), "harvester-spec-"));
  });

  afterEach(async () => {
    await rm(dataDir, { recursive: true, force: true });
  });

  it("launches the backend only once across calls", async () => {
    const { backend, launch } = makeBackend();
    const service = new BrowserService(makeConfig(), [backend]);

    await service.getContext();
    await service.getContext();

    expect(launch).toHaveBeenCalledTimes(1);
  });

  it("passes the profile, channel and fingerprint settings to the backend", async () => {
    const { backend, launch } = makeBackend();
    const service = new BrowserService(
      makeConfig({ HARVEST_HEADLESS: false, HARVEST_CHANNEL: "chromium" }),
      [backend],
    );

    await service.getContext();

    const options = launch.mock
      .calls[0]?.[0] as unknown as BackendLaunchOptions;
    expect(options).toMatchObject({
      profileDir: ".cache/profile",
      channel: "chromium",
      headless: false,
      locale: "zh-CN",
      timezoneId: "Asia/Shanghai",
      viewport: { width: 1280, height: 800 },
      slowMo: 0,
      excludeAddons: ["UBO"],
      os: "macos",
    });
  });

  it("runs page work serially and always closes the page", async () => {
    const { backend } = makeBackend();
    const service = new BrowserService(makeConfig(), [backend]);
    const order: string[] = [];
    let active = 0;
    let maxActive = 0;

    const task = (name: string) => async (): Promise<void> => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      order.push(`start:${name}`);
      await new Promise((resolve) => setTimeout(resolve, 10));
      order.push(`end:${name}`);
      active -= 1;
    };

    await Promise.all([
      service.withPage(task("a")),
      service.withPage(task("b")),
    ]);

    expect(maxActive).toBe(1);
    expect(order).toEqual(["start:a", "end:a", "start:b", "end:b"]);
  });

  it("closes the page and rethrows when the task fails", async () => {
    const { backend } = makeBackend();
    const service = new BrowserService(makeConfig(), [backend]);
    const context = await service.getContext();
    const page = makePage();
    context.newPage = vi.fn(
      async () => page as unknown as Page,
    ) as unknown as BrowserContext["newPage"];

    await expect(
      service.withPage(async () => {
        throw new Error("boom");
      }),
    ).rejects.toThrow("boom");
    expect(page.close).toHaveBeenCalledTimes(1);
  });

  it("writes screenshots under <dataDir>/screenshots", async () => {
    const { backend } = makeBackend();
    const service = new BrowserService(
      makeConfig({ HARVEST_DATA_DIR: dataDir }),
      [backend],
    );

    const path = await service.withPage(async (page) =>
      service.screenshot(page, "demo"),
    );

    expect(path).toContain(join(dataDir, "screenshots"));
    expect(path.endsWith(".png")).toBe(true);
    await expect(readFile(path, "utf8")).resolves.toBe("png");
  });

  it("rejects engines that are not registered", async () => {
    const { backend } = makeBackend();
    const service = new BrowserService(
      makeConfig({ HARVEST_BROWSER: "mock" }),
      [backend],
    );

    await expect(service.getContext()).rejects.toThrow(/mock.*not implemented/);
  });

  it("closes the context on module destroy and relaunches afterwards", async () => {
    const { backend, launch } = makeBackend();
    const service = new BrowserService(makeConfig(), [backend]);
    const context = await service.getContext();

    await service.onModuleDestroy();
    expect(context.close).toHaveBeenCalledTimes(1);

    await service.getContext();
    expect(launch).toHaveBeenCalledTimes(2);
  });

  it("ignores destroy when nothing was launched", async () => {
    const { backend, launch } = makeBackend();
    const service = new BrowserService(makeConfig(), [backend]);

    await service.onModuleDestroy();
    expect(launch).not.toHaveBeenCalled();
  });
});
