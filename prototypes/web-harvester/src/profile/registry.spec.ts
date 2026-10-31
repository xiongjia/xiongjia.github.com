import type { ConfigService } from "@nestjs/config";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ProfileRegistry } from "./registry";

function makeConfig(values: Record<string, unknown> = {}): ConfigService {
  const defaults: Record<string, unknown> = {
    HARVEST_PROFILES_DIR: ".cache/profiles",
    HARVEST_PROFILE_DIR: ".cache/profile",
    HARVEST_PROFILE: "main",
    HARVEST_BROWSER: "camoufox",
    HARVEST_OS: "macos",
    HARVEST_LOCALE: "zh-CN",
    HARVEST_TIMEZONE: "Asia/Shanghai",
    HARVEST_VIEWPORT_WIDTH: 1280,
    HARVEST_VIEWPORT_HEIGHT: 800,
    ...values,
  };
  return { get: (key: string) => defaults[key] } as unknown as ConfigService;
}

/** A registry rooted in the temp dir — never in the repo's `.cache/`. */
function makeRegistry(baseDir: string, values: Record<string, unknown> = {}) {
  return new ProfileRegistry(
    makeConfig({
      HARVEST_PROFILES_DIR: join(baseDir, "profiles"),
      HARVEST_PROFILE_DIR: join(baseDir, "profile"),
      ...values,
    }),
  );
}

describe("ProfileRegistry", () => {
  let dir: string;
  let config: ConfigService;
  let registry: ProfileRegistry;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "harvester-profiles-"));
    config = makeConfig({
      HARVEST_PROFILES_DIR: join(dir, "profiles"),
      HARVEST_PROFILE_DIR: join(dir, "profile"),
    });
    registry = new ProfileRegistry(config);
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("creates a profile from the env defaults on first use", async () => {
    const profile = await registry.get("main");

    expect(profile).toMatchObject({
      name: "main",
      engine: "camoufox",
      os: "macos",
      locale: "zh-CN",
      timezoneId: "Asia/Shanghai",
      viewport: { width: 1280, height: 800 },
      proxy: null,
    });
    // The preset is drawn once and written back, so the next start is the same
    // device rather than a new one.
    expect(Object.keys(profile.preset).length).toBeGreaterThan(0);
    const onDisk = JSON.parse(
      await readFile(join(dir, "profiles", "main", "profile.json"), "utf8"),
    ) as { preset: Record<string, unknown> };
    expect(onDisk.preset).toEqual(profile.preset);
  });

  it("reuses the frozen preset instead of drawing a new one", async () => {
    const first = await registry.get("main");
    const second = await new ProfileRegistry(config).get("main");

    expect(second.preset).toEqual(first.preset);
  });

  it("gives the default profile the legacy browser directory", async () => {
    const profile = await registry.get("main");

    expect(registry.browserDir(profile)).toBe(join(dir, "profile"));
    const other = await registry.get("second");
    expect(registry.browserDir(other)).toBe(
      join(dir, "profiles", "second", "browser"),
    );
  });

  it("creates a CloakBrowser profile without a Camoufox preset", async () => {
    const cloak = makeRegistry(dir, { HARVEST_BROWSER: "cloakbrowser" });

    const profile = await cloak.get("main");

    expect(profile.engine).toBe("cloakbrowser");
    // Chromium engines take their identity from the profile directory.
    expect(profile.preset).toEqual({});
  });

  it("keeps one browser directory per engine", async () => {
    const camoufoxProfile = await registry.get("main");
    const cloak = makeRegistry(dir, { HARVEST_BROWSER: "cloakbrowser" });
    const cloakProfile = await cloak.get("main");

    // Camoufox keeps the legacy path, Chromium engines get their own subdir, so
    // switching engines never touches the other engine's cookies.
    expect(registry.browserDir(camoufoxProfile)).toBe(join(dir, "profile"));
    expect(cloak.browserDir(cloakProfile)).toBe(
      join(dir, "profile", "cloakbrowser"),
    );
    expect(cloak.browserDir({ ...camoufoxProfile, name: "second" })).toBe(
      join(dir, "profiles", "second", "browser", "cloakbrowser"),
    );
  });

  it("lets HARVEST_BROWSER override a profile that already has an engine", async () => {
    const stored = await registry.get("main");
    expect(stored.engine).toBe("camoufox");

    const overridden = makeRegistry(dir, { HARVEST_BROWSER: "cloakbrowser" });
    const profile = await overridden.get("main");

    // The file stays untouched …
    expect(profile.engine).toBe("camoufox");
    // … the launch does not: engine and directory both follow the env.
    expect(overridden.effectiveEngine(profile)).toBe("cloakbrowser");
    expect(overridden.browserDir(profile)).toBe(
      join(dir, "profile", "cloakbrowser"),
    );
    expect(await overridden.summary(profile)).toMatchObject({
      engine: "camoufox",
      effectiveEngine: "cloakbrowser",
    });
  });

  it("lists every directory plus the untouched default", async () => {
    await registry.get("second");
    await mkdir(join(dir, "profiles", "main"), { recursive: true });

    const summaries = await registry.list();

    expect(summaries.map((summary) => summary.name)).toEqual([
      "main",
      "second",
    ]);
    expect(summaries[0]).toMatchObject({ hasBrowserDir: false, proxy: false });
  });

  it("reports whether a browser directory exists and a proxy is set", async () => {
    await writeFile(join(dir, "profiles", "work", "profile.json"), "{}").catch(
      async () => {
        await mkdir(join(dir, "profiles", "work"), { recursive: true });
        await writeFile(
          join(dir, "profiles", "work", "profile.json"),
          JSON.stringify({
            name: "work",
            proxy: "http://user:pass@127.0.0.1:3128",
          }),
        );
      },
    );
    await mkdir(join(dir, "profiles", "work", "browser"), { recursive: true });

    const profile = await registry.get("work");

    expect(profile.proxy).toBe("http://user:pass@127.0.0.1:3128");
    expect(await registry.summary(profile)).toMatchObject({
      hasBrowserDir: true,
      proxy: true,
      engine: "camoufox",
    });
  });

  it("updates one field and rejects unknown ones", async () => {
    await registry.get("main");

    const updated = await registry.update("main", { locale: "en-US" });
    expect(updated.locale).toBe("en-US");
    expect((await new ProfileRegistry(config).get("main")).locale).toBe(
      "en-US",
    );

    await expect(registry.update("main", { local: "en-US" })).rejects.toThrow(
      /Unrecognized key/,
    );
    await expect(registry.update("main", { name: "other" })).rejects.toThrow(
      /cannot be renamed/,
    );
  });

  it("validates the proxy while the profile is edited", async () => {
    await registry.get("main");
    await expect(
      registry.update("main", { proxy: "127.0.0.1:3128" }),
    ).rejects.toThrow(/http\(s\)/);

    const proxied = await registry.update("main", {
      proxy: "http://user:pass@127.0.0.1:3128",
    });
    expect(proxied.proxy).toBe("http://user:pass@127.0.0.1:3128");
  });

  it("deletes a profile but never the default one", async () => {
    await registry.get("second");
    await expect(registry.remove("main")).rejects.toThrow(/default profile/);

    await registry.remove("second");
    expect((await registry.list()).map((summary) => summary.name)).toEqual([
      "main",
    ]);
  });

  it("refuses names that are not safe directory names", async () => {
    await expect(registry.get("../etc")).rejects.toThrow(/not a profile name/);
    await expect(registry.get("Bad Name")).rejects.toThrow(
      /not a profile name/,
    );
  });

  it("rejects a profile file whose id does not match its directory", async () => {
    await mkdir(join(dir, "profiles", "misnamed"), { recursive: true });
    await writeFile(
      join(dir, "profiles", "misnamed", "profile.json"),
      JSON.stringify({ name: "other" }),
    );

    await expect(registry.get("misnamed")).rejects.toThrow(
      /declares name "other", expected "misnamed"/,
    );
  });
});
