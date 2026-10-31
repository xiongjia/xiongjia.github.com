import { z } from "zod";
import { getRandomPreset } from "camoufox";

/**
 * One browser identity.
 *
 * With the engine still in-process (M0 not done), a profile is a *persistent
 * browser directory*: cookies, localStorage and the fingerprint live there, so
 * `<profile>.json` only has to describe what cannot be derived — which is why the
 * fpgen preset is frozen into the file instead of being drawn on every launch.
 */
export const profileSchema = z
  .object({
    name: z
      .string()
      .min(1)
      .max(64)
      .regex(/^[a-z0-9][a-z0-9._-]*$/, "use lower-case kebab-case"),
    engine: z
      .enum(["camoufox", "patchright", "cloakbrowser"])
      .default("camoufox"),
    /**
     * Fingerprint OS Camoufox should claim (fonts and UA follow it). The Chromium
     * engines have no such switch: their platform is the one they run on.
     */
    os: z.enum(["macos", "windows", "linux"]).default("macos"),
    locale: z.string().min(1).default("zh-CN"),
    timezoneId: z.string().min(1).default("Asia/Shanghai"),
    viewport: z
      .object({
        width: z.number().int().positive().default(1280),
        height: z.number().int().positive().default(800),
      })
      .default({ width: 1280, height: 800 }),
    /** `http(s)://user:pass@host:port`; applied per context. */
    proxy: z
      .string()
      .min(1)
      .nullable()
      .default(null)
      .refine(
        (value) => value === null || isHttpUrl(value),
        "use http(s)://[user:pass@]host:port",
      ),
    /** Frozen Camoufox fingerprint preset (empty for patchright/cloakbrowser). */
    preset: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();
export type ProfileConfig = z.infer<typeof profileSchema>;

/** What `GET /api/v1/profiles` may reveal: never the preset. */
export interface ProfileSummary {
  name: string;
  /** Engine stored in `profile.json` (what a new profile would be created as). */
  engine: ProfileConfig["engine"];
  /** Engine a launch would actually use: `HARVEST_BROWSER` wins when set. */
  effectiveEngine: ProfileConfig["engine"];
  os: ProfileConfig["os"];
  locale: string;
  timezoneId: string;
  /** True when a browser directory exists — i.e. the profile has been used. */
  hasBrowserDir: boolean;
  /** True when a proxy is configured (the URL itself stays local). */
  proxy: boolean;
}

/** Only http(s) proxies make sense for a browser context. */
function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

/** Camoufox's name for the host platform. */
export function hostOs(): ProfileConfig["os"] {
  if (process.platform === "darwin") {
    return "macos";
  }
  if (process.platform === "win32") {
    return "windows";
  }
  return "linux";
}

/** A fresh preset to freeze into a new profile (Camoufox only). */
export function newPreset(os: ProfileConfig["os"]): Record<string, unknown> {
  return (getRandomPreset(os) as Record<string, unknown> | null) ?? {};
}
