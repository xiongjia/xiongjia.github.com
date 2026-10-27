import { Injectable, Logger, type OnModuleDestroy } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import type { Page } from "playwright-core";
import { BrowserService } from "../browser/browser.service";
import {
  hasSession,
  readCookieJar,
  SESSION_COOKIE,
  writeCookieJar,
} from "./cookie.store";
import {
  ACCOUNT_NICKNAME_SELECTORS,
  ACCOUNT_PROFILE_LINK_SELECTORS,
  BLOCKED_PATTERNS,
  LOGIN_TRIGGER_SELECTORS,
  QR_SELECTORS,
  USER_PROFILE_ID_RE,
  XHS_HOME,
} from "./selectors";

const LOGIN_PAGE_KEY = "xhs-login";
/** How long a verification result is trusted before we look at the site again. */
const VERIFY_TTL_MS = 60_000;

/**
 * Data that only exists for a signed-in user.
 *
 * Deliberately tiny and non-personal: the nickname and the id that appear in the
 * signed-in sidebar. It is the proof that a session still works — a saved
 * `web_session` cookie alone can be stale, revoked, or belong to a logged-out
 * session, and would otherwise be reported as "logged in" forever.
 */
export interface XhsAccount {
  nickname: string;
  userId: string | null;
}

export interface LoginStatus {
  /** A session cookie exists (saved jar or the live browser). */
  loggedIn: boolean;
  /** Login-gated data was actually read back — the strong signal. */
  verified: boolean;
  /** Set when Xiaohongshu served its risk-control page instead of the site. */
  blocked: boolean;
  /** The proof itself: sidebar identity of the signed-in account. */
  account: XhsAccount | null;
  cookieNames: string[];
  qrSource: string | null;
  savedAt: string | null;
  checkedAt: string;
}

/**
 * QR login for Xiaohongshu.
 *
 * One long-lived page (`xhs-login`) keeps the QR alive between HTTP calls: the
 * user asks for the QR, scans it on the phone, and polls the status endpoint
 * until the session cookie shows up. The session then lands in a 0600 cookie
 * jar, and every later status call re-checks it against login-gated content.
 */
@Injectable()
export class XhsLoginService implements OnModuleDestroy {
  private readonly logger = new Logger(XhsLoginService.name);
  private qrSource: string | null = null;
  private sessionLoaded = false;
  private verified?: {
    at: number;
    account: XhsAccount | null;
    blocked: boolean;
  };

  constructor(
    private readonly browser: BrowserService,
    private readonly config: ConfigService,
  ) {}

  private get cookieFile(): string {
    return (
      this.config.get<string>("HARVEST_XHS_COOKIES") ??
      ".cache/xhs-cookies.json"
    );
  }

  /**
   * Open the login page (if needed) and return the QR code as a PNG buffer.
   *
   * Falls back to a viewport screenshot when no QR selector matches — better a
   * slightly wrong image than a blank failure while the site is re-skinned.
   */
  async qrCode(): Promise<{ png: Buffer; source: string }> {
    const page = await this.browser.persistentPage(LOGIN_PAGE_KEY);
    await this.gotoHome(page);
    // The risk-control redirect happens after the first paint, so give the page
    // a moment to either land on its error route or paint the QR.
    await this.settle(page);
    await this.assertNotBlocked(page);
    await this.openLoginModal(page);

    for (const selector of QR_SELECTORS) {
      const locator = page.locator(selector).first();
      if ((await locator.count()) === 0) {
        continue;
      }
      const png = await locator.screenshot();
      this.qrSource = selector;
      return { png, source: selector };
    }

    this.logger.warn("No QR selector matched — returning a page screenshot");
    this.qrSource = "viewport";
    return { png: await page.screenshot(), source: "viewport" };
  }

  async status(): Promise<LoginStatus> {
    await this.ensureSessionLoaded();
    const checkedAt = new Date().toISOString();

    const jar = await readCookieJar(this.cookieFile);
    if (hasSession(jar)) {
      const proof = await this.verifySavedSession();
      return {
        loggedIn: true,
        verified: proof.account !== null,
        blocked: proof.blocked,
        account: proof.account,
        cookieNames: (jar?.cookies ?? []).map((cookie) => cookie.name),
        qrSource: this.qrSource,
        savedAt: jar?.savedAt ?? null,
        checkedAt,
      };
    }

    // No saved session: the login page may already have one (user just scanned).
    const page = await this.browser.persistentPage(LOGIN_PAGE_KEY);
    const cookies = await this.browser.cookies();
    const scanned = cookies.some((cookie) => cookie.name === SESSION_COOKIE);
    if (scanned) {
      const account = await this.readAccount(page);
      const saved = await writeCookieJar(this.cookieFile, cookies);
      this.verified = { at: Date.now(), account, blocked: false };
      await this.browser.releasePage(LOGIN_PAGE_KEY);
      this.logger.log(
        `Session saved to ${this.cookieFile}${account ? ` for ${account.nickname}` : ""}`,
      );
      return {
        loggedIn: true,
        verified: account !== null,
        blocked: false,
        account,
        cookieNames: cookies.map((cookie) => cookie.name),
        qrSource: this.qrSource,
        savedAt: saved.savedAt,
        checkedAt,
      };
    }

    return {
      loggedIn: false,
      verified: false,
      blocked: page.isClosed() ? false : await this.isBlocked(page),
      account: null,
      cookieNames: cookies.map((cookie) => cookie.name),
      qrSource: page.isClosed() ? null : this.qrSource,
      savedAt: null,
      checkedAt,
    };
  }

  /** Drop the session: close the login page, clear cookies, delete the jar. */
  async logout(): Promise<void> {
    await this.browser.releasePage(LOGIN_PAGE_KEY);
    const context = await this.browser.getContext();
    await context.clearCookies();
    this.sessionLoaded = false;
    this.verified = undefined;
    this.qrSource = null;
    await writeCookieJar(this.cookieFile, []);
    this.logger.log("Session cleared");
  }

  async onModuleDestroy(): Promise<void> {
    await this.browser.releasePage(LOGIN_PAGE_KEY);
  }

  /** Seed the browser with a saved session, once per process. */
  private async ensureSessionLoaded(): Promise<void> {
    if (this.sessionLoaded) {
      return;
    }
    this.sessionLoaded = true;

    const jar = await readCookieJar(this.cookieFile);
    if (!hasSession(jar)) {
      return;
    }
    await this.browser.addCookies(jar?.cookies ?? []);
    this.logger.log(`Loaded saved session from ${this.cookieFile}`);
  }

  /**
   * Read login-gated data to prove the saved cookie is still good.
   *
   * Cached for a minute: the status endpoint is meant to be polled, and every
   * probe opens a real page.
   */
  private async verifySavedSession(): Promise<{
    account: XhsAccount | null;
    blocked: boolean;
  }> {
    const cached = this.verified;
    if (cached && Date.now() - cached.at < VERIFY_TTL_MS) {
      return { account: cached.account, blocked: cached.blocked };
    }

    const result = await this.browser.withPage(async (page) => {
      await page.goto(XHS_HOME, { waitUntil: "domcontentloaded" });
      if (await this.isBlocked(page)) {
        return { account: null, blocked: true };
      }
      return { account: await this.readAccount(page), blocked: false };
    });

    if (result.blocked) {
      this.logger.warn("Risk-control page while verifying the saved session");
    } else if (!result.account) {
      this.logger.warn(
        "Saved session did not expose the signed-in sidebar — cookie is stale",
      );
    }
    this.verified = { at: Date.now(), ...result };
    return result;
  }

  /** Sidebar identity of the signed-in user; `null` when it is not rendered. */
  private async readAccount(page: Page): Promise<XhsAccount | null> {
    let nickname = "";
    for (const selector of ACCOUNT_NICKNAME_SELECTORS) {
      const locator = page.locator(selector).first();
      if ((await locator.count()) === 0) {
        continue;
      }
      // Short timeout: a missing selector must not cost the default 15s.
      const text = await locator
        .textContent({ timeout: 1_000 })
        .catch(() => null);
      const trimmed = text?.trim() ?? "";
      if (trimmed.length > 0) {
        nickname = trimmed;
        break;
      }
    }

    let userId: string | null = null;
    for (const selector of ACCOUNT_PROFILE_LINK_SELECTORS) {
      const href = await page.getAttribute(selector, "href").catch(() => null);
      const match = href?.match(USER_PROFILE_ID_RE);
      if (match?.[1]) {
        userId = match[1];
        break;
      }
    }

    if (!nickname && !userId) {
      return null;
    }
    return { nickname: nickname || "(unnamed)", userId };
  }

  /**
   * Wait until the page either shows a QR or redirects to the risk-control page.
   *
   * Without this the first request races the redirect and screenshots the normal
   * page, which looks like "no QR selector matched" instead of "IP rejected".
   */
  private async settle(page: Page, timeoutMs?: number): Promise<void> {
    const budget =
      timeoutMs ?? this.config.get<number>("HARVEST_XHS_SETTLE_MS") ?? 8_000;
    const deadline = Date.now() + budget;
    while (Date.now() < deadline) {
      if (await this.isBlocked(page)) {
        return;
      }
      for (const selector of QR_SELECTORS) {
        if ((await page.locator(selector).first().count()) > 0) {
          return;
        }
      }
      await page.waitForTimeout(500);
    }
  }

  /** Risk-control pages are an environment problem: surface them loudly. */
  private async assertNotBlocked(page: Page): Promise<void> {
    if (await this.isBlocked(page)) {
      throw new Error(
        "Xiaohongshu served its risk-control page (安全限制 / 300012) instead of the site: " +
          "this IP is rejected, so no QR code can be rendered. Retry from another network " +
          "or through a residential proxy (HARVEST_PROXY is not wired yet).",
      );
    }
  }

  private async isBlocked(page: Page): Promise<boolean> {
    // Most reliable signal: the site redirects to its error page, e.g.
    // /website-login/error?...error_code=300012&error_msg=IP存在风险
    if (/website-login\/error|error_code=300012/.test(page.url())) {
      return true;
    }
    const body = (await page.textContent("body").catch(() => null)) ?? "";
    const title = await page.title().catch(() => "");
    const haystack = `${title} ${body}`;
    return BLOCKED_PATTERNS.some((pattern) => pattern.test(haystack));
  }

  private async gotoHome(page: Page): Promise<void> {
    const current = page.url();
    if (
      current.startsWith(XHS_HOME) ||
      current.startsWith("https://www.xiaohongshu.com")
    ) {
      return;
    }
    await page.goto(XHS_HOME, { waitUntil: "domcontentloaded" });
  }

  /** The QR only renders inside the login modal; click the trigger if needed. */
  private async openLoginModal(page: Page): Promise<void> {
    const qrVisible = async (): Promise<boolean> => {
      for (const selector of QR_SELECTORS) {
        if ((await page.locator(selector).first().count()) > 0) {
          return true;
        }
      }
      return false;
    };

    if (await qrVisible()) {
      return;
    }

    for (const selector of LOGIN_TRIGGER_SELECTORS) {
      const trigger = page.locator(selector).first();
      if ((await trigger.count()) === 0) {
        continue;
      }
      await trigger.click({ timeout: 5_000 }).catch(() => undefined);
      await page.waitForTimeout(500);
      if (await qrVisible()) {
        return;
      }
    }

    // Give a slow first paint one more chance before falling back.
    await page.waitForTimeout(1_000);
  }
}
