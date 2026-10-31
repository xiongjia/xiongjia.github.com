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

/** One open context, as `GET /api/v1/browser` reports it. */
export interface OpenContext {
  profile: string;
  /** Engine this context was launched with. */
  engine: BackendName | null;
  /** Milliseconds since it was last used. */
  idleMs: number;
  /** True while a run holds it — an idle sweep never closes a busy context. */
  busy: boolean;
}

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
 *
 * Contexts are kept warm on purpose (that is what makes "log in once" cheap) and
 * released in three ways: `HARVEST_BROWSER_IDLE_MS` closes a context that has
 * been idle that long, `close()`/`closeAll()` do it on demand, and shutdown
 * closes everything. Closing a context never loses the session — that lives in
 * the profile directory — it only gives the browser's memory and child processes
 * back.
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
  /** Engine each open context was launched with (for the status endpoint). */
  private readonly engines = new Map<string, BackendName>();
  /** Last time a profile was used; the idle sweep compares against this. */
  private readonly lastUsed = new Map<string, number>();
  /** Page work in flight per profile: `> 0` means "never close this one". */
  private readonly inFlight = new Map<string, number>();
  private sweep: NodeJS.Timeout | undefined;

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
      this.touch(profile);
      return existing;
    }
    let pending = this.launching.get(profile);
    if (!pending) {
      pending = this.launch(profile);
      this.launching.set(profile, pending);
    }
    const context = await pending;
    this.contexts.set(profile, context);
    this.touch(profile);
    return context;
  }

  /** Contexts that are open right now, newest activity last. */
  status(): OpenContext[] {
    const now = Date.now();
    return [...this.contexts.keys()].sort().map((profile) => ({
      profile,
      engine: this.engines.get(profile) ?? null,
      idleMs: Math.max(0, now - (this.lastUsed.get(profile) ?? now)),
      busy: (this.inFlight.get(profile) ?? 0) > 0,
    }));
  }

  /**
   * Close one profile's context (no-op when it is not open).
   *
   * The persistent profile directory is untouched: cookies, localStorage and the
   * fingerprint stay on disk, so the next call simply launches again.
   */
  async close(profile = this.defaultProfile): Promise<boolean> {
    // Never leave a half-launched browser behind: let it settle first.
    const pending = this.launching.get(profile);
    if (pending) {
      await pending.catch(() => undefined);
    }

    const context = this.contexts.get(profile);
    this.contexts.delete(profile);
    this.launching.delete(profile);
    this.engines.delete(profile);
    this.lastUsed.delete(profile);
    if (this.contexts.size === 0) {
      this.stopSweep();
    }
    if (!context) {
      return false;
    }

    this.logger.log(`Closing browser context (profile ${profile})`);
    await context.close().catch((error: unknown) => {
      this.logger.warn(
        `Failed to close context for profile ${profile}: ${String(error)}`,
      );
    });
    return true;
  }

  /** Close every open context; returns the profiles that actually had one. */
  async closeAll(): Promise<string[]> {
    const profiles = [
      ...new Set([...this.contexts.keys(), ...this.launching.keys()]),
    ].sort();
    const closed: string[] = [];
    for (const profile of profiles) {
      if (await this.close(profile)) {
        closed.push(profile);
      }
    }
    return closed;
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
      this.inFlight.set(profile, (this.inFlight.get(profile) ?? 0) + 1);
      try {
        return await fn(page);
      } finally {
        this.inFlight.set(
          profile,
          Math.max(0, (this.inFlight.get(profile) ?? 1) - 1),
        );
        // Idle time is measured from the end of the work, not its start.
        this.touch(profile);
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
    this.stopSweep();
    for (const [profile, context] of this.contexts) {
      this.logger.log(`Closing browser context (profile ${profile})`);
      await context.close().catch((error: unknown) => {
        this.logger.warn(
          `Failed to close context for profile ${profile}: ${String(error)}`,
        );
      });
    }
    this.contexts.clear();
    this.engines.clear();
    this.lastUsed.clear();
    this.inFlight.clear();
    // Drop the memoised launch promises too, otherwise getContext() would hand
    // back an already-closed context after a destroy/relaunch cycle.
    this.launching.clear();
  }

  /** How long a context may sit unused before it is closed (`0` = never). */
  private get idleCloseMs(): number {
    return this.config.get<number>("HARVEST_BROWSER_IDLE_MS") ?? 0;
  }

  /** Record activity on a profile and make sure the sweep is running. */
  private touch(profile: string): void {
    this.lastUsed.set(profile, Date.now());
    const idleMs = this.idleCloseMs;
    if (idleMs <= 0 || this.sweep) {
      return;
    }
    const period = Math.max(100, Math.floor(idleMs / 2));
    this.sweep = setInterval(() => {
      void this.closeIdleContexts();
    }, period);
    // Never keep the process alive just to close browsers.
    this.sweep.unref();
  }

  private stopSweep(): void {
    if (this.sweep) {
      clearInterval(this.sweep);
      this.sweep = undefined;
    }
  }

  /** Close every context that has been idle for `HARVEST_BROWSER_IDLE_MS`. */
  private async closeIdleContexts(): Promise<void> {
    const idleMs = this.idleCloseMs;
    if (idleMs <= 0) {
      return;
    }
    const now = Date.now();
    const stale = [...this.contexts.keys()].filter(
      (profile) =>
        (this.inFlight.get(profile) ?? 0) === 0 &&
        now - (this.lastUsed.get(profile) ?? now) >= idleMs,
    );
    for (const profile of stale) {
      const idle = now - (this.lastUsed.get(profile) ?? now);
      this.logger.log(
        `Releasing idle browser context for profile "${profile}" (idle ${idle} ms, HARVEST_BROWSER_IDLE_MS=${idleMs})`,
      );
      await this.close(profile);
    }
  }

  private get pageTimeout(): number {
    return this.config.get<number>("HARVEST_PAGE_TIMEOUT") ?? 15_000;
  }

  private async launch(profileName: string): Promise<BrowserContext> {
    const profile = await this.profiles.get(profileName);
    // `HARVEST_BROWSER` (when set) overrides the profile's own engine, so the
    // engine is switched with one env var instead of editing every profile.
    const engine = this.profiles.effectiveEngine(profile);
    const backend = this.backends.get(engine);
    if (!backend) {
      throw new Error(
        `Browser backend "${engine}" is not implemented yet (available: ${[...this.backends.keys()].join(", ")})`,
      );
    }

    const profileDir = this.profiles.browserDir(profile);
    await mkdir(profileDir, { recursive: true });

    const headless =
      this.config.get<boolean | "virtual">("HARVEST_HEADLESS") ?? true;
    const excludeAddons =
      this.config.get<string[]>("HARVEST_EXCLUDE_ADDONS") ?? [];

    const engineLabel =
      backend.name === "patchright"
        ? `${backend.name}/${this.config.get<string>("HARVEST_CHANNEL") ?? "chrome"}`
        : backend.name;
    const overridden =
      profile.engine !== engine
        ? ` [HARVEST_BROWSER overrides ${profile.engine}]`
        : "";
    this.logger.log(
      `Launching ${engineLabel} for profile "${profile.name}"${overridden} (headless=${headless}, os=${profile.os}, dir=${profileDir})`,
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
    this.engines.set(profile.name, backend.name);
    context.setDefaultTimeout(this.pageTimeout);
    return context;
  }
}
