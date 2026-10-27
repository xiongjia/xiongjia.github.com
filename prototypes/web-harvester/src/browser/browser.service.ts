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
import type { BackendName, BrowserBackend } from "./backends/backend";
import { BROWSER_BACKENDS } from "./backends/index";

/** Minimal serial queue: one page at a time per browser, no extra dependency. */
function createSerialQueue(): <T>(task: () => Promise<T>) => Promise<T> {
  let tail: Promise<unknown> = Promise.resolve();
  return <T>(task: () => Promise<T>): Promise<T> => {
    const run = tail.then(task, task);
    tail = run.catch(() => undefined);
    return run;
  };
}

/**
 * Owns the single browser instance for the process.
 *
 * Pages are handed out through `withPage`, which serialises work: one account
 * means one profile, and two concurrent page loads on the same profile are both
 * a fingerprint leak and a flakiness source.
 */
@Injectable()
export class BrowserService implements OnModuleDestroy {
  private readonly logger = new Logger(BrowserService.name);
  private readonly backends: Map<BackendName, BrowserBackend>;
  private readonly serial = createSerialQueue();

  private context?: BrowserContext;
  private launching?: Promise<BrowserContext>;
  /** Long-lived pages (e.g. a login page that must survive between requests). */
  private readonly persistent = new Map<string, Page>();

  constructor(
    private readonly config: ConfigService,
    @Inject(BROWSER_BACKENDS) backends: BrowserBackend[],
  ) {
    this.backends = new Map(backends.map((backend) => [backend.name, backend]));
  }

  /** Camoufox's name for the host platform (keeps fonts and UA consistent). */
  private get hostOs(): "macos" | "windows" | "linux" {
    if (process.platform === "darwin") return "macos";
    if (process.platform === "win32") return "windows";
    return "linux";
  }

  get dataDir(): string {
    return this.config.get<string>("HARVEST_DATA_DIR") ?? "data";
  }

  async getContext(): Promise<BrowserContext> {
    if (this.context) {
      return this.context;
    }
    this.launching ??= this.launch();
    this.context = await this.launching;
    return this.context;
  }

  /** Run `fn` with a fresh page; the page is always closed afterwards. */
  async withPage<T>(fn: (page: Page) => Promise<T>): Promise<T> {
    return this.serial(async () => {
      const context = await this.getContext();
      const page = await context.newPage();
      try {
        return await fn(page);
      } finally {
        await page.close().catch(() => undefined);
      }
    });
  }

  /**
   * A page that stays open between requests, keyed by name.
   *
   * Needed by flows that span multiple HTTP calls — QR login being the obvious
   * one: the page holding the QR code must not be closed while the user scans.
   */
  async persistentPage(key: string): Promise<Page> {
    const existing = this.persistent.get(key);
    if (existing && !existing.isClosed()) {
      return existing;
    }
    const context = await this.getContext();
    const page = await context.newPage();
    page.setDefaultTimeout(15_000);
    this.persistent.set(key, page);
    return page;
  }

  async releasePage(key: string): Promise<void> {
    const page = this.persistent.get(key);
    this.persistent.delete(key);
    await page?.close().catch(() => undefined);
  }

  async cookies(): Promise<Cookie[]> {
    const context = await this.getContext();
    return context.cookies();
  }

  /** Seed a fresh context with a previously saved session. */
  async addCookies(cookies: Cookie[]): Promise<void> {
    const context = await this.getContext();
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
    if (!this.context) {
      return;
    }
    for (const key of [...this.persistent.keys()]) {
      await this.releasePage(key);
    }
    this.logger.log("Closing browser context");
    await this.context.close().catch((error: unknown) => {
      this.logger.warn(`Failed to close browser context: ${String(error)}`);
    });
    this.context = undefined;
    // Drop the memoised launch promise too, otherwise getContext() would hand
    // back the already-closed context after a destroy/relaunch cycle.
    this.launching = undefined;
  }

  private async launch(): Promise<BrowserContext> {
    const name =
      this.config.get<BackendName>("HARVEST_BROWSER") ?? "patchright";
    const backend = this.backends.get(name);
    if (!backend) {
      throw new Error(
        `Browser backend "${name}" is not implemented yet (available: ${[...this.backends.keys()].join(", ")})`,
      );
    }

    const profileDir =
      this.config.get<string>("HARVEST_PROFILE_DIR") ?? ".cache/profile";
    await mkdir(profileDir, { recursive: true });

    const viewport = {
      width: this.config.get<number>("HARVEST_VIEWPORT_WIDTH") ?? 1280,
      height: this.config.get<number>("HARVEST_VIEWPORT_HEIGHT") ?? 800,
    };
    const headless =
      this.config.get<boolean | "virtual">("HARVEST_HEADLESS") ?? true;
    const slowMo = this.config.get<number>("HARVEST_SLOWMO") ?? 0;
    const channel =
      this.config.get<"chrome" | "chromium">("HARVEST_CHANNEL") ?? "chrome";
    const excludeAddons =
      this.config.get<string[]>("HARVEST_EXCLUDE_ADDONS") ?? [];
    const os =
      this.config.get<"macos" | "windows" | "linux">("HARVEST_OS") ??
      this.hostOs;

    const engine =
      backend.name === "patchright"
        ? `${backend.name}/${channel}`
        : backend.name;
    this.logger.log(
      `Launching ${engine} (headless=${headless}, os=${os}, profile=${profileDir})`,
    );
    const context = await backend.launch({
      profileDir,
      channel,
      headless,
      locale: this.config.get<string>("HARVEST_LOCALE") ?? "zh-CN",
      timezoneId:
        this.config.get<string>("HARVEST_TIMEZONE") ?? "Asia/Shanghai",
      viewport,
      slowMo,
      excludeAddons,
      os,
    });
    context.setDefaultTimeout(15_000);
    return context;
  }
}
