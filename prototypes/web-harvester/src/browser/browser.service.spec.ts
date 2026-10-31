import type { ConfigService } from "@nestjs/config";
import type { BrowserContext, Page } from "playwright-core";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProfileRegistry } from "../profile/registry";
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
    HARVEST_PROFILE_DIR: join(tmpdir(), "harvester-spec-profile"),
    HARVEST_DATA_DIR: "data",
    HARVEST_VIEWPORT_WIDTH: 1280,
    HARVEST_VIEWPORT_HEIGHT: 800,
    ...values,
  };
  return { get: (key: string) => defaults[key] } as unknown as ConfigService;
}

/** Registry on a temp root: profile creation is part of the behaviour here. */
function makeProfiles(dataDir: string, values: Record<string, unknown> = {}) {
  return new ProfileRegistry(
    makeConfig({
      HARVEST_PROFILES_DIR: join(dataDir, "profiles"),
      HARVEST_PROFILE_DIR: join(dataDir, "profile"),
      ...values,
    }),
  );
}

function makeService(
  values: Record<string, unknown>,
  dataDir: string,
  backends: BrowserBackend[],
): BrowserService {
  return new BrowserService(
    makeConfig({
      HARVEST_PROFILES_DIR: join(dataDir, "profiles"),
      HARVEST_PROFILE_DIR: join(dataDir, "profile"),
      ...values,
    }),
    makeProfiles(dataDir, values),
    backends,
  );
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
    const service = makeService({}, dataDir, [backend]);

    await service.getContext();
    await service.getContext();

    expect(launch).toHaveBeenCalledTimes(1);
  });

  it("passes the profile, channel and fingerprint settings to the backend", async () => {
    const { backend, launch } = makeBackend();
    const service = makeService(
      { HARVEST_HEADLESS: false, HARVEST_CHANNEL: "chromium" },
      dataDir,
      [backend],
    );

    await service.getContext();

    const options = launch.mock
      .calls[0]?.[0] as unknown as BackendLaunchOptions;
    expect(options).toMatchObject({
      profileDir: join(dataDir, "profile"),
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
    const service = makeService({}, dataDir, [backend]);
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
    const service = makeService({}, dataDir, [backend]);
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
    const service = makeService({ HARVEST_DATA_DIR: dataDir }, dataDir, [
      backend,
    ]);

    const path = await service.withPage(async (page) =>
      service.screenshot(page, "demo"),
    );

    expect(path).toContain(join(dataDir, "screenshots"));
    expect(path.endsWith(".png")).toBe(true);
    await expect(readFile(path, "utf8")).resolves.toBe("png");
  });

  it("keeps one context per profile, each in its own directory", async () => {
    const { backend, launch } = makeBackend();
    const service = makeService({}, dataDir, [backend]);

    await service.getContext("main");
    await service.getContext("second");
    await service.getContext("second");

    expect(launch).toHaveBeenCalledTimes(2);
    const dirs = launch.mock.calls.map(
      (call) => (call[0] as unknown as BackendLaunchOptions).profileDir,
    );
    expect(dirs).toEqual([
      join(dataDir, "profile"),
      join(dataDir, "profiles", "second", "browser"),
    ]);
  });

  it("hands the frozen preset and locale of the profile to the backend", async () => {
    const { backend, launch } = makeBackend();
    const profiles = makeProfiles(dataDir, { HARVEST_LOCALE: "en-US" });
    const service = new BrowserService(
      makeConfig({
        HARVEST_PROFILES_DIR: join(dataDir, "profiles"),
        HARVEST_PROFILE_DIR: join(dataDir, "profile"),
        HARVEST_LOCALE: "en-US",
      }),
      profiles,
      [backend],
    );

    await service.getContext();

    const options = launch.mock
      .calls[0]?.[0] as unknown as BackendLaunchOptions;
    expect(options.locale).toBe("en-US");
    expect(options.proxy).toBeNull();
    // Frozen in profile.json, so restarts keep the same device.
    const stored = await profiles.get("main");
    expect(options.preset).toEqual(stored.preset);
    expect(Object.keys(stored.preset).length).toBeGreaterThan(0);
  });

  it("rejects engines that are not registered", async () => {
    const { backend } = makeBackend();
    const service = makeService({ HARVEST_BROWSER: "mock" }, dataDir, [
      backend,
    ]);

    await expect(service.getContext()).rejects.toThrow(/mock.*not implemented/);
  });

  it("switches engine with HARVEST_BROWSER, profile file untouched", async () => {
    // The profile on disk was created as Camoufox.
    await makeProfiles(dataDir).get("main");

    const camoufox = makeBackend();
    const cloak = makeBackend({ name: "cloakbrowser" });
    const profiles = makeProfiles(dataDir, { HARVEST_BROWSER: "cloakbrowser" });
    const service = new BrowserService(
      makeConfig({
        HARVEST_PROFILES_DIR: join(dataDir, "profiles"),
        HARVEST_PROFILE_DIR: join(dataDir, "profile"),
        HARVEST_BROWSER: "cloakbrowser",
      }),
      profiles,
      [camoufox.backend, cloak.backend],
    );

    await service.getContext();

    expect(camoufox.launch).not.toHaveBeenCalled();
    expect(cloak.launch).toHaveBeenCalledTimes(1);
    // Chromium engines never share the Camoufox (Firefox) profile directory.
    expect(
      (cloak.launch.mock.calls[0]?.[0] as unknown as BackendLaunchOptions)
        .profileDir,
    ).toBe(join(dataDir, "profile", "cloakbrowser"));
    expect((await profiles.get("main")).engine).toBe("camoufox");
  });

  it("closes the context on module destroy and relaunches afterwards", async () => {
    const { backend, launch } = makeBackend();
    const service = makeService({}, dataDir, [backend]);
    const context = await service.getContext();

    await service.onModuleDestroy();
    expect(context.close).toHaveBeenCalledTimes(1);

    await service.getContext();
    expect(launch).toHaveBeenCalledTimes(2);
  });

  it("ignores destroy when nothing was launched", async () => {
    const { backend, launch } = makeBackend();
    const service = makeService({}, dataDir, [backend]);

    await service.onModuleDestroy();
    expect(launch).not.toHaveBeenCalled();
  });

  it("closes a context on demand and relaunches on the next use", async () => {
    const { backend, launch } = makeBackend();
    const service = makeService({}, dataDir, [backend]);
    const context = await service.getContext();

    await expect(service.close()).resolves.toBe(true);
    expect(context.close).toHaveBeenCalledTimes(1);
    // Nothing open, so closing again is a no-op rather than an error.
    await expect(service.close()).resolves.toBe(false);
    expect(service.status()).toEqual([]);

    await service.getContext();
    expect(launch).toHaveBeenCalledTimes(2);
  });

  it("reports the open contexts with engine and idle time", async () => {
    const { backend } = makeBackend({ name: "cloakbrowser" });
    const service = makeService({ HARVEST_BROWSER: "cloakbrowser" }, dataDir, [
      backend,
    ]);

    await service.getContext("main");
    await service.getContext("second");
    await service.withPage(async () => undefined, "second");

    expect(service.status()).toMatchObject([
      { profile: "main", engine: "cloakbrowser", busy: false },
      { profile: "second", engine: "cloakbrowser", busy: false },
    ]);
    expect(service.status()[0]?.idleMs).toBeGreaterThanOrEqual(0);
  });

  it("closes every open context at once", async () => {
    const { backend } = makeBackend();
    const service = makeService({}, dataDir, [backend]);
    const first = await service.getContext("main");
    const second = await service.getContext("second");

    await expect(service.closeAll()).resolves.toEqual(["main", "second"]);
    expect(first.close).toHaveBeenCalledTimes(1);
    expect(second.close).toHaveBeenCalledTimes(1);
    await expect(service.closeAll()).resolves.toEqual([]);
  });

  describe("idle close", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("releases a context that sat idle for HARVEST_BROWSER_IDLE_MS", async () => {
      const { backend, launch } = makeBackend();
      const service = makeService({ HARVEST_BROWSER_IDLE_MS: 1_000 }, dataDir, [
        backend,
      ]);
      const context = await service.getContext();

      await vi.advanceTimersByTimeAsync(600);
      expect(context.close).not.toHaveBeenCalled();

      await vi.advanceTimersByTimeAsync(600);
      expect(context.close).toHaveBeenCalledTimes(1);

      // The session is on disk: the next use just launches again.
      await service.getContext();
      expect(launch).toHaveBeenCalledTimes(2);
    });

    it("never closes while a run holds the context", async () => {
      const { backend } = makeBackend();
      const service = makeService({ HARVEST_BROWSER_IDLE_MS: 100 }, dataDir, [
        backend,
      ]);
      const context = await service.getContext();

      let release = (): void => undefined;
      const held = service.withPage(
        () =>
          new Promise<void>((resolve) => {
            release = resolve;
          }),
      );
      await vi.advanceTimersByTimeAsync(1_000);
      expect(context.close).not.toHaveBeenCalled();

      release();
      await held;
      await vi.advanceTimersByTimeAsync(1_000);
      expect(context.close).toHaveBeenCalledTimes(1);
    });

    it("stays out of the way when the switch is off", async () => {
      const { backend } = makeBackend();
      const service = makeService({ HARVEST_BROWSER_IDLE_MS: 0 }, dataDir, [
        backend,
      ]);
      const context = await service.getContext();

      await vi.advanceTimersByTimeAsync(60_000);

      expect(context.close).not.toHaveBeenCalled();
    });
  });
});
