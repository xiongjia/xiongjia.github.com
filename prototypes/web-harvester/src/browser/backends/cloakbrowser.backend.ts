import {
  binaryInfo,
  CloakBrowserLicenseError,
  launchPersistentContext,
  type LaunchPersistentContextOptions,
} from "cloakbrowser";
import type { BrowserContext } from "playwright-core";
import {
  EngineNotReadyError,
  type BackendLaunchOptions,
  type BrowserBackend,
} from "./backend";
import {
  CHROMIUM_NO_PROMPT_ARGS,
  repairChromiumProfile,
} from "./chromium-profile";

const MISSING_BINARY =
  "CloakBrowser's stealth Chromium build is not installed (a ~200 MB download from cloakbrowser.dev). " +
  "Run `pnpm cloakbrowser:install` (or `pnpm exec cloakbrowser install`), " +
  "point CLOAKBROWSER_BINARY_PATH at a local Chromium build, " +
  "or start the server with HARVEST_BROWSER=camoufox (or patchright) instead.";

const LICENSE_REFUSED =
  "CloakBrowser refused the launch for licensing reasons. Builds after v146 need a key: " +
  "run `pnpm exec cloakbrowser login` (a GitHub sign-in gives a free key with one concurrent session) " +
  "or set CLOAKBROWSER_LICENSE_KEY, then retry. " +
  "For several profiles at once use HARVEST_BROWSER=camoufox.";

/** True when the stealth Chromium build is on disk: no network, no download. */
function isInstalled(): boolean {
  if (process.env.CLOAKBROWSER_BINARY_PATH) {
    return true;
  }
  return binaryInfo(undefined, process.env.CLOAKBROWSER_RELEASE_CHANNEL)
    .installed;
}

/**
 * CloakBrowser (patched Chromium) backend — the stealth option.
 *
 * Drop-in Playwright: `launchPersistentContext()` hands back a plain
 * `BrowserContext`, so nothing above this file knows which engine it talks to.
 * The identity is the profile directory plus the `--fingerprint` seed
 * CloakBrowser freezes inside it — the Chromium counterpart of Camoufox's
 * frozen preset, which is why the profile's `preset`/`os` fields are unused here
 * (Chromium's platform is the one it runs on; claiming another one would bring
 * back the missing-CJK-font problem).
 *
 * The binary is never fetched here: like Camoufox, a missing build is an
 * operator problem, so the launch fails fast with the command that fixes it
 * instead of starting a 200 MB download behind a request.
 */
export const cloakbrowserBackend: BrowserBackend = {
  name: "cloakbrowser",

  async launch(options: BackendLaunchOptions): Promise<BrowserContext> {
    if (!isInstalled()) {
      throw new EngineNotReadyError(MISSING_BINARY);
    }

    // A killed browser leaves "this session crashed" behind; clearing it keeps
    // the next launch free of the restore-pages prompt.
    await repairChromiumProfile(options.profileDir);

    const launchOptions: LaunchPersistentContextOptions = {
      userDataDir: options.profileDir,
      // `virtual` means "headed on an Xvfb display", so it stays headed here.
      headless: options.headless === "virtual" ? false : options.headless,
      // Both are binary flags (`--fingerprint-locale`, `--fingerprint-timezone`),
      // not CDP emulation, so they stay invisible to fingerprinting scripts.
      locale: options.locale,
      timezoneId: options.timezoneId,
      viewport: options.viewport,
      // The profile URL goes in as-is: CloakBrowser splits the credentials
      // itself and keeps proxy auth inside the browser where its build allows.
      proxy: options.proxy ?? undefined,
      humanize: true,
      args: [...CHROMIUM_NO_PROMPT_ARGS],
      // Raw Playwright launch options, so slow-motion works for this engine too.
      launchOptions: { slowMo: options.slowMo },
    };

    try {
      const context = await launchPersistentContext(launchOptions);
      return context as unknown as BrowserContext;
    } catch (error) {
      if (error instanceof CloakBrowserLicenseError) {
        throw new EngineNotReadyError(LICENSE_REFUSED);
      }
      throw error;
    }
  },
};
