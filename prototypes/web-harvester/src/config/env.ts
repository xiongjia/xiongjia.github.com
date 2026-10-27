import { z } from "zod";

/**
 * Single source of truth for runtime configuration.
 *
 * Everything is read from the environment (`.env` is loaded by
 * `ConfigModule.forRoot`), validated once at boot, and then read through
 * `ConfigService` with the exact key names below.
 */
export const envSchema = z.object({
  /** Bind address. Keep the default loopback — there is no auth layer. */
  HARVEST_HOST: z.string().min(1).default("127.0.0.1"),
  HARVEST_PORT: z.coerce.number().int().positive().default(8765),

  /**
   * Browser engine. `camoufox` (patched Firefox) is the default; `patchright`
   * drives your installed Chrome and needs no extra download.
   */
  HARVEST_BROWSER: z
    .enum(["patchright", "camoufox", "mock"])
    .default("camoufox"),
  /**
   * Playwright channel: "chrome" uses the locally installed Google Chrome (no
   * 180MB download, and the engine is real Chrome — good for anti-bot),
   * "chromium" uses the bundled build (`pnpm browser:install` first).
   */
  HARVEST_CHANNEL: z.enum(["chrome", "chromium"]).default("chrome"),
  /**
   * `false` shows a real window (best for watching a run), `virtual` runs it
   * headed on an Xvfb display (containers), `true` is fully headless.
   */
  HARVEST_HEADLESS: z
    .enum(["true", "false", "virtual"])
    .default("true")
    .transform((value) => (value === "virtual" ? "virtual" : value === "true")),

  /** Persistent browser profile (fingerprint + cookies live here). */
  HARVEST_PROFILE_DIR: z.string().min(1).default(".cache/profile"),
  /** Scraped output, screenshots included. */
  HARVEST_DATA_DIR: z.string().min(1).default("data"),

  /**
   * How long the login page may take to paint its QR before we screenshot the
   * whole viewport instead (the risk-control redirect also has to fit in here).
   */
  HARVEST_XHS_SETTLE_MS: z.coerce.number().int().min(0).default(8_000),

  /** Where the Xiaohongshu session jar lives (mode 0600 when written). */
  HARVEST_XHS_COOKIES: z.string().min(1).default(".cache/xhs-cookies.json"),

  /**
   * Fingerprint OS. Defaults to the host OS on purpose: Camoufox draws its font
   * list for the target platform, and claiming `windows` while running on macOS
   * leaves CJK text without a matching font — the page then renders as boxes.
   */
  HARVEST_OS: z.enum(["macos", "windows", "linux"]).optional(),

  HARVEST_LOCALE: z.string().min(1).default("zh-CN"),
  HARVEST_TIMEZONE: z.string().min(1).default("Asia/Shanghai"),
  /**
   * Camoufox downloads default addons (uBO) on launch; addons.mozilla.org
   * answers 451 in some regions, so the download is skipped by default.
   * Empty string = keep the default addons.
   */
  HARVEST_EXCLUDE_ADDONS: z
    .string()
    .default("uBO")
    .transform((value) =>
      value
        .split(",")
        .map((name) => name.trim().toUpperCase())
        .filter((name) => name.length > 0),
    ),

  /** Milliseconds between browser actions — set >0 to slow a run down. */
  HARVEST_SLOWMO: z.coerce.number().int().min(0).default(0),
  HARVEST_VIEWPORT_WIDTH: z.coerce.number().int().positive().default(1280),
  HARVEST_VIEWPORT_HEIGHT: z.coerce.number().int().positive().default(800),
});

export type HarvesterEnv = z.infer<typeof envSchema>;

/** `ConfigModule.forRoot({ validate })` hook: fail fast on bad config. */
export function validateEnv(raw: Record<string, unknown>): HarvesterEnv {
  const parsed = envSchema.safeParse(raw);
  if (!parsed.success) {
    const details = parsed.error.issues
      .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
      .join("; ");
    throw new Error(`Invalid environment: ${details}`);
  }
  return parsed.data;
}
