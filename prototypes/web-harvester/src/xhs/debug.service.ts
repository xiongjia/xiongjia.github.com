import { Injectable, Logger } from "@nestjs/common";
import type { Page } from "playwright-core";
import { BrowserService } from "../browser/browser.service";
import { SESSION_COOKIE } from "./cookie.store";
import {
  ACCOUNT_PROFILE_LINK_SELECTORS,
  FOLLOWING_ITEM_SELECTOR,
  FOLLOWING_PANEL_SELECTOR,
  FOLLOWING_TAB_SELECTORS,
  USER_PROFILE_ID_RE,
  XHS_HOME,
} from "./selectors";

/**
 * What a "why did the following list come back empty?" report contains.
 *
 * The site changes shape often enough that guessing selectors is wasteful: this
 * dumps what the page actually looked like — which tab candidates matched, which
 * anchors exist, whether the list opened in a modal — plus a screenshot.
 */
export interface FollowingDebugReport {
  url: string;
  title: string;
  profileId: string | null;
  sidebarMatches: Array<{ selector: string; count: number }>;
  tabMatches: Array<{ selector: string; count: number; text: string | null }>;
  clickedTab: string | null;
  urlAfterTabClick: string;
  /** Selector → number of matches, after opening the tab. */
  selectorCounts: Record<string, number>;
  /** Every profile-ish link found, with the element it came from. */
  links: Array<{ href: string; text: string; tag: string; cls: string }>;
  /** Names of the likely scroll/modal containers, to debug the wheel target. */
  containers: Array<{
    cls: string;
    scrollHeight: number;
    clientHeight: number;
  }>;
  bodyTextSample: string;
  screenshotPath: string;
}

const PROBE_SELECTORS = [
  FOLLOWING_PANEL_SELECTOR,
  FOLLOWING_ITEM_SELECTOR,
  "[class*='relation-name']",
  "[class*='following-list']",
  "[class*='following-scroll']",
  "a[href*='/user/profile']",
  "[class*='modal']",
] as const;

/** One-off inspection of the profile page — no scraping, no side effects. */
@Injectable()
export class XhsDebugService {
  private readonly logger = new Logger(XhsDebugService.name);

  constructor(private readonly browser: BrowserService) {}

  async inspectFollowing(profileId?: string): Promise<FollowingDebugReport> {
    const cookies = await this.browser.cookies();
    if (!cookies.some((cookie) => cookie.name === SESSION_COOKIE)) {
      throw new Error(
        "no Xiaohongshu session — call GET /api/v1/xhs/login/qrcode, scan it, then retry",
      );
    }

    return this.browser.withPage(async (page) => {
      await page.goto(XHS_HOME, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1_500);

      const sidebarMatches = (
        await this.matchAll(page, ACCOUNT_PROFILE_LINK_SELECTORS)
      ).map(({ selector, count }) => ({ selector, count }));
      const resolved =
        profileId ?? (await this.firstProfileId(page)) ?? undefined;

      if (resolved) {
        await page.goto(
          `https://www.xiaohongshu.com/user/profile/${resolved}`,
          { waitUntil: "domcontentloaded" },
        );
      }
      await page.waitForTimeout(2_000);

      const tabMatches = (
        await this.matchAll(page, FOLLOWING_TAB_SELECTORS, true)
      ).map(({ selector, count, text }) => ({
        selector,
        count,
        text: text ?? null,
      }));
      const clickedTab =
        tabMatches.find((match) => match.count > 0)?.selector ?? null;
      if (clickedTab) {
        await page
          .locator(clickedTab)
          .first()
          .click({ timeout: 5_000 })
          .catch(() => undefined);
        await page.waitForTimeout(2_500);
      }

      const selectorCounts: Record<string, number> = {};
      for (const selector of PROBE_SELECTORS) {
        selectorCounts[selector] = await page
          .locator(selector)
          .count()
          .catch(() => -1);
      }

      const links = await page.evaluate(() => {
        return [...document.querySelectorAll("[href*='/user/profile']")]
          .slice(0, 40)
          .map((element) => ({
            href: element.getAttribute("href") ?? "",
            text: (element.textContent ?? "").trim().slice(0, 40),
            tag: element.tagName.toLowerCase(),
            cls: String(element.className).slice(0, 60),
          }));
      });

      const containers = await page.evaluate(() => {
        return [...document.querySelectorAll("div,section,ul")]
          .filter((element) => element.scrollHeight > element.clientHeight + 40)
          .slice(0, 10)
          .map((element) => ({
            cls: String(element.className).slice(0, 60),
            scrollHeight: element.scrollHeight,
            clientHeight: element.clientHeight,
          }));
      });

      const followCandidates = await page.evaluate(() => {
        const isSidebar = (element: Element): boolean =>
          Boolean(element.closest(".side-bar, [class*='side-bar']"));
        return [...document.querySelectorAll("div,span,a,button")]
          .filter((element) => {
            const text = (element.textContent ?? "").trim();
            return /^关注\s*\d*$/.test(text) || /^\d+\s*关注$/.test(text);
          })
          .slice(0, 12)
          .map((element) => {
            const rect = element.getBoundingClientRect();
            return {
              tag: element.tagName.toLowerCase(),
              cls: String(element.className).slice(0, 60),
              text: (element.textContent ?? "").trim().slice(0, 20),
              inSidebar: isSidebar(element),
              x: Math.round(rect.x),
              y: Math.round(rect.y),
            };
          });
      });

      const modalHtml = await page.evaluate(() => {
        const modal = document.querySelector(
          "[class*='modal'], [class*='dialog']",
        );
        return modal
          ? modal.innerHTML.replace(/\s+/g, " ").slice(0, 1_500)
          : null;
      });

      const bodyTextSample = (
        (await page.textContent("body").catch(() => "")) ?? ""
      )
        .replace(/\s+/g, " ")
        .slice(0, 400);
      const screenshotPath = await this.browser.screenshot(
        page,
        "debug-following",
      );

      return {
        url: page.url(),
        title: await page.title().catch(() => ""),
        profileId: resolved ?? null,
        sidebarMatches,
        tabMatches,
        clickedTab,
        urlAfterTabClick: page.url(),
        selectorCounts,
        links,
        containers,
        followCandidates,
        modalHtml,
        bodyTextSample,
        screenshotPath,
      };
    });
  }

  private async matchAll(
    page: Page,
    selectors: readonly string[],
    withText = false,
  ): Promise<Array<{ selector: string; count: number; text?: string | null }>> {
    const out: Array<{
      selector: string;
      count: number;
      text?: string | null;
    }> = [];
    for (const selector of selectors) {
      const locator = page.locator(selector);
      const count = await locator.count().catch(() => -1);
      if (!withText) {
        out.push({ selector, count });
        continue;
      }
      const text =
        count > 0
          ? await locator
              .first()
              .textContent({ timeout: 1_000 })
              .catch(() => null)
          : null;
      out.push({ selector, count, text: text?.trim().slice(0, 40) ?? null });
    }
    return out;
  }

  private async firstProfileId(page: Page): Promise<string | null> {
    for (const selector of ACCOUNT_PROFILE_LINK_SELECTORS) {
      const locator = page.locator(selector).first();
      if ((await locator.count().catch(() => 0)) === 0) {
        continue;
      }
      const href = await locator
        .getAttribute("href", { timeout: 1_000 })
        .catch(() => null);
      const match = href?.match(USER_PROFILE_ID_RE);
      if (match?.[1]) {
        return match[1];
      }
    }
    this.logger.warn("No signed-in sidebar link found");
    return null;
  }
}
