import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  hostOs,
  newPreset,
  profileSchema,
  type ProfileConfig,
  type ProfileSummary,
} from "./profile";

/** Reserved characters: a profile name becomes a directory name. */
const NAME_PATTERN = /^[a-z0-9][a-z0-9._-]*$/;
const CONFIG_FILE = "profile.json";
const BROWSER_DIR = "browser";

/**
 * Profiles on disk.
 *
 * Layout (`HARVEST_PROFILES_DIR`, default `.cache/profiles`):
 *
 * ```
 * main/
 *   profile.json   # identity: engine, os, locale, frozen preset, proxy
 *   browser/       # the persistent browser profile (cookies, localStorage)
 * ```
 *
 * The default profile keeps using `HARVEST_PROFILE_DIR` as its browser directory,
 * so an existing logged-in profile (Xiaohongshu session) survives this change.
 */
@Injectable()
export class ProfileRegistry {
  private readonly logger = new Logger(ProfileRegistry.name);
  private readonly cache = new Map<string, ProfileConfig>();

  constructor(private readonly config: ConfigService) {}

  get rootDir(): string {
    return this.config.get<string>("HARVEST_PROFILES_DIR") ?? ".cache/profiles";
  }

  get defaultName(): string {
    return this.config.get<string>("HARVEST_PROFILE") ?? "main";
  }

  profileDir(name: string): string {
    return join(this.rootDir, assertName(name));
  }

  /**
   * Where this profile's browser lives.
   *
   * The default profile honours the legacy `HARVEST_PROFILE_DIR` so an existing
   * `.cache/profile` is not thrown away; every other profile gets its own
   * directory under the profiles root.
   */
  browserDir(profile: ProfileConfig): string {
    if (profile.name === this.defaultName) {
      return this.config.get<string>("HARVEST_PROFILE_DIR") ?? ".cache/profile";
    }
    return join(this.profileDir(profile.name), BROWSER_DIR);
  }

  /** Read a profile, creating it with sensible defaults on first use. */
  async get(name: string): Promise<ProfileConfig> {
    const safe = assertName(name);
    const cached = this.cache.get(safe);
    if (cached) {
      return cached;
    }

    const path = join(this.profileDir(safe), CONFIG_FILE);
    const raw = await readFile(path, "utf8").catch(() => null);
    const profile =
      raw === null
        ? await this.create(safe, path)
        : parseProfile(JSON.parse(raw) as unknown, path, safe);

    this.cache.set(safe, profile);
    return profile;
  }

  /** Every profile on disk, plus the default when it has not been used yet. */
  async list(): Promise<ProfileSummary[]> {
    const entries = await readdir(this.rootDir, { withFileTypes: true }).catch(
      () => [],
    );
    const names = new Set(
      entries
        .filter((entry) => entry.isDirectory() && NAME_PATTERN.test(entry.name))
        .map((entry) => entry.name),
    );
    names.add(this.defaultName);

    const summaries: ProfileSummary[] = [];
    for (const name of [...names].sort()) {
      try {
        summaries.push(await this.summary(await this.get(name)));
      } catch (error) {
        this.logger.warn(
          `profile "${name}" is unreadable: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    }
    return summaries;
  }

  /** Replace one profile's configuration (the name/preset are kept). */
  async update(
    name: string,
    patch: Record<string, unknown>,
  ): Promise<ProfileConfig> {
    const current = await this.get(name);
    if (patch.name !== undefined && patch.name !== current.name) {
      throw new Error(`a profile cannot be renamed ("${name}")`);
    }
    // `.strict()` on the schema turns a typo into an error instead of a no-op.
    const parsed = profileSchema.safeParse({ ...current, ...patch });
    if (!parsed.success) {
      throw new Error(
        parsed.error.issues
          .map(
            (issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`,
          )
          .join("; "),
      );
    }
    return this.save(parsed.data);
  }

  async save(profile: ProfileConfig): Promise<ProfileConfig> {
    const dir = this.profileDir(profile.name);
    await mkdir(dir, { recursive: true });
    await writeFile(
      join(dir, CONFIG_FILE),
      `${JSON.stringify(profile, null, 2)}\n`,
      "utf8",
    );
    this.cache.set(profile.name, profile);
    return profile;
  }

  /** Delete a profile and its browser directory; the default one is protected. */
  async remove(name: string): Promise<void> {
    if (name === this.defaultName) {
      throw new Error(
        `"${name}" is the default profile — switch HARVEST_PROFILE first if you really want it gone`,
      );
    }
    await rm(this.profileDir(name), { recursive: true, force: true });
    this.cache.delete(name);
  }

  async summary(profile: ProfileConfig): Promise<ProfileSummary> {
    const browserDir = this.browserDir(profile);
    const hasBrowserDir = await readdir(browserDir)
      .then(() => true)
      .catch(() => false);
    return {
      name: profile.name,
      engine: profile.engine,
      os: profile.os,
      locale: profile.locale,
      timezoneId: profile.timezoneId,
      hasBrowserDir,
      proxy: profile.proxy !== null,
    };
  }

  private async create(name: string, path: string): Promise<ProfileConfig> {
    const config = this.config;
    const os = config.get<ProfileConfig["os"]>("HARVEST_OS") ?? hostOs();
    const profile: ProfileConfig = {
      name,
      engine:
        config.get<ProfileConfig["engine"]>("HARVEST_BROWSER") ?? "camoufox",
      os,
      locale: config.get<string>("HARVEST_LOCALE") ?? "zh-CN",
      timezoneId: config.get<string>("HARVEST_TIMEZONE") ?? "Asia/Shanghai",
      viewport: {
        width: config.get<number>("HARVEST_VIEWPORT_WIDTH") ?? 1280,
        height: config.get<number>("HARVEST_VIEWPORT_HEIGHT") ?? 800,
      },
      proxy: null,
      preset: newPreset(os),
    };

    await mkdir(join(this.rootDir, name), { recursive: true });
    await writeFile(path, `${JSON.stringify(profile, null, 2)}\n`, "utf8");
    this.logger.log(
      `created profile "${name}" (${profile.engine}, os=${profile.os}) at ${path}`,
    );
    return profile;
  }
}

function parseProfile(
  raw: unknown,
  path: string,
  expectedName: string,
): ProfileConfig {
  const parsed = profileSchemaSafe(raw);
  if (parsed.ok === false) {
    throw new Error(`${path} is not a valid profile: ${parsed.error}`);
  }
  if (parsed.profile.name !== expectedName) {
    throw new Error(
      `${path} declares name "${parsed.profile.name}", expected "${expectedName}"`,
    );
  }
  return parsed.profile;
}

function profileSchemaSafe(
  raw: unknown,
): { ok: true; profile: ProfileConfig } | { ok: false; error: string } {
  const result = profileSchema.safeParse(raw);
  if (result.success) {
    return { ok: true, profile: result.data };
  }
  return {
    ok: false,
    error: result.error.issues
      .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
      .join("; "),
  };
}

function assertName(name: string): string {
  const value = name.trim();
  if (!NAME_PATTERN.test(value) || value.length > 64) {
    throw new Error(
      `"${name}" is not a profile name (lower-case kebab-case, e.g. main)`,
    );
  }
  return value;
}
