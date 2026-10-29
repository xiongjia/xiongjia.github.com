import type { BrowserContext } from "playwright-core";
import { chromium } from "patchright";
import {
  toProxy,
  type BackendLaunchOptions,
  type BrowserBackend,
} from "./backend";

/**
 * Patchright (patched Playwright/Chromium) backend — the fallback engine.
 *
 * Uses a persistent context on purpose: cookies, localStorage and the rest of
 * the profile stay warm between runs, which is what makes "log in once" work.
 */
export const patchrightBackend: BrowserBackend = {
  name: "patchright",

  async launch(options: BackendLaunchOptions): Promise<BrowserContext> {
    const context = await chromium.launchPersistentContext(options.profileDir, {
      // Real Chrome by default: no browser download and a far more common
      // fingerprint than a bundled Chromium build.
      channel: options.channel,
      headless: options.headless === "virtual" ? false : options.headless,
      viewport: options.viewport,
      locale: options.locale,
      timezoneId: options.timezoneId,
      slowMo: options.slowMo,
      proxy: toProxy(options.proxy),
      args: ["--no-default-browser-check", "--no-first-run"],
    });
    return context as unknown as BrowserContext;
  },
};
