import type { Cookie } from "playwright-core";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

/**
 * On-disk session jar for Xiaohongshu.
 *
 * Mirrors the approach of the repo's `shared/douban_auth.py`: the file holds
 * only cookies, is written with mode 0600 (the directory 0700), and a missing or
 * corrupt file is a normal "not logged in" answer rather than an error.
 */
export interface CookieJar {
  savedAt: string;
  cookies: Cookie[];
}

/** Session cookie that Xiaohongshu sets once a scan succeeds. */
export const SESSION_COOKIE = "web_session";

export async function readCookieJar(file: string): Promise<CookieJar | null> {
  const raw = await readFile(file, "utf8").catch(() => null);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<CookieJar>;
    if (!Array.isArray(parsed.cookies)) {
      return null;
    }
    return {
      savedAt: typeof parsed.savedAt === "string" ? parsed.savedAt : "",
      cookies: parsed.cookies,
    };
  } catch {
    return null;
  }
}

export async function writeCookieJar(
  file: string,
  cookies: Cookie[],
): Promise<CookieJar> {
  const jar: CookieJar = { savedAt: new Date().toISOString(), cookies };
  await mkdir(dirname(file), { recursive: true, mode: 0o700 });
  await writeFile(file, `${JSON.stringify(jar, null, 2)}\n`, { mode: 0o600 });
  // writeFile only applies `mode` when creating; re-assert for existing files.
  await chmod(file, 0o600);
  return jar;
}

/** True when the jar carries a session cookie (i.e. a scan happened). */
export function hasSession(jar: CookieJar | null): boolean {
  return Boolean(jar?.cookies.some((cookie) => cookie.name === SESSION_COOKIE));
}
