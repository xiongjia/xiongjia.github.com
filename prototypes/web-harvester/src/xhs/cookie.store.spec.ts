import type { Cookie } from "playwright-core";
import {
  mkdir,
  mkdtemp,
  readFile,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  hasSession,
  readCookieJar,
  SESSION_COOKIE,
  writeCookieJar,
} from "./cookie.store";

const cookie = (name: string): Cookie => ({
  name,
  value: "v",
  domain: ".xiaohongshu.com",
  path: "/",
  expires: -1,
  httpOnly: true,
  secure: true,
  sameSite: "Lax",
});

describe("cookie store", () => {
  let dir: string;
  let file: string;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "xhs-cookies-"));
    file = join(dir, "nested", "cookies.json");
    await mkdir(join(dir, "nested"), { recursive: true });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("round-trips cookies and records when they were saved", async () => {
    const jar = await writeCookieJar(file, [
      cookie(SESSION_COOKIE),
      cookie("a1"),
    ]);

    expect(jar.savedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    const read = await readCookieJar(file);
    expect(read?.cookies.map((entry) => entry.name)).toEqual([
      SESSION_COOKIE,
      "a1",
    ]);
  });

  it("writes the jar as 0600", async () => {
    await writeCookieJar(file, [cookie(SESSION_COOKIE)]);
    const mode = (await stat(file)).mode & 0o777;
    expect(mode).toBe(0o600);
  });

  it("treats a corrupt or missing jar as 'no session'", async () => {
    expect(await readCookieJar(file)).toBeNull();

    await writeFile(file, "{ not json", { mode: 0o600 });
    expect(await readCookieJar(file)).toBeNull();
    expect(hasSession(await readCookieJar(file))).toBe(false);
  });

  it("ignores jars without a cookies array", async () => {
    await writeFile(file, JSON.stringify({ savedAt: "now" }), { mode: 0o600 });
    expect(await readCookieJar(file)).toBeNull();
  });

  it("detects the session cookie specifically", async () => {
    expect(hasSession({ savedAt: "", cookies: [cookie("a1")] })).toBe(false);
    expect(hasSession({ savedAt: "", cookies: [cookie(SESSION_COOKIE)] })).toBe(
      true,
    );
    expect(hasSession(null)).toBe(false);
  });

  it("keeps the file readable JSON (no trailing garbage)", async () => {
    await writeCookieJar(file, [cookie("a1")]);
    const raw = await readFile(file, "utf8");
    expect(() => JSON.parse(raw)).not.toThrow();
    expect(raw.endsWith("\n")).toBe(true);
  });
});
