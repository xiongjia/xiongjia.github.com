/**
 * Xiaohongshu selectors, all in one place.
 *
 * The site re-skins its login modal regularly, so every entry is a list of
 * candidates tried in order. When a flow breaks, this file is the only one that
 * should need editing — `pnpm camoufox:download`-style fixes never apply here,
 * but `pnpm dev` + `curl` shows which candidate won via the response header.
 */
export const XHS_ORIGIN = "https://www.xiaohongshu.com";

/** Landing page: shows the QR login modal when the profile has no session. */
export const XHS_HOME = `${XHS_ORIGIN}/explore`;

/** Elements that render the login QR code, most specific first. */
export const QR_SELECTORS = [
  "img.qrcode-img",
  ".qrcode-img",
  ".qrcode img",
  ".login-container .qrcode",
  "canvas.qrcode",
  ".qrcode",
] as const;

/** Buttons that open the login modal from the home page. */
export const LOGIN_TRIGGER_SELECTORS = [
  "text=登录",
  ".login-btn",
  ".side-bar .user .login-btn",
  "button:has-text('登录')",
] as const;

/**
 * Xiaohongshu answers a risk-control page ("安全限制", error 300012) instead of
 * the site when it dislikes the source IP. No QR is rendered in that case, so it
 * must be reported as its own failure rather than "the selector changed".
 */
export const BLOCKED_PATTERNS = [/安全限制/, /IP存在风险/, /300012/] as const;

/** Text the login modal shows once its QR is on screen. */
export const QR_HINT_PATTERNS = [/扫码登录/, /二维码/] as const;

/**
 * Identity block in the left sidebar — rendered only for a signed-in user, which
 * makes it the cheapest proof that a session is real rather than a stale cookie.
 */
export const ACCOUNT_NICKNAME_SELECTORS = [
  ".user .name",
  ".side-bar .user .name",
  ".user .user-name",
  "[class*='user'] [class*='name']",
] as const;

/** Links to the signed-in user's own profile (carries the user id). */
export const ACCOUNT_PROFILE_LINK_SELECTORS = [
  ".user a[href*='/user/profile']",
  ".side-bar a[href*='/user/profile']",
  "a[href*='/user/profile/']",
] as const;

/**
 * Following panel, as rendered by the web app (verified against a live account):
 *
 *   div.xhs-relation-panel
 *     div.xhs-panel-header  > span.xhs-panel-tab (`.xhs-tab-label` 关注 / 粉丝)
 *     div.xhs-following-list > div.xhs-following-scroll
 *        div.xhs-relation-item  (avatar + .xhs-relation-name + .xhs-relation-desc)
 *
 * The items are **not** anchors, so there is no profile URL to read: the list has
 * to be scraped by class name. Keep the candidates in sync with the DOM above.
 */

/** Clickable "关注 N" counter on the profile header that opens the panel. */
export const FOLLOWING_TRIGGER_SELECTORS = [
  ".clickable:has-text('关注')",
  ".user-interactions .clickable:has-text('关注')",
  "div:has-text('关注') >> nth=0",
] as const;

/** The panel itself, once it is open. */
export const FOLLOWING_PANEL_SELECTOR = ".xhs-relation-panel";

/** Tab inside the panel that selects the following (关注) list. */
export const FOLLOWING_TAB_SELECTORS = [
  ".xhs-panel-tab:has-text('关注')",
  ".xhs-tab-label:text-is('关注')",
] as const;

/** The scrollable list container (not the window). */
export const FOLLOWING_SCROLL_SELECTORS = [
  ".xhs-following-scroll",
  ".xhs-relation-panel [class*='scroll']",
] as const;

/** One entry of the list. */
export const FOLLOWING_ITEM_SELECTOR = ".xhs-relation-item";

/** `/user/profile/<id>` — id is the only stable handle we need. */
export const USER_PROFILE_ID_RE = /\/user\/profile\/([0-9a-zA-Z]+)/;

/** Elements that only exist for a signed-in user (fallback login check). */
export const LOGGED_IN_SELECTORS = [
  ".user .name",
  ".side-bar .user a",
  ".user-avatar",
] as const;
