import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { Page } from "playwright-core";
import { BrowserService } from "../browser/browser.service";
import { SESSION_COOKIE } from "./cookie.store";
import {
  ACCOUNT_PROFILE_LINK_SELECTORS,
  FOLLOWING_ITEM_SELECTOR,
  FOLLOWING_PANEL_SELECTOR,
  FOLLOWING_SCROLL_SELECTORS,
  FOLLOWING_TAB_SELECTORS,
  FOLLOWING_TRIGGER_SELECTORS,
  USER_PROFILE_ID_RE,
  XHS_HOME,
} from "./selectors";
import {
  FollowItem,
  FollowRow,
  toFollowItem,
  toJsonl,
  uniqueFollowItems,
} from "./following";

export interface FollowingResult {
  /** Signed-in account the list belongs to. */
  profileId: string | null;
  count: number;
  items: FollowItem[];
  /** Selector that opened the panel, and how many rows the DOM held. */
  triggerUsed: string | null;
  rowsSeen: number;
  outputPath: string;
  elapsedMs: number;
}

/**
 * Collects the accounts this account follows (关注).
 *
 * Verified against the live web app: the list lives in a panel
 * (`.xhs-relation-panel`) whose rows are plain divs — nickname, description and
 * avatar, **no profile link**. Scrolling therefore has to happen on the panel's
 * own scroll container, not on the window.
 */
@Injectable()
export class XhsFollowingService {
  private readonly logger = new Logger(XhsFollowingService.name);

  constructor(
    private readonly browser: BrowserService,
    private readonly config: ConfigService,
  ) {}

  async collect(
    options: { profileId?: string; limit?: number; scrolls?: number } = {},
  ): Promise<FollowingResult> {
    await this.assertLoggedIn();
    const limit = options.limit ?? 500;
    const scrolls = options.scrolls ?? 10;
    const startedAt = Date.now();

    const run = await this.browser.withPage(async (page) => {
      const selfId = options.profileId ?? (await this.readOwnProfileId(page));
      await this.openProfile(page, selfId);

      const triggerUsed = await this.openFollowingPanel(page);
      if (!triggerUsed) {
        return {
          items: [] as FollowItem[],
          rowsSeen: 0,
          triggerUsed,
          profileId: selfId,
        };
      }

      const collected = new Map<string, FollowItem>();
      let rowsSeen = 0;

      for (let round = 0; round <= scrolls; round += 1) {
        const rows = await this.readRows(page);
        rowsSeen = Math.max(rowsSeen, rows.length);
        for (const item of uniqueFollowItems(rows.map(toFollowItem))) {
          if (collected.size < limit) {
            collected.set(`${item.nickname}|${item.avatarUrl ?? ""}`, item);
          }
        }
        if (collected.size >= limit || rows.length === 0) {
          break;
        }
        const grew = await this.scrollList(page);
        if (!grew) {
          break;
        }
        await page.waitForTimeout(900);
      }

      return {
        items: [...collected.values()],
        rowsSeen,
        triggerUsed,
        profileId: selfId,
      };
    });

    const outputPath = await this.save(run.items, run.profileId);
    if (run.items.length === 0) {
      this.logger.warn(
        `No following rows found (trigger=${run.triggerUsed ?? "none"}, rows=${run.rowsSeen}) — ` +
          "GET /api/v1/xhs/debug/following to see the page",
      );
    } else {
      this.logger.log(
        `Collected ${run.items.length} following entries → ${outputPath}`,
      );
    }

    return {
      profileId: run.profileId,
      count: run.items.length,
      items: run.items,
      triggerUsed: run.triggerUsed,
      rowsSeen: run.rowsSeen,
      outputPath,
      elapsedMs: Date.now() - startedAt,
    };
  }

  /** Refuse to scrape without a session. */
  private async assertLoggedIn(): Promise<void> {
    const cookies = await this.browser.cookies();
    if (cookies.some((cookie) => cookie.name === SESSION_COOKIE)) {
      return;
    }
    throw new Error(
      "no Xiaohongshu session — call GET /api/v1/xhs/login/qrcode, scan it, then retry",
    );
  }

  /** Own profile id, read from the signed-in sidebar. */
  private async readOwnProfileId(page: Page): Promise<string | null> {
    await page.goto(XHS_HOME, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1_500);
    for (const selector of ACCOUNT_PROFILE_LINK_SELECTORS) {
      const locator = page.locator(selector).first();
      if ((await locator.count()) === 0) {
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
    this.logger.warn(
      "No signed-in sidebar link found — pass ?profileId= explicitly",
    );
    return null;
  }

  private async openProfile(
    page: Page,
    profileId: string | null,
  ): Promise<void> {
    if (profileId) {
      await page.goto(`https://www.xiaohongshu.com/user/profile/${profileId}`, {
        waitUntil: "domcontentloaded",
      });
    }
    await page.waitForTimeout(2_000);
  }

  /**
   * Click the "关注 N" counter and wait for the panel; returns the selector used.
   *
   * The counter is a `div.clickable`, not a tab — and the panel starts on the
   * 关注 tab already, so clicking a tab is only a fallback.
   */
  private async openFollowingPanel(page: Page): Promise<string | null> {
    for (const selector of FOLLOWING_TRIGGER_SELECTORS) {
      const trigger = page.locator(selector).first();
      if ((await trigger.count().catch(() => 0)) === 0) {
        continue;
      }
      await trigger.click({ timeout: 5_000 }).catch(() => undefined);
      const opened = await page
        .waitForSelector(FOLLOWING_PANEL_SELECTOR, { timeout: 8_000 })
        .catch(() => null);
      if (!opened) {
        continue;
      }
      // Make sure the 关注 tab is the active one (not 粉丝).
      for (const tab of FOLLOWING_TAB_SELECTORS) {
        const locator = page.locator(tab).first();
        if ((await locator.count().catch(() => 0)) > 0) {
          await locator.click({ timeout: 3_000 }).catch(() => undefined);
          break;
        }
      }
      await page.waitForTimeout(1_200);
      return selector;
    }
    return null;
  }

  /** Rows currently rendered inside the panel. */
  private async readRows(page: Page): Promise<FollowRow[]> {
    return page.evaluate((itemSelector) => {
      return [...document.querySelectorAll(itemSelector)]
        .slice(0, 2_000)
        .map((element) => {
          const name = element.querySelector("[class*='relation-name']");
          const desc = element.querySelector("[class*='relation-desc']");
          const avatar = element.querySelector("img");
          return {
            name: name?.textContent ?? null,
            desc: desc?.textContent ?? null,
            avatar: avatar?.getAttribute("src") ?? null,
          };
        });
    }, FOLLOWING_ITEM_SELECTOR);
  }

  /** Scroll the panel's container; returns false when it is already at the end. */
  private async scrollList(page: Page): Promise<boolean> {
    return page.evaluate(
      (selectors) => {
        const isScrollable = (element: Element): element is HTMLElement => {
          const node = element as HTMLElement;
          return node.scrollHeight > node.clientHeight + 20;
        };
        let scroller: HTMLElement | null = null;
        for (const selector of selectors) {
          const candidate = document.querySelector(selector);
          if (candidate && isScrollable(candidate)) {
            scroller = candidate as HTMLElement;
            break;
          }
        }
        scroller ??= document.querySelector(
          "[class*='xhs-relation-panel']",
        ) as HTMLElement | null;
        if (!scroller) {
          return false;
        }
        const before = scroller.scrollTop;
        scroller.scrollBy(0, 1_200);
        return scroller.scrollTop !== before;
      },
      FOLLOWING_SCROLL_SELECTORS as unknown as string[],
    );
  }

  /** Append a timestamped snapshot under `data/`. */
  private async save(
    items: FollowItem[],
    profileId: string | null,
  ): Promise<string> {
    const dataDir = this.config.get<string>("HARVEST_DATA_DIR") ?? "data";
    await mkdir(dataDir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const path = join(dataDir, `xhs-following-${stamp}.jsonl`);
    const header = `# profile=${profileId ?? "unknown"} count=${items.length} at=${stamp}\n`;
    await writeFile(path, header + toJsonl(items), "utf8");
    return path;
  }
}
