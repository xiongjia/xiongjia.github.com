import { Logger } from "@nestjs/common";
import { readFile, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
const logger = new Logger("ChromiumProfile");

/**
 * Chromium switches every automated launch wants, shared by both Chromium engines.
 *
 * The two `bubble` switches suppress the "Chromium didn't shut down correctly /
 * Restore pages?" prompt after an unclean exit. `repairChromiumProfile()` clears
 * the underlying marker as well, because the prompt keys off the profile state and
 * not only off the switch. Unknown switches are ignored by Chromium, so listing an
 * older alias costs nothing.
 */
export const CHROMIUM_NO_PROMPT_ARGS = [
  "--no-first-run",
  "--no-default-browser-check",
  "--hide-crash-restore-bubble",
  "--disable-session-crashed-bubble",
];

/**
 * Where Chromium keeps the flags that decide "did the last session end well?".
 *
 * `Default/Preferences` is the current layout; the bare `Preferences` is what
 * older builds (and some channels) write.
 */
const PREFERENCES_FILES = ["Default/Preferences", "Preferences"];

/**
 * Clear Chromium's "the last session crashed" marker before a launch.
 *
 * Chromium writes `profile.exit_type = "Crashed"` while it runs and only flips it
 * back to `Normal` on a clean shutdown. Kill the browser process (Ctrl-C twice,
 * `docker stop`, a laptop that slept, an OOM) and the marker survives — which is
 * what makes the next launch show the *Restore pages?* bubble and offer to reopen
 * the tabs of a session the harvester never wanted to keep.
 *
 * Rewriting the two fields (and nothing else) makes the launch look like an
 * ordinary clean start. Missing, unreadable or half-written files are left alone:
 * Chromium is the authority on its own profile, this is best effort.
 *
 * @returns the files that were repaired — empty when the profile was already clean.
 */
export async function repairChromiumProfile(
  profileDir: string,
): Promise<string[]> {
  const repaired: string[] = [];
  for (const relative of PREFERENCES_FILES) {
    const path = join(profileDir, relative);
    const raw = await readFile(path, "utf8").catch(() => null);
    if (raw === null) {
      continue;
    }

    let prefs: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(raw);
      if (
        typeof parsed !== "object" ||
        parsed === null ||
        Array.isArray(parsed)
      ) {
        continue;
      }
      prefs = parsed as Record<string, unknown>;
    } catch {
      continue;
    }

    const profile =
      typeof prefs.profile === "object" &&
      prefs.profile !== null &&
      !Array.isArray(prefs.profile)
        ? (prefs.profile as Record<string, unknown>)
        : {};
    if (profile.exit_type === "Normal" && profile.exited_cleanly === true) {
      continue;
    }

    profile.exit_type = "Normal";
    profile.exited_cleanly = true;
    prefs.profile = profile;

    // Write then rename: Chromium must never read a half-written Preferences.
    const temporary = `${path}.repair`;
    await writeFile(temporary, JSON.stringify(prefs), "utf8");
    await rename(temporary, path);
    repaired.push(relative);
  }

  if (repaired.length > 0) {
    logger.log(
      `Repaired an unclean Chromium profile (${repaired.join(", ")}) — no restore-pages prompt on this launch`,
    );
  }
  return repaired;
}
