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
import { isTerminal, type RunRecord } from "../run/run";

/** How long a verification result is trusted before the site is asked again. */
const VERIFY_TTL_MS = 60_000;
/**
 * Session cookie Xiaohongshu sets once a scan succeeds — **and for guests as
 * well**, in the first seconds of the very first page load. It is a hint, never
 * a proof: only login-gated data is.
 */
const SESSION_COOKIE = "web_session";
/** `/user/profile/<id>` — the id is the only stable handle we need. */
const USER_PROFILE_ID_RE = /\/user\/profile\/([0-9a-zA-Z]+)/;
/** Keeps a QR page open until the scan lands (see `flows/xhs-login-scan.jsonc`). */
const SCAN_FLOW = "xhs-login-scan";
/** Reads login-gated data; the proof that a session still works. */
const CHECK_FLOW = "xhs-login-check";
/** Artifact the login page writes on its first screenshot. */
const QR_ARTIFACT = "qr.png";
/** How often the QR artifact is polled while the login page paints. */
const QR_POLL_MS = 400;
/** How often the open scan run is checked so a landed scan writes the jar. */
const SCAN_WATCH_MS = 2_000;

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
 * `web_session` cookie alone can be stale, revoked, or the guest cookie every
 * anonymous visitor gets, and would otherwise be reported as "logged in" forever.
 */
export interface XhsAccount {
  nickname: string;
  userId: string | null;
}

/**
 * Where the session stands, in one word.
 *
 * - `anonymous` — no session cookie at all;
 * - `waiting-scan` — a login page is open with a QR on it, nothing scanned yet;
 * - `verified` — login-gated data was read back (the only "really logged in");
 * - `stale` — a session cookie exists but the site no longer honours it;
 * - `blocked` — Xiaohongshu served its risk-control page instead of the site.
 */
export type LoginPhase =
  "anonymous" | "waiting-scan" | "verified" | "stale" | "blocked";

export interface LoginStatus {
  /** True only for `phase: "verified"` — a scan that really landed. */
  loggedIn: boolean;
  /** Same signal, kept because it is the honest name for it. */
  verified: boolean;
  phase: LoginPhase;
  /** A `web_session` cookie exists. Guests get one too: not a login. */
  sessionCookie: boolean;
  /** Set when Xiaohongshu served its risk-control page instead of the site. */
  blocked: boolean;
  /** The proof itself: sidebar identity of the signed-in account. */
  account: XhsAccount | null;
  cookieNames: string[];
  /** Selector the QR screenshot used (`null` = unknown or viewport fallback). */
  qrSource: string | null;
  /** Run keeping a QR page open, if one is waiting for a scan. */
  loginRunId: string | null;
  /** When the jar copy on disk was written. */
  savedAt: string | null;
  checkedAt: string;
}

/**
 * Xiaohongshu session management: QR login, session state, logout.
 *
 * The page work lives in the flows (`xhs-login-scan`, `xhs-login-check`); this
 * service owns what a flow should not: the PNG contract, the keep-a-page-open
 * run, the 0600 cookie jar, the 60s verification cache and the phase mapping.
 *
 * The one rule that decides the whole design: **the login page is the login**.
 * XHS completes a scan inside the page that is polling the code, so a run that
 * screenshots the QR and exits can never produce a session — the page has to stay
 * on screen until the scan lands. Hence two calls, one run:
 *
 * `GET /login/qrcode` → starts `xhs-login-scan`, answers the PNG as soon as it
 * exists and leaves the run going; `GET /login/status` follows that same run and,
 * on success, copies the cookies into the jar. Nothing else has to poll the site.
 */
@Injectable()
export class XhsService implements OnModuleDestroy {
  private readonly logger = new Logger(XhsService.name);
  private qrSource: string | null = null;
  private sessionLoaded = false;
  /** The login run that is keeping a QR page alive, if any. */
  private scan?: { runId: string };
  /** Polls `scan` so a scan that lands is harvested without a `status` call. */
  private watcher?: NodeJS.Timeout;
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

  /** How long to wait for the QR to be painted before answering 503. */
  private get qrWaitMs(): number {
    return this.config.get<number>("HARVEST_XHS_QR_WAIT_MS") ?? 60_000;
  }

  private get cookieFile(): string {
    return (
      this.config.get<string>("HARVEST_XHS_COOKIES") ??
      ".cache/xhs-cookies.json"
    );
  }

  /**
   * Produce the login QR as a PNG **and keep the page that made it alive**.
   *
   * The run is not awaited: `xhs-login-scan` stays on the page until the sidebar
   * identity appears (≤ 3 min), which is the only window in which a scan can
   * land. This method returns as soon as `artifacts/qr.png` exists; `status`
   * follows the same run and turns it into a verified session.
   */
  async qrCode(): Promise<{
    png: Buffer;
    runId: string;
    source: string | null;
  }> {
    // A new code always means "forget the previous page": two live QR pages would
    // race for the same account and hold two browser pages open.
    await this.cancelScan("a newer QR code replaced it");
    this.qrSource = null;

    const { record } = await this.flows.submit(SCAN_FLOW, {
      profile: this.flows.defaultProfile,
    });
    this.scan = { runId: record.id };
    this.watchScan();
    const png = await this.awaitQr(record.id);
    return { png, runId: record.id, source: this.qrSource };
  }

  async status(): Promise<LoginStatus> {
    const checkedAt = new Date().toISOString();

    // While a QR page is open it is the only thing that can apply a scan, so the
    // run — not the cookie jar — is the answer.
    const scanning = await this.scanStatus(checkedAt);
    if (scanning) {
      return scanning;
    }

    await this.ensureSessionLoaded();
    const jar = await readCookieJar(this.cookieFile);
    const cookies = await this.currentCookies(jar);
    const cookieNames = [...new Set(cookies.map((cookie) => cookie.name))];

    if (!cookieNames.includes(SESSION_COOKIE)) {
      return this.report({ phase: "anonymous", cookieNames, checkedAt });
    }

    const proof = await this.verifySavedSession();
    // Refresh the jar whenever the live context is the better copy, so the 0600
    // file stays importable for another profile or machine.
    const saved =
      jar && hasSession(jar) ? jar : await this.persistSession(cookies);
    if (!jar || !hasSession(jar)) {
      this.logger.log(
        `Session saved to ${this.cookieFile}${proof.account ? ` for ${proof.account.nickname}` : ""}`,
      );
    }

    return this.report({
      phase: proof.blocked ? "blocked" : proof.account ? "verified" : "stale",
      account: proof.account,
      blocked: proof.blocked,
      cookieNames,
      savedAt: saved?.savedAt ?? null,
      checkedAt,
    });
  }

  /** Drop the session: cancel a pending scan, clear cookies and the jar. */
  async logout(): Promise<void> {
    await this.cancelScan("the session was cleared");
    const context = await this.browser.getContext();
    await context.clearCookies();
    this.sessionLoaded = false;
    this.verified = undefined;
    this.qrSource = null;
    await writeCookieJar(this.cookieFile, []);
    this.logger.log("Session cleared");
  }

  async onModuleDestroy(): Promise<void> {
    this.stopWatch();
    this.scan = undefined;
    this.verified = undefined;
  }

  /**
   * Harvest a finished scan without waiting for a `/status` poll.
   *
   * The scan is the one event nobody can be relied on to poll: the caller scanned
   * the code and moved on (often straight to `xhs-following`), which used to leave
   * the jar at whatever the last write was — an empty one after a `DELETE
   * /xhs/login`. A 2s watcher over the run writes the jar the moment the scan
   * lands, and `status` then reads the state instead of producing it.
   */
  private watchScan(): void {
    this.stopWatch();
    if (!this.scan) {
      return;
    }
    const timer = setInterval(() => {
      void this.harvestScan().catch(() => undefined);
    }, SCAN_WATCH_MS);
    // Never keep the process alive just to watch a login page.
    timer.unref();
    this.watcher = timer;
  }

  private stopWatch(): void {
    if (this.watcher) {
      clearInterval(this.watcher);
      this.watcher = undefined;
    }
  }

  /** Watcher body: settle the scan run (same code path as a `status` poll). */
  private async harvestScan(): Promise<void> {
    if (!this.scan) {
      this.stopWatch();
      return;
    }
    const record = await this.flows.get(this.scan.runId).catch(() => null);
    if (record && !isTerminal(record.state)) {
      return;
    }
    // Finished (or gone): let `scanStatus` do the work — jar included — and stop.
    this.stopWatch();
    await this.scanStatus(new Date().toISOString());
  }

  /**
   * Wait for the run's QR artifact.
   *
   * The artifact is written by the flow's first screenshot, seconds after the
   * page loads (plus the flow's throttle). Polling the file is what separates
   * "the code is ready" from "the scan is done" — the run keeps going either way.
   */
  private async awaitQr(runId: string): Promise<Buffer> {
    const deadline = Date.now() + this.qrWaitMs;
    for (;;) {
      const artifact = await this.flows
        .artifact(runId, QR_ARTIFACT)
        .catch(() => null);
      if (artifact) {
        // Only a finished run recorded which selector won.
        const record = await this.flows.get(runId).catch(() => null);
        this.qrSource = record ? screenshotSelector(record) : null;
        return artifact.buffer;
      }

      const record = await this.flows.get(runId).catch(() => null);
      if (!record || isTerminal(record.state)) {
        this.scan = undefined;
        throw new ServiceUnavailableException(
          describeFailure(record, "Could not render the login QR code"),
        );
      }
      if (Date.now() >= deadline) {
        await this.cancelScan("it never produced a QR code");
        throw new ServiceUnavailableException(
          `the login page produced no QR code within ${this.qrWaitMs}ms (run ${runId} is still ${record.state}) — raise HARVEST_XHS_QR_WAIT_MS when the engine launch or the flow throttle is slower than that`,
        );
      }
      await sleep(QR_POLL_MS);
    }
  }

  /**
   * Follow the pending login run.
   *
   * Returns a payload for `waiting-scan`, and for the verification the finished
   * run just produced. `null` means "nothing to follow any more" — a failed scan
   * is not an error of `status`: the scan may have landed a moment after the page
   * closed, so the cookie path still gets a say.
   */
  private async scanStatus(checkedAt: string): Promise<LoginStatus | null> {
    const scan = this.scan;
    if (!scan) {
      return null;
    }

    const record = await this.flows.get(scan.runId).catch(() => null);
    if (!record) {
      this.scan = undefined;
      return null;
    }

    if (!isTerminal(record.state)) {
      return this.report({
        phase: "waiting-scan",
        checkedAt,
        loginRunId: scan.runId,
      });
    }

    this.scan = undefined;
    if (record.state !== "succeeded") {
      this.logger.warn(
        `Login run ${record.id} ended ${record.state} (${record.error?.code ?? "no code"}); falling back to the saved session`,
      );
      return null;
    }

    const proof = await this.proofOf(record);
    this.verified = { at: Date.now(), ...proof };
    const saved = await this.persistSession();
    this.logger.log(
      `Scanned login confirmed${proof.account ? ` for ${proof.account.nickname}` : ""} — session kept in the browser profile and in ${this.cookieFile}`,
    );
    return this.report({
      phase: proof.account ? "verified" : "stale",
      account: proof.account,
      blocked: proof.blocked,
      cookieNames: saved?.cookies.map((cookie) => cookie.name) ?? [],
      savedAt: saved?.savedAt ?? null,
      checkedAt,
    });
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

    const { record } = await this.flows.submit(CHECK_FLOW, {
      profile: this.flows.defaultProfile,
      waitMs: 25_000,
    });
    const proof = await this.proofOf(record);
    if (proof.blocked) {
      this.logger.warn("Risk-control page while verifying the saved session");
    } else if (!proof.account) {
      this.logger.warn(
        "Saved session did not expose the signed-in sidebar — cookie is stale (a guest web_session looks exactly like this)",
      );
    }
    this.verified = { at: Date.now(), ...proof };
    return proof;
  }

  /** Output of a scan/check run → the status payload's proof. */
  private async proofOf(record: RunRecord): Promise<{
    account: XhsAccount | null;
    blocked: boolean;
  }> {
    if (record.state !== "succeeded") {
      return {
        account: null,
        blocked: record.error?.code === "blocked",
      };
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

  /**
   * Cookies of the live browser, or the jar when the context cannot answer.
   *
   * The profile directory is the truth and the jar is only a copy, so this may
   * launch a browser: an empty or stale jar must never hide a session the profile
   * still holds (that is how "logged in, but `status` says anonymous" happens after
   * a hard kill or a logout-then-login sequence). Contexts stay warm, so only the
   * first poll pays the launch.
   */
  private async currentCookies(jar: CookieJar | null): Promise<Cookie[]> {
    return this.browser.cookies().catch(() => jar?.cookies ?? []);
  }

  /** Copy the live context's cookies into the 0600 jar (portable session). */
  private async persistSession(cookies?: Cookie[]): Promise<CookieJar | null> {
    const live = cookies ?? (await this.browser.cookies().catch(() => []));
    if (live.length === 0) {
      return null;
    }
    try {
      return await writeCookieJar(this.cookieFile, live);
    } catch (error) {
      this.logger.warn(
        `Could not write the session jar ${this.cookieFile}: ${message(error)}`,
      );
      return null;
    }
  }

  /** Stop the pending login run; its page is closed by the run itself. */
  private async cancelScan(reason: string): Promise<void> {
    const scan = this.scan;
    if (!scan) {
      return;
    }
    this.scan = undefined;
    this.stopWatch();
    this.logger.log(`Cancelling login run ${scan.runId} (${reason})`);
    await this.flows.cancel(scan.runId).catch(() => undefined);
  }

  /** One status payload; `loggedIn` is never inferred from a cookie. */
  private report(args: {
    phase: LoginPhase;
    account?: XhsAccount | null;
    blocked?: boolean;
    cookieNames?: string[];
    savedAt?: string | null;
    checkedAt: string;
    loginRunId?: string | null;
  }): LoginStatus {
    const account = args.account ?? null;
    const cookieNames = args.cookieNames ?? [];
    return {
      loggedIn: account !== null,
      verified: account !== null,
      phase: args.phase,
      sessionCookie: cookieNames.includes(SESSION_COOKIE),
      blocked: args.blocked ?? false,
      account,
      cookieNames,
      qrSource: this.qrSource,
      loginRunId: args.loginRunId ?? this.scan?.runId ?? null,
      savedAt: args.savedAt ?? null,
      checkedAt: args.checkedAt,
    };
  }
}

/** Which selector the QR screenshot actually used (`null` = unknown). */
function screenshotSelector(record: RunRecord): string | null {
  const used = record.meta?.usedSelectors ?? {};
  const key = Object.keys(used)
    .filter((name) => name.endsWith(".screenshot"))
    .sort()[0];
  return key ? used[key] : null;
}

function describeFailure(record: RunRecord | null, prefix: string): string {
  if (!record) {
    return `${prefix}: the run disappeared before writing an artifact`;
  }
  const code = record.error?.code ?? record.state;
  const detail = record.error?.message ?? "no detail";
  return `${prefix} (${code}): ${detail}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
