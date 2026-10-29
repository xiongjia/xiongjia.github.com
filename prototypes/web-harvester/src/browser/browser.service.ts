import {
  Inject,
  Injectable,
  Logger,
  type OnModuleDestroy,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import type { BrowserContext, Cookie, Page } from "playwright-core";
import { ProfileRegistry } from "../profile/registry";
import type { BackendName, BrowserBackend } from "./backends/backend";
import { BROWSER_BACKENDS } from "./backends/index";

/** Minimal serial queue: one task at a time, no extra dependency. */
function createSerialQueue(): <T>(task: () => Promise<T>) => Promise<T> {
  let tail: Promise<unknown> = Promise.resolve();
  return <T>(task: () => Promise<T>): Promise<T> => {
    const run = tail.then(task, task);
    tail = run.catch(() => undefined);
    return run;
  };
}

/**
 * Owns one persistent browser context per profile.
 *
 * Serialisation is per profile, not global: two profiles may browse at the same
 * time, but two page loads on the same profile are a fingerprint leak and a
 * flakiness source. Every method defaults to `HARVEST_PROFILE`, so existing
 * single-profile callers (Xiaohongshu) keep working unchanged.
 */
@Injectable()
export class BrowserService implements OnModuleDestroy {
  private readonly logger = new Logger(BrowserService.name);
  private readonly backends: Map<BackendName, BrowserBackend>;
  private readonly serials = new Map<
    string,
    ReturnType<typeof createSerialQueue>
  >();
  private readonly contexts = new Map<string, BrowserContext>();
  private readonly launching = new Map<string, Promise<BrowserContext>>();

  constructor(
    private readonly config: ConfigService,
    private readonly profiles: ProfileRegistry,
    @Inject(BROWSER_BACKENDS) backends: BrowserBackend[],
  ) {
    this.backends = new Map(backends.map((backend) => [backend.name, backend]));
  }

  get dataDir(): string {
    return this.config.get<string>("HARVEST_DATA_DIR") ?? "data";
  }

  /** Profile used when a caller does not name one. */
  get defaultProfile(): string {
    return this.profiles.defaultName;
  }

  async getContext(profile = this.defaultProfile): Promise<BrowserContext> {
    const existing = this.contexts.get(profile);
    if (existing) {
      return existing;
    }
    let pending = this.launching.get(profile);
    if (!pending) {
      pending = this.launch(profile);
      this.launching.set(profile, pending);
    }
    const context = await pending;
    this.contexts.set(profile, context);
    return context;
  }

  /** Run `fn` with a fresh page on `profile`; the page is always closed. */
  async withPage<T>(
    fn: (page: Page) => Promise<T>,
    profile = this.defaultProfile,
  ): Promise<T> {
    let serial = this.serials.get(profile);
    if (!serial) {
      serial = createSerialQueue();
      this.serials.set(profile, serial);
    }
    return serial(async () => {
      const context = await this.getContext(profile);
      const page = await context.newPage();
      try {
        return await fn(page);
      } finally {
        await page.close().catch(() => undefined);
      }
    });
  }

  async cookies(profile = this.defaultProfile): Promise<Cookie[]> {
    const context = await this.getContext(profile);
    return context.cookies();
  }

  /** Seed a fresh context with a previously saved session. */
  async addCookies(
    cookies: Cookie[],
    profile = this.defaultProfile,
  ): Promise<void> {
    const context = await this.getContext(profile);
    await context.addCookies(cookies);
  }

  /** Screenshot helper: writes under `<dataDir>/screenshots` and returns the path. */
  async screenshot(page: Page, prefix: string): Promise<string> {
    const dir = join(this.dataDir, "screenshots");
    await mkdir(dir, { recursive: true });
    const path = join(
      dir,
      `${prefix}-${new Date().toISOString().replace(/[:.]/g, "-")}.png`,
    );
    await page.screenshot({ path, fullPage: true });
    return path;
  }

  async onModuleDestroy(): Promise<void> {
    for (const [profile, context] of this.contexts) {
      this.logger.log(`Closing browser context (profile ${profile})`);
      await context.close().catch((error: unknown) => {
        this.logger.warn(
          `Failed to close context for profile ${profile}: ${String(error)}`,
        );
      });
    }
    this.contexts.clear();
    // Drop the memoised launch promises too, otherwise getContext() would hand
    // back an already-closed context after a destroy/relaunch cycle.
    this.launching.clear();
  }

  private get pageTimeout(): number {
    return this.config.get<number>("HARVEST_PAGE_TIMEOUT") ?? 15_000;
  }

  private async launch(profileName: string): Promise<BrowserContext> {
    const profile = await this.profiles.get(profileName);
    const backend = this.backends.get(profile.engine as BackendName);
    if (!backend) {
      throw new Error(
        `Browser backend "${profile.engine}" is not implemented yet (available: ${[...this.backends.keys()].join(", ")})`,
      );
    }

    const profileDir = this.profiles.browserDir(profile);
    await mkdir(profileDir, { recursive: true });

    const headless =
      this.config.get<boolean | "virtual">("HARVEST_HEADLESS") ?? true;
    const excludeAddons =
      this.config.get<string[]>("HARVEST_EXCLUDE_ADDONS") ?? [];

    const engine =
      backend.name === "patchright"
        ? `${backend.name}/${this.config.get<string>("HARVEST_CHANNEL") ?? "chrome"}`
        : backend.name;
    this.logger.log(
      `Launching ${engine} for profile "${profile.name}" (headless=${headless}, os=${profile.os}, dir=${profileDir})`,
    );

    const context = await backend.launch({
      profileDir,
      channel:
        this.config.get<"chrome" | "chromium">("HARVEST_CHANNEL") ?? "chrome",
      headless,
      locale: profile.locale,
      timezoneId: profile.timezoneId,
      viewport: profile.viewport,
      slowMo: this.config.get<number>("HARVEST_SLOWMO") ?? 0,
      excludeAddons,
      os: profile.os,
      preset: profile.preset,
      proxy: profile.proxy,
    });
    context.setDefaultTimeout(this.pageTimeout);
    return context;
  }
}
