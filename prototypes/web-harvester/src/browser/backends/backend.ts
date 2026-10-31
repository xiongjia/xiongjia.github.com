import type { BrowserContext } from "playwright-core";

/**
 * Engine abstraction: everything above this interface only touches the
 * Playwright-compatible `BrowserContext` / `Page` API, so swapping the engine
 * (Camoufox/Firefox, patchright or CloakBrowser/Chromium) never touches demo or
 * XHS code.
 */
export type BackendName = "camoufox" | "patchright" | "cloakbrowser" | "mock";

/**
 * Thrown when an engine is configured but cannot start: its browser build is
 * missing, or its license refuses the launch.
 *
 * The HTTP layer maps this to `503 Service Unavailable` — it is an operator
 * problem with a concrete remedy, never a bug in the request.
 */
export class EngineNotReadyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EngineNotReadyError";
  }
}

/** `virtual` = run headed on an Xvfb display (Linux/containers). */
export type HeadlessMode = boolean | "virtual";

export interface BackendLaunchOptions {
  /** Persistent profile directory — fingerprint and cookies survive restarts. */
  profileDir: string;
  /** `chrome` = installed Chrome (patchright only), `chromium` = bundled build. */
  channel: "chrome" | "chromium";
  headless: HeadlessMode;
  locale: string;
  timezoneId: string;
  viewport: { width: number; height: number };
  /** Milliseconds to wait between actions — useful when watching a run. */
  slowMo: number;
  /** Default Camoufox addons to skip (e.g. `["UBO"]`); ignored by other engines. */
  excludeAddons: string[];
  /** Fingerprint OS the browser should claim (affects fonts, UA, navigator). */
  os: "macos" | "windows" | "linux";
  /** Frozen fpgen preset, so a profile keeps one identity across restarts. */
  preset: Record<string, unknown>;
  /** `http(s)://user:pass@host:port`, already validated by the profile file. */
  proxy: string | null;
}

/** `http://user:pass@host:3128` → Playwright's proxy config, or nothing. */
export function toProxy(
  proxy: string | null,
): { server: string; username?: string; password?: string } | undefined {
  if (!proxy) {
    return undefined;
  }
  const url = new URL(proxy);
  return {
    server: `${url.protocol}//${url.host}`,
    ...(url.username ? { username: decodeURIComponent(url.username) } : {}),
    ...(url.password ? { password: decodeURIComponent(url.password) } : {}),
  };
}

export interface BrowserBackend {
  readonly name: BackendName;
  launch(options: BackendLaunchOptions): Promise<BrowserContext>;
}
