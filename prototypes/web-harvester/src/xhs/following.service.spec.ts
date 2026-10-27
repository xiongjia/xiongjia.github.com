import type { ConfigService } from "@nestjs/config";
import type { Page } from "playwright-core";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BrowserService } from "../browser/browser.service";
import { XhsFollowingService } from "./following.service";

const ROWS = [
  { name: "财经不眠姐", desc: "1篇笔记未看", avatar: "a/1" },
  { name: "NASA宇宙", desc: "8件商品上新", avatar: "a/2" },
  { name: "NASA宇宙", desc: "dup", avatar: "a/2" },
  { name: null, desc: "", avatar: null },
];

interface PageOptions {
  rows?: typeof ROWS;
  /** true → keep scrolling (scrollTop changes), false → at the end. */
  scrolls?: boolean;
  panelOpens?: boolean;
}

function makePage(options: PageOptions = {}) {
  const rows = options.rows ?? ROWS;
  const page = {
    goto: vi.fn(async () => null),
    waitForTimeout: vi.fn(async () => undefined),
    waitForSelector: vi.fn(async () =>
      options.panelOpens === false ? null : {},
    ),
    getAttribute: vi.fn(async () => "/user/profile/self001"),
    locator: vi.fn(() => ({
      first: () => ({
        count: async () => 1,
        click: async () => undefined,
        getAttribute: async () => "/user/profile/self001",
        textContent: async () => null,
      }),
    })),
    evaluate: vi.fn(async (fn: unknown, arg: unknown) => {
      const source = String(fn);
      if (source.includes("scrollBy")) {
        return options.scrolls ?? false;
      }
      if (Array.isArray(arg) && source.includes("scrollHeight")) {
        return false;
      }
      return rows;
    }),
  };
  return page as unknown as Page;
}

function makeBrowser(
  page: Page,
  cookies: Array<{ name: string }> = [{ name: "web_session" }],
) {
  const withPage = vi.fn(
    async <T>(fn: (target: Page) => Promise<T>): Promise<T> => fn(page),
  );
  const cookieMock = vi.fn(async () => cookies);
  return {
    browser: { withPage, cookies: cookieMock } as unknown as BrowserService,
    withPage,
  };
}

function makeConfig(dataDir: string): ConfigService {
  return {
    get: (key: string) => (key === "HARVEST_DATA_DIR" ? dataDir : undefined),
  } as unknown as ConfigService;
}

describe("XhsFollowingService", () => {
  let dir: string;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "xhs-following-"));
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("collects the panel rows and writes them to disk", async () => {
    const page = makePage();
    const { browser } = makeBrowser(page);
    const service = new XhsFollowingService(browser, makeConfig(dir));

    const result = await service.collect({ scrolls: 0 });

    expect(result.profileId).toBe("self001");
    expect(result.items).toEqual([
      { nickname: "财经不眠姐", desc: "1篇笔记未看", avatarUrl: "a/1" },
      { nickname: "NASA宇宙", desc: "8件商品上新", avatarUrl: "a/2" },
    ]);
    expect(result.count).toBe(2);
    expect(result.triggerUsed).toBeTruthy();

    const raw = await readFile(result.outputPath, "utf8");
    expect(raw).toContain("# profile=self001 count=2");
    expect(raw).toContain('"nickname":"财经不眠姐"');
  });

  it("stops at the requested limit", async () => {
    const page = makePage();
    const { browser } = makeBrowser(page);
    const service = new XhsFollowingService(browser, makeConfig(dir));

    const result = await service.collect({ limit: 1, scrolls: 5 });

    expect(result.items).toHaveLength(1);
  });

  it("returns nothing when the panel never opens", async () => {
    const page = makePage({ panelOpens: false });
    const { browser } = makeBrowser(page);
    const service = new XhsFollowingService(browser, makeConfig(dir));

    const result = await service.collect({ scrolls: 2 });

    expect(result.count).toBe(0);
    expect(result.triggerUsed).toBeNull();
  });

  it("refuses to scrape without a session", async () => {
    const page = makePage();
    const { browser, withPage } = makeBrowser(page, []);
    const service = new XhsFollowingService(browser, makeConfig(dir));

    await expect(service.collect()).rejects.toThrow(/no Xiaohongshu session/);
    expect(withPage).not.toHaveBeenCalled();
  });

  it("uses an explicitly provided profile id", async () => {
    const page = makePage();
    const { browser } = makeBrowser(page);
    const service = new XhsFollowingService(browser, makeConfig(dir));

    const result = await service.collect({
      profileId: "explicit9",
      scrolls: 0,
    });

    expect(result.profileId).toBe("explicit9");
    expect(page.goto).not.toHaveBeenCalledWith(
      "https://www.xiaohongshu.com/explore",
      expect.anything(),
    );
  });
});
