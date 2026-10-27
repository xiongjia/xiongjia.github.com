import type { ConfigService } from "@nestjs/config";
import type { Cookie, Page } from "playwright-core";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BrowserService } from "../browser/browser.service";
import { SESSION_COOKIE, writeCookieJar } from "./cookie.store";
import { XhsLoginService } from "./login.service";
import {
  ACCOUNT_NICKNAME_SELECTORS,
  ACCOUNT_PROFILE_LINK_SELECTORS,
  QR_SELECTORS,
} from "./selectors";

const PNG = Buffer.from("fake-png");

function cookie(name: string): Cookie {
  return {
    name,
    value: "v",
    domain: ".xiaohongshu.com",
    path: "/",
    expires: -1,
    httpOnly: true,
    secure: true,
    sameSite: "Lax",
  };
}

interface FakePageOptions {
  url?: string;
  title?: string;
  body?: string;
  /** Selector → element count; anything else returns 0. */
  counts?: Record<string, number>;
  /** Selector → text, for the signed-in sidebar. */
  texts?: Record<string, string>;
  /** Selector → href, for the profile link. */
  hrefs?: Record<string, string>;
}

function makePage(options: FakePageOptions = {}) {
  const counts = options.counts ?? {};
  let url = options.url ?? "about:blank";
  const page = {
    url: vi.fn(() => url),
    isClosed: vi.fn(() => false),
    goto: vi.fn(async (target: string) => {
      url = options.url ?? target;
    }),
    title: vi.fn(async () => options.title ?? "小红书"),
    textContent: vi.fn(async (selector?: string) => {
      if (selector && options.texts?.[selector] !== undefined) {
        return options.texts[selector];
      }
      return options.body ?? "";
    }),
    getAttribute: vi.fn(
      async (selector: string) => options.hrefs?.[selector] ?? null,
    ),
    waitForTimeout: vi.fn(async () => undefined),
    screenshot: vi.fn(async () => PNG),
    locator: vi.fn((selector: string) => ({
      first: () => ({
        count: async () => counts[selector] ?? 0,
        screenshot: async () => PNG,
        click: async () => undefined,
        textContent: async () => options.texts?.[selector] ?? null,
        getAttribute: async () => options.hrefs?.[selector] ?? null,
      }),
    })),
  };
  return {
    page: page as unknown as Page,
    mock: page,
    setUrl: (next: string) => (url = next),
  };
}

function makeBrowser(page: Page, cookies: Cookie[] = []) {
  const persistentPage = vi.fn(async () => page);
  const releasePage = vi.fn(async () => undefined);
  const cookieMock = vi.fn(async () => cookies);
  const addCookies = vi.fn(async () => undefined);
  const clearCookies = vi.fn(async () => undefined);
  const withPage = vi.fn(
    async <T>(fn: (target: Page) => Promise<T>): Promise<T> => fn(page),
  );
  const browser = {
    persistentPage,
    releasePage,
    withPage,
    cookies: cookieMock,
    addCookies,
    getContext: vi.fn(async () => ({ clearCookies })),
  } as unknown as BrowserService;
  return {
    browser,
    persistentPage,
    releasePage,
    withPage,
    cookieMock,
    addCookies,
    clearCookies,
  };
}

function makeConfig(cookieFile: string): ConfigService {
  return {
    get: (key: string) => {
      if (key === "HARVEST_XHS_COOKIES") return cookieFile;
      // keep the fallback test fast: no real 8s wait for a QR
      if (key === "HARVEST_XHS_SETTLE_MS") return 50;
      return undefined;
    },
  } as unknown as ConfigService;
}

describe("XhsLoginService", () => {
  let dir: string;
  let cookieFile: string;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "xhs-login-"));
    cookieFile = join(dir, "cookies.json");
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("returns an element screenshot when a QR selector matches", async () => {
    const { page } = makePage({
      url: "https://www.xiaohongshu.com/explore",
      counts: { [QR_SELECTORS[0]]: 1 },
    });
    const { browser } = makeBrowser(page);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));

    const { png, source } = await service.qrCode();

    expect(source).toBe(QR_SELECTORS[0]);
    expect(png).toEqual(PNG);
  });

  it("falls back to a viewport screenshot when no QR selector matches", async () => {
    const { page } = makePage({ url: "https://www.xiaohongshu.com/explore" });
    const { browser } = makeBrowser(page);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));

    const { source } = await service.qrCode();

    expect(source).toBe("viewport");
  });

  it("fails loudly on the IP risk-control page", async () => {
    const { page } = makePage({
      url: "https://www.xiaohongshu.com/website-login/error?error_code=300012",
    });
    const { browser } = makeBrowser(page);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));

    await expect(service.qrCode()).rejects.toThrow(
      /risk-control page \(安全限制 \/ 300012\)/,
    );
  });

  it("reports no session when nothing is saved and no cookie is set", async () => {
    const { page } = makePage({ url: "https://www.xiaohongshu.com/explore" });
    const { browser } = makeBrowser(page, [cookie("a1")]);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));

    const status = await service.status();

    expect(status).toMatchObject({
      loggedIn: false,
      blocked: false,
      savedAt: null,
    });
    expect(status.cookieNames).toEqual(["a1"]);
  });

  it("saves the jar as soon as the session cookie appears", async () => {
    const { page, setUrl } = makePage({
      url: "https://www.xiaohongshu.com/explore",
    });
    setUrl("https://www.xiaohongshu.com/explore");
    const { browser, releasePage } = makeBrowser(page, [
      cookie(SESSION_COOKIE),
    ]);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));

    const status = await service.status();

    expect(status.loggedIn).toBe(true);
    expect(status.savedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(releasePage).toHaveBeenCalled();
    const raw = JSON.parse(await readFile(cookieFile, "utf8"));
    expect(raw.cookies.map((entry: Cookie) => entry.name)).toEqual([
      SESSION_COOKIE,
    ]);
  });

  it("reports a saved session and seeds the browser with it once", async () => {
    const { page } = makePage({ url: "https://www.xiaohongshu.com/explore" });
    const { browser, addCookies, persistentPage } = makeBrowser(page);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));
    // a previous run left a jar behind
    await service.logout();
    await writeCookieJar(cookieFile, [cookie(SESSION_COOKIE)]);

    const fresh = new XhsLoginService(browser, makeConfig(cookieFile));
    const status = await fresh.status();
    await fresh.status();

    expect(status.loggedIn).toBe(true);
    expect(addCookies).toHaveBeenCalledTimes(1);
    expect(persistentPage).not.toHaveBeenCalled();
  });

  it("flags the risk-control page in status instead of pretending to be logged out", async () => {
    const { page } = makePage({
      url: "https://www.xiaohongshu.com/website-login/error?error_code=300012",
    });
    const { browser } = makeBrowser(page, [cookie("a1")]);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));

    const status = await service.status();

    expect(status).toMatchObject({ loggedIn: false, blocked: true });
  });

  it("returns login-gated identity data as proof of a live session", async () => {
    const nicknameSelector = ACCOUNT_NICKNAME_SELECTORS[0];
    const linkSelector = ACCOUNT_PROFILE_LINK_SELECTORS[0];
    const { page } = makePage({
      url: "https://www.xiaohongshu.com/explore",
      counts: { [nicknameSelector]: 1, [linkSelector]: 1 },
      texts: { [nicknameSelector]: " 阿甲 " },
      hrefs: { [linkSelector]: "/user/profile/5f8a1b2c" },
    });
    const { browser } = makeBrowser(page, [cookie("a1")]);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));
    await writeCookieJar(cookieFile, [cookie(SESSION_COOKIE)]);

    const status = await service.status();

    expect(status).toMatchObject({
      loggedIn: true,
      verified: true,
      account: { nickname: "阿甲", userId: "5f8a1b2c" },
    });
  });

  it("reports a stale session as logged in but unverified", async () => {
    const { page } = makePage({ url: "https://www.xiaohongshu.com/explore" });
    const { browser, withPage } = makeBrowser(page, [cookie("a1")]);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));
    await writeCookieJar(cookieFile, [cookie(SESSION_COOKIE)]);

    const status = await service.status();

    expect(status).toMatchObject({
      loggedIn: true,
      verified: false,
      account: null,
    });
    expect(withPage).toHaveBeenCalledTimes(1);
  });

  it("caches the verification instead of reopening a page on every poll", async () => {
    const { page } = makePage({
      url: "https://www.xiaohongshu.com/explore",
      counts: { [ACCOUNT_NICKNAME_SELECTORS[0]]: 1 },
      texts: { [ACCOUNT_NICKNAME_SELECTORS[0]]: "阿甲" },
    });
    const { browser, withPage } = makeBrowser(page, [cookie("a1")]);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));
    await writeCookieJar(cookieFile, [cookie(SESSION_COOKIE)]);

    await service.status();
    await service.status();

    expect(withPage).toHaveBeenCalledTimes(1);
  });

  it("clears cookies and empties the jar on logout", async () => {
    const { page } = makePage({ url: "https://www.xiaohongshu.com/explore" });
    const { browser, clearCookies, releasePage } = makeBrowser(page, [
      cookie(SESSION_COOKIE),
    ]);
    const service = new XhsLoginService(browser, makeConfig(cookieFile));

    await service.logout();

    expect(clearCookies).toHaveBeenCalledTimes(1);
    expect(releasePage).toHaveBeenCalled();
    const jar = JSON.parse(await readFile(cookieFile, "utf8"));
    expect(jar.cookies).toEqual([]);
  });
});
