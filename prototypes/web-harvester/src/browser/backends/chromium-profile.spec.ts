import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  CHROMIUM_NO_PROMPT_ARGS,
  repairChromiumProfile,
} from "./chromium-profile";

async function read(profileDir: string, relative: string) {
  const raw = await readFile(join(profileDir, relative), "utf8");
  return JSON.parse(raw) as {
    profile?: { exit_type?: string; exited_cleanly?: boolean };
  };
}

async function writePrefs(
  profileDir: string,
  relative: string,
  value: unknown,
): Promise<void> {
  const path = join(profileDir, relative);
  await mkdir(join(path, ".."), { recursive: true });
  await writeFile(
    path,
    typeof value === "string" ? value : JSON.stringify(value),
    "utf8",
  );
}

describe("repairChromiumProfile", () => {
  let dir: string;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "harvester-prefs-"));
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("clears the crashed marker a killed browser leaves behind", async () => {
    await writePrefs(dir, "Default/Preferences", {
      profile: { exit_type: "Crashed", name: "Person 1" },
      other: { untouched: true },
    });

    await expect(repairChromiumProfile(dir)).resolves.toEqual([
      "Default/Preferences",
    ]);

    const prefs = await read(dir, "Default/Preferences");
    expect(prefs.profile).toMatchObject({
      exit_type: "Normal",
      exited_cleanly: true,
      // Everything else in the file is Chromium's, not ours.
      name: "Person 1",
    });
    expect((prefs as { other: { untouched: boolean } }).other).toEqual({
      untouched: true,
    });
  });

  it("leaves a clean profile alone", async () => {
    await writePrefs(dir, "Default/Preferences", {
      profile: { exit_type: "Normal", exited_cleanly: true },
    });

    await expect(repairChromiumProfile(dir)).resolves.toEqual([]);
  });

  it("adds the marker when the profile never wrote one", async () => {
    await writePrefs(dir, "Default/Preferences", { profile: {} });

    await expect(repairChromiumProfile(dir)).resolves.toEqual([
      "Default/Preferences",
    ]);
    await expect(read(dir, "Default/Preferences")).resolves.toMatchObject({
      profile: { exit_type: "Normal", exited_cleanly: true },
    });
  });

  it("handles the older top-level Preferences layout", async () => {
    await writePrefs(dir, "Preferences", { profile: { exit_type: "Crashed" } });

    await expect(repairChromiumProfile(dir)).resolves.toEqual(["Preferences"]);
  });

  it("ignores a missing profile directory", async () => {
    await expect(repairChromiumProfile(join(dir, "nope"))).resolves.toEqual([]);
  });

  it("ignores a half-written or non-object Preferences file", async () => {
    await writePrefs(dir, "Default/Preferences", '{"profile": {"exit_t');
    await expect(repairChromiumProfile(dir)).resolves.toEqual([]);

    await writePrefs(dir, "Preferences", "[]");
    await expect(repairChromiumProfile(dir)).resolves.toEqual([]);
  });

  it("carries the switches that suppress the prompt anyway", () => {
    expect(CHROMIUM_NO_PROMPT_ARGS).toContain("--hide-crash-restore-bubble");
    expect(CHROMIUM_NO_PROMPT_ARGS).toContain(
      "--disable-session-crashed-bubble",
    );
    expect(CHROMIUM_NO_PROMPT_ARGS).toContain("--no-first-run");
  });
});
