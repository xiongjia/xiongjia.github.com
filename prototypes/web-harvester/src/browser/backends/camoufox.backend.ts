import {
  type DefaultAddon,
  Camoufox,
  listInstalled as listCamoufoxBuilds,
} from "camoufox";
import type { BrowserContext } from "playwright-core";
import type { BackendLaunchOptions, BrowserBackend } from "./backend";

const MISSING_BUILD =
  "Camoufox's Firefox build is not installed (it is a ~1.3 GB download from GitHub releases). " +
  "Run `pnpm camoufox:fetch` — with CAMOUFOX_MIRROR=https://ghfast.top/ when github.com downloads are blocked, " +
  "or CAMOUFOX_ZIP=/path/to/camoufox-<version>-<os>.<arch>.zip to install a copy fetched elsewhere — " +
  "or start the server with HARVEST_BROWSER=patchright to use the installed Chrome instead.";

/**
 * Camoufox (patched Firefox) backend — the default engine.
 *
 * Camoufox draws a coherent fingerprint per profile (navigator, screen, WebGL,
 * fonts, voices), which is the whole reason to prefer it over vanilla Chromium.
 * Its Firefox build is installed by `pnpm camoufox:fetch`, never on demand: the
 * launcher would otherwise sit in a slow background download on first request.
 */
export const camoufoxBackend: BrowserBackend = {
  name: "camoufox",

  async launch(options: BackendLaunchOptions): Promise<BrowserContext> {
    if (listCamoufoxBuilds().length === 0) {
      throw new Error(MISSING_BUILD);
    }

    const context = await Camoufox({
      headless: options.headless,
      persistent_context: true,
      user_data_dir: options.profileDir,
      humanize: true,
      os: options.os,
      exclude_addons: options.excludeAddons as DefaultAddon[],
      locale: options.locale,
      window: [options.viewport.width, options.viewport.height],
      slowMo: options.slowMo,
    });
    return context as unknown as BrowserContext;
  },
};

/** Surfaced by the demo controller so a missing build reads as 503, not 500. */
export const CAMOUFOX_MISSING_BUILD_MESSAGE = MISSING_BUILD;
