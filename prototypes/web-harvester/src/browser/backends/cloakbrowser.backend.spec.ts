import { mkdtemp, readFile, rm, writeFile, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The real module downloads a ~200 MB Chromium build on demand, so it is mocked
 * out entirely: these tests assert how we *call* it, not what it does.
 */
const state = vi.hoisted(() => ({
  installed: true,
  mode: "ok" as "ok" | "license" | "boom",
  calls: [] as unknown[],
}));

vi.mock("cloakbrowser", () => {
  class MockLicenseError extends Error {
    constructor(message: string) {
      super(message);
      this.name = "CloakBrowserLicenseError";
    }
  }
  return {
    binaryInfo: vi.fn(() => ({ installed: state.installed })),
    CloakBrowserLicenseError: MockLicenseError,
    launchPersistentContext: vi.fn(async (options: unknown) => {
      state.calls.push(options);
      if (state.mode === "license") {
        throw new MockLicenseError("no seat available");
      }
      if (state.mode === "boom") {
        throw new Error("profile is locked");
      }
      return { close: vi.fn(async () => undefined) };
    }),
  };
});

import { EngineNotReadyError } from "./backend";
import { cloakbrowserBackend } from "./cloakbrowser.backend";

const OPTIONS = {
  profileDir: "/tmp/harvester-cloak/profile",
  channel: "chrome" as const,
  headless: true as const,
  locale: "zh-CN",
  timezoneId: "Asia/Shanghai",
  viewport: { width: 1280, height: 800 },
  slowMo: 0,
  excludeAddons: ["UBO"],
  os: "macos" as const,
  preset: {},
  proxy: null,
};

const crashedProfileDirs: string[] = [];

describe("cloakbrowserBackend", () => {
  beforeEach(() => {
    state.installed = true;
    state.mode = "ok";
    state.calls = [];
  });

  afterEach(async () => {
    delete process.env.CLOAKBROWSER_BINARY_PATH;
    for (const dir of crashedProfileDirs.splice(0)) {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("refuses to launch without the stealth build instead of downloading it", async () => {
    state.installed = false;

    await expect(cloakbrowserBackend.launch(OPTIONS)).rejects.toThrow(
      EngineNotReadyError,
    );
    await expect(cloakbrowserBackend.launch(OPTIONS)).rejects.toThrow(
      /pnpm cloakbrowser:install/,
    );
    expect(state.calls).toHaveLength(0);
  });

  it("accepts a local binary override", async () => {
    state.installed = false;
    process.env.CLOAKBROWSER_BINARY_PATH = "/opt/chromium/Chromium";

    await cloakbrowserBackend.launch(OPTIONS);

    expect(state.calls).toHaveLength(1);
  });

  it("maps the profile onto one persistent context", async () => {
    await cloakbrowserBackend.launch(OPTIONS);

    expect(state.calls[0]).toMatchObject({
      userDataDir: "/tmp/harvester-cloak/profile",
      headless: true,
      locale: "zh-CN",
      timezoneId: "Asia/Shanghai",
      viewport: { width: 1280, height: 800 },
      humanize: true,
      // Undefined rather than null: the library takes a URL or nothing.
      proxy: undefined,
    });
    // No restore-pages prompt after an unclean exit.
    expect(state.calls[0]).toMatchObject({
      args: expect.arrayContaining([
        "--hide-crash-restore-bubble",
        "--disable-session-crashed-bubble",
      ]),
    });
  });

  it("clears a crashed profile before handing it to Chromium", async () => {
    const profileDir = await mkdtemp(join(tmpdir(), "harvester-cloak-"));
    crashedProfileDirs.push(profileDir);
    const prefsPath = join(profileDir, "Default", "Preferences");
    await mkdir(join(profileDir, "Default"), { recursive: true });
    await writeFile(prefsPath, '{"profile":{"exit_type":"Crashed"}}');

    await cloakbrowserBackend.launch({ ...OPTIONS, profileDir });

    const prefs = JSON.parse(await readFile(prefsPath, "utf8")) as {
      profile: { exit_type: string; exited_cleanly: boolean };
    };
    expect(prefs.profile).toMatchObject({ exit_type: "Normal" });
  });

  it("runs headed on an Xvfb display and forwards slow-motion", async () => {
    await cloakbrowserBackend.launch({
      ...OPTIONS,
      headless: "virtual",
      slowMo: 250,
      proxy: "http://user:pass@127.0.0.1:3128",
    });

    expect(state.calls[0]).toMatchObject({
      headless: false,
      proxy: "http://user:pass@127.0.0.1:3128",
      launchOptions: { slowMo: 250 },
    });
  });

  it("reports a license refusal as an engine that is not ready", async () => {
    state.mode = "license";

    await expect(cloakbrowserBackend.launch(OPTIONS)).rejects.toThrow(
      EngineNotReadyError,
    );
    await expect(cloakbrowserBackend.launch(OPTIONS)).rejects.toThrow(
      /cloakbrowser login/,
    );
  });

  it("lets genuine launch failures through unchanged", async () => {
    state.mode = "boom";

    await expect(cloakbrowserBackend.launch(OPTIONS)).rejects.toThrow(
      /profile is locked/,
    );
  });
});
