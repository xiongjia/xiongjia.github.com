import {
  Injectable,
  Logger,
  ServiceUnavailableException,
  type OnModuleDestroy,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import type { Cookie } from "playwright-core";
import { BrowserService } from "../browser/browser.service";
import { FlowService } from "../flows/flow.service";
import type { RunRecord } from "../run/run";

/** How long a verification result is trusted before the site is asked again. */
const VERIFY_TTL_MS = 60_000;
/** Session cookie Xiaohongshu sets once a scan succeeds. */
const SESSION_COOKIE = "web_session";
/** `/user/profile/<id>` — the id is the only stable handle we need. */
const USER_PROFILE_ID_RE = /\/user\/profile\/([0-9a-zA-Z]+)/;

/** On-disk session jar: cookies only, mode 0600, corrupt = "not logged in". */
interface CookieJar {
  savedAt: string;
  cookies: Cookie[];
}

async function readCookieJar(file: string): Promise<CookieJar | null> {
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

async function writeCookieJar(
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

function hasSession(jar: CookieJar | null): boolean {
  return Boolean(jar?.cookies.some((cookie) => cookie.name === SESSION_COOKIE));
}

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
 * Xiaohongshu session management: QR login, session state, logout.
 *
 * The page work lives in the two short login flows (`xhs-login-qr`,
 * `xhs-login-check`); this service owns what a flow should not: the PNG contract,
 * the 0600 cookie jar, the 60s verification cache and the `blocked` mapping.
 */
@Injectable()
export class XhsService implements OnModuleDestroy {
  private readonly logger = new Logger(XhsService.name);
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
    private readonly flows: FlowService,
  ) {}

  /** How long the login page may take to paint before we give up on it. */
  private get settleMs(): number {
    return this.config.get<number>("HARVEST_XHS_SETTLE_MS") ?? 8_000;
  }

  private get cookieFile(): string {
    return (
      this.config.get<string>("HARVEST_XHS_COOKIES") ??
      ".cache/xhs-cookies.json"
    );
  }

  /**
   * Produce the login QR as a PNG.
   *
   * The page work lives in `flows/xhs-login-qr.jsonc`; this method owns the HTTP
   * contract (a PNG body) and maps a failed run to a readable error. One run per
   * call keeps the code fresh — XHS expires it after a minute or so.
   */
  async qrCode(): Promise<{ png: Buffer; source: string }> {
    const { record } = await this.flows.submit("xhs-login-qr", {
      profile: this.flows.defaultProfile,
      waitMs: this.settleMs + 10_000,
    });

    if (record.state !== "succeeded") {
      throw new ServiceUnavailableException(
        describeFailure(record, "Could not render the login QR code"),
      );
    }

    const { buffer } = await this.flows.artifact(record.id, "qr.png");
    this.qrSource = screenshotSelector(record) ?? "viewport";
    return { png: buffer, source: this.qrSource };
  }

  async status(): Promise<LoginStatus> {
    await this.ensureSessionLoaded();
    const checkedAt = new Date().toISOString();
    const cookies = await this.browser.cookies();
    const cookieNames = cookies.map((cookie) => cookie.name);
    const jar = await readCookieJar(this.cookieFile);

    if (hasSession(jar) || cookieNames.includes(SESSION_COOKIE)) {
      const proof = await this.verifySavedSession();
      // Refresh the jar when the live context has the session (first poll after a
      // scan) so the 0600 copy stays importable for another profile or machine.
      const saved =
        jar && hasSession(jar)
          ? jar
          : cookies.length > 0
            ? await writeCookieJar(this.cookieFile, cookies)
            : jar;
      if (!jar || !hasSession(jar)) {
        this.logger.log(
          `Session saved to ${this.cookieFile}${proof.account ? ` for ${proof.account.nickname}` : ""}`,
        );
      }
      return {
        loggedIn: true,
        verified: proof.account !== null,
        blocked: proof.blocked,
        account: proof.account,
        cookieNames,
        qrSource: this.qrSource,
        savedAt: saved?.savedAt ?? null,
        checkedAt,
      };
    }

    return {
      loggedIn: false,
      verified: false,
      blocked: false,
      account: null,
      cookieNames,
      qrSource: this.qrSource,
      savedAt: null,
      checkedAt,
    };
  }

  /** Drop the session: clear cookies and the jar. */
  async logout(): Promise<void> {
    const context = await this.browser.getContext();
    await context.clearCookies();
    this.sessionLoaded = false;
    this.verified = undefined;
    this.qrSource = null;
    await writeCookieJar(this.cookieFile, []);
    this.logger.log("Session cleared");
  }

  async onModuleDestroy(): Promise<void> {
    this.verified = undefined;
  }

  /**
   * Prove the session by reading login-gated data.
   *
   * Cached for a minute: `/status` is meant to be polled, and every probe runs a
   * real flow.
   */
  private async verifySavedSession(): Promise<{
    account: XhsAccount | null;
    blocked: boolean;
  }> {
    const cached = this.verified;
    if (cached && Date.now() - cached.at < VERIFY_TTL_MS) {
      return { account: cached.account, blocked: cached.blocked };
    }

    const { record } = await this.flows.submit("xhs-login-check", {
      profile: this.flows.defaultProfile,
      waitMs: 25_000,
    });
    const proof = await this.proofOf(record);
    if (proof.blocked) {
      this.logger.warn("Risk-control page while verifying the saved session");
    } else if (!proof.account) {
      this.logger.warn(
        "Saved session did not expose the signed-in sidebar — cookie is stale",
      );
    }
    this.verified = { at: Date.now(), ...proof };
    return proof;
  }

  /** Output of a `xhs-login-check` run → the status payload's proof. */
  private async proofOf(record: RunRecord): Promise<{
    account: XhsAccount | null;
    blocked: boolean;
  }> {
    if (record.state !== "succeeded") {
      return { account: null, blocked: record.error?.code === "blocked" };
    }
    const output = await this.flows.output(record.id).catch(() => null);
    const nickname =
      typeof output?.nickname === "string" ? output.nickname.trim() : "";
    const href =
      typeof output?.profileHref === "string" ? output.profileHref : "";
    return {
      account: {
        nickname: nickname || "(unnamed)",
        userId: href.match(USER_PROFILE_ID_RE)?.[1] ?? null,
      },
      blocked: false,
    };
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
}

/** Which selector the QR screenshot actually used (`null` = viewport fallback). */
function screenshotSelector(record: RunRecord): string | null {
  const used = record.meta?.usedSelectors ?? {};
  const key = Object.keys(used)
    .filter((name) => name.endsWith(".screenshot"))
    .sort()[0];
  return key ? used[key] : null;
}

function describeFailure(record: RunRecord, prefix: string): string {
  const code = record.error?.code ?? record.state;
  const detail = record.error?.message ?? "no detail";
  return `${prefix} (${code}): ${detail}`;
}
