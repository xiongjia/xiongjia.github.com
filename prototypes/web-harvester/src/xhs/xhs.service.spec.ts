import { ServiceUnavailableException } from "@nestjs/common";
import type { ConfigService } from "@nestjs/config";
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
import type { Cookie } from "playwright-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BrowserService, OpenContext } from "../browser/browser.service";
import type { FlowService } from "../flows/flow.service";
import type { RunRecord } from "../run/run";
import type { LoginStatus } from "./xhs.service";
import { XhsService } from "./xhs.service";

const PNG = Buffer.from("fake-png");
/** Duplicated on purpose: the service keeps it module-private. */
const SESSION_COOKIE = "web_session";
const SCAN_FLOW = "xhs-login-scan";
const CHECK_FLOW = "xhs-login-check";

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

function run(flow: string, overrides: Partial<RunRecord> = {}): RunRecord {
  return {
    id: `run-${flow}`,
    flow,
    profile: "main",
    state: "succeeded",
    createdAt: "2026-01-01T00:00:00.000Z",
    startedAt: "2026-01-01T00:00:01.000Z",
    finishedAt: "2026-01-01T00:00:02.000Z",
    input: {},
    meta: null,
    error: null,
    ...overrides,
  };
}

/** A login page that is still open: state stays `running` until the scan lands. */
function scanning(flow = SCAN_FLOW): RunRecord {
  return run(flow, {
    state: "running",
    finishedAt: null,
    meta: {
      url: "https://www.xiaohongshu.com/explore",
      userAgent: "",
      usedSelectors: {},
      screenshots: {},
      steps: [],
    },
  });
}

interface FlowOptions {
  runs?: Record<string, RunRecord>;
  output?: Record<string, unknown> | null;
  /** Artifact failures before the QR exists, e.g. 2 = "not written yet". */
  artifacts?: number;
}

function makeFlows(options: FlowOptions = {}) {
  let misses = options.artifacts ?? 0;
  const submit = vi.fn(async (name: string) => ({
    record: options.runs?.[name] ?? run(name),
    settled: true,
  }));
  const get = vi.fn(async (id: string) => {
    const runs = options.runs ?? {};
    // Lookups arrive both ways: by flow name (from `submit`) and by run id (from
    // `status`, which only knows the id it stored).
    return (
      Object.values(runs).find((record) => record.id === id) ?? runs[id] ?? null
    );
  });
  const output = vi.fn(async () => options.output ?? {});
  const artifact = vi.fn(async () => {
    if (misses > 0) {
      misses -= 1;
      throw new Error("no such artifact");
    }
    return { buffer: PNG, contentType: "image/png" };
  });
  const cancel = vi.fn(async (id: string) => run(id));
  const flows = {
    submit,
    get,
    output,
    artifact,
    cancel,
    defaultProfile: "main",
  } as unknown as FlowService;
  return { flows, submit, get, output, artifact, cancel };
}

function makeBrowser(cookies: Cookie[] = [], open = false) {
  const addCookies = vi.fn(async () => undefined);
  const clearCookies = vi.fn(async () => undefined);
  const contexts: OpenContext[] = open
    ? [{ profile: "main", engine: "mock", idleMs: 0, busy: false }]
    : [];
  const browser = {
    cookies: vi.fn(async () => cookies),
    addCookies,
    status: vi.fn(() => contexts),
    getContext: vi.fn(async () => ({ clearCookies })),
  } as unknown as BrowserService;
  return {
    browser,
    addCookies,
    clearCookies,
    setCookies: (next: Cookie[]) => cookies.splice(0, cookies.length, ...next),
  };
}

function makeConfig(
  cookieFile: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    get: (key: string) => {
      if (key === "HARVEST_XHS_COOKIES") return cookieFile;
      if (key === "HARVEST_XHS_QR_WAIT_MS") return 2_000;
      return overrides[key];
    },
  } as unknown as ConfigService;
}

describe("XhsService", () => {
  let dir: string;
  let cookieFile: string;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "xhs-service-"));
    cookieFile = join(dir, "cookies.json");
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  function make(
    options: {
      cookies?: Cookie[];
      open?: boolean;
      flows?: FlowOptions;
      qrWaitMs?: number;
    } = {},
  ): {
    service: XhsService;
    submit: ReturnType<typeof makeFlows>["submit"];
    artifact: ReturnType<typeof makeFlows>["artifact"];
    cancel: ReturnType<typeof makeFlows>["cancel"];
    browser: ReturnType<typeof makeBrowser>;
  } {
    const browser = makeBrowser(options.cookies ?? [], options.open ?? false);
    const flows = makeFlows(options.flows);
    const service = new XhsService(
      browser.browser,
      makeConfig(
        cookieFile,
        options.qrWaitMs === undefined
          ? {}
          : { HARVEST_XHS_QR_WAIT_MS: options.qrWaitMs },
      ),
      flows.flows,
    );
    return {
      service,
      submit: flows.submit,
      artifact: flows.artifact,
      cancel: flows.cancel,
      browser,
    };
  }

  async function writeJar(cookies: Cookie[]) {
    // `status` writes the jar itself; seed one by writing the same shape.
    await writeFile(
      cookieFile,
      `${JSON.stringify({ savedAt: "2026-01-01T00:00:00.000Z", cookies }, null, 2)}\n`,
      { mode: 0o600 },
    );
  }

  /** Fill the scan artifact so `qrCode` answers, then report a finished run. */
  function scanned(
    state: RunRecord["state"] = "succeeded",
    error: RunRecord["error"] = null,
  ): RunRecord {
    return run(SCAN_FLOW, {
      id: `run-${SCAN_FLOW}`,
      state,
      error,
      meta: {
        url: "https://www.xiaohongshu.com/explore",
        userAgent: "",
        usedSelectors: { "4.1.screenshot": "img.qrcode-img" },
        screenshots: { qr: "artifacts/qr.png" },
        steps: [],
      },
    });
  }

  describe("qrCode", () => {
    it("starts the long scan flow and answers the QR once the artifact exists", async () => {
      const { service, submit, artifact } = make({
        flows: { runs: { "run-xhs-login-scan": scanning() } },
      });

      const qr = await service.qrCode();

      expect(qr).toMatchObject({ png: PNG, runId: "run-xhs-login-scan" });
      // No `waitMs`: the run must outlive the response, that is the scan window.
      expect(submit).toHaveBeenCalledWith(SCAN_FLOW, { profile: "main" });
      expect(artifact).toHaveBeenCalledWith("run-xhs-login-scan", "qr.png");
    });

    it("reports the selector a finished run used", async () => {
      const { service } = make({
        flows: { runs: { "run-xhs-login-scan": scanned() } },
      });

      expect((await service.qrCode()).source).toBe("img.qrcode-img");
    });

    it("reports an unknown source while the page is still painting", async () => {
      const { service } = make({
        flows: { runs: { "run-xhs-login-scan": scanning() }, artifacts: 1 },
      });

      expect((await service.qrCode()).source).toBeNull();
    });

    it("maps a failed run to 503 with its reason", async () => {
      const { service } = make({
        flows: {
          runs: {
            "run-xhs-login-scan": scanned("failed", {
              code: "blocked",
              message: "IP存在风险",
            }),
          },
          artifacts: 100,
        },
      });

      const error = await service.qrCode().catch((caught: unknown) => caught);

      expect(error).toBeInstanceOf(ServiceUnavailableException);
      expect((error as ServiceUnavailableException).message).toContain(
        "blocked",
      );
    });

    it("cancels the run and 503s when no QR ever appears", async () => {
      const { service, cancel } = make({
        flows: {
          runs: { "run-xhs-login-scan": scanning() },
          artifacts: 100,
        },
        qrWaitMs: 1_000,
      });

      const error = await service.qrCode().catch((caught: unknown) => caught);

      expect(error).toBeInstanceOf(ServiceUnavailableException);
      expect((error as ServiceUnavailableException).message).toContain(
        "produced no QR code",
      );
      expect(cancel).toHaveBeenCalledWith("run-xhs-login-scan");
    });

    it("cancels the previous QR page before starting a new one", async () => {
      const { service, cancel } = make({
        flows: { runs: { "run-xhs-login-scan": scanning() } },
      });

      await service.qrCode();
      await service.qrCode();

      expect(cancel).toHaveBeenCalledTimes(1);
    });
  });

  describe("status", () => {
    it("reports a live QR page as waiting-scan, not as logged in", async () => {
      const { service } = make({
        flows: { runs: { "run-xhs-login-scan": scanning() } },
      });
      await service.qrCode();

      const status: LoginStatus = await service.status();

      expect(status).toMatchObject({
        phase: "waiting-scan",
        loggedIn: false,
        verified: false,
        sessionCookie: false,
        account: null,
        loginRunId: "run-xhs-login-scan",
      });
    });

    it("turns a successful scan run into a verified session and a jar", async () => {
      const { service, submit } = make({
        cookies: [cookie(SESSION_COOKIE), cookie("a1")],
        open: true,
        flows: {
          runs: { "xhs-login-scan": scanned() },
          output: { nickname: " 阿甲 ", profileHref: "/user/profile/5f8a1b2c" },
        },
      });
      await service.qrCode();

      const status = await service.status();

      expect(status).toMatchObject({
        phase: "verified",
        loggedIn: true,
        verified: true,
        sessionCookie: true,
        account: { nickname: "阿甲", userId: "5f8a1b2c" },
        loginRunId: null,
      });
      // The proof came from the scan run itself — no second flow was needed.
      expect(submit).toHaveBeenCalledTimes(1);
      expect(submit).toHaveBeenCalledWith(SCAN_FLOW, expect.anything());
      expect((await stat(cookieFile)).mode & 0o777).toBe(0o600);
      const raw = await readFile(cookieFile, "utf8");
      expect(
        JSON.parse(raw).cookies.map((entry: Cookie) => entry.name),
      ).toEqual([SESSION_COOKIE, "a1"]);
    });

    it("harvests a scan that lands without anyone polling status", async () => {
      // The real-world path: scan → go straight to `xhs-following`, never call
      // `/status`. The jar still has to be written, so the pending run is watched.
      const runs: Record<string, RunRecord> = {
        "xhs-login-scan": scanning(),
      };
      const { service, submit } = make({
        cookies: [cookie(SESSION_COOKIE), cookie("a1")],
        open: true,
        flows: {
          runs,
          output: { nickname: "阿甲", profileHref: "/user/profile/5f8a1b2c" },
        },
      });
      // Fake timers must be installed before the QR call, otherwise the watch
      // interval belongs to the real clock and no amount of advancing hits it.
      vi.useFakeTimers();
      try {
        await service.qrCode();
        expect(submit).toHaveBeenCalledTimes(1);

        // The scan lands: the run finishes behind our back.
        runs["xhs-login-scan"] = scanned();
        await vi.advanceTimersByTimeAsync(2_500);
      } finally {
        vi.useRealTimers();
      }

      await vi.waitFor(async () => {
        const raw = await readFile(cookieFile, "utf8");
        expect(
          JSON.parse(raw).cookies.map((entry: Cookie) => entry.name),
        ).toEqual([SESSION_COOKIE, "a1"]);
      });
      // Harvesting is not a second flow run.
      expect(submit).toHaveBeenCalledTimes(1);
    });

    it("falls back to the cookie path when the scan page times out", async () => {
      const { service, submit } = make({
        cookies: [cookie(SESSION_COOKIE)],
        open: true,
        flows: {
          runs: {
            "xhs-login-scan": scanned("failed", {
              code: "timeout",
              message: "sidebar never rendered",
            }),
          },
          artifacts: 0,
          output: { nickname: "阿甲", profileHref: "" },
        },
      });
      await service.qrCode();

      const status = await service.status();

      expect(status).toMatchObject({ phase: "verified", loggedIn: true });
      expect(submit).toHaveBeenCalledWith(CHECK_FLOW, expect.anything());
    });

    it("does not call a guest session cookie a login", async () => {
      // XHS hands `web_session` to anonymous visitors; only `verified` counts.
      const { service } = make({
        cookies: [cookie(SESSION_COOKIE), cookie("a1")],
        open: true,
        flows: {
          runs: {
            [CHECK_FLOW]: run(CHECK_FLOW, {
              state: "failed",
              error: { code: "timeout", message: "sidebar never rendered" },
            }),
          },
        },
      });

      expect(await service.status()).toMatchObject({
        phase: "stale",
        loggedIn: false,
        verified: false,
        sessionCookie: true,
        account: null,
      });
    });

    it("reports anonymous when the profile holds no session either", async () => {
      const { service, submit, browser } = make();

      const status = await service.status();

      expect(status).toMatchObject({
        phase: "anonymous",
        loggedIn: false,
        verified: false,
        sessionCookie: false,
        cookieNames: [],
      });
      // The profile is the truth, so it is asked even when there is no jar to go on.
      expect(browser.browser.cookies).toHaveBeenCalled();
      expect(submit).not.toHaveBeenCalled();
    });

    it("fills an empty jar from a profile that is still logged in", async () => {
      // Real case: a logout emptied the jar, then the profile logged in again. An
      // empty jar must not hide the session — and it gets refilled on the spot.
      await writeJar([]);
      const { service } = make({
        cookies: [cookie(SESSION_COOKIE), cookie("a1")],
        flows: {
          output: { nickname: "阿甲", profileHref: "/user/profile/5f8a1b2c" },
        },
      });

      expect(await service.status()).toMatchObject({
        phase: "verified",
        loggedIn: true,
      });
      const raw = await readFile(cookieFile, "utf8");
      expect(
        JSON.parse(raw).cookies.map((entry: Cookie) => entry.name),
      ).toEqual([SESSION_COOKIE, "a1"]);
    });

    it("seeds a saved jar once", async () => {
      await writeJar([cookie(SESSION_COOKIE)]);
      const { service, browser } = make({
        flows: {
          output: { nickname: "阿甲", profileHref: "/user/profile/5f8a1b2c" },
        },
      });

      await service.status();
      await service.status();

      expect(browser.addCookies).toHaveBeenCalledTimes(1);
    });

    it("surfaces the risk-control page instead of calling it stale", async () => {
      const { service } = make({
        cookies: [cookie(SESSION_COOKIE)],
        open: true,
        flows: {
          runs: {
            [CHECK_FLOW]: run(CHECK_FLOW, {
              state: "failed",
              error: { code: "blocked", message: "安全限制" },
            }),
          },
        },
      });

      expect(await service.status()).toMatchObject({
        phase: "blocked",
        loggedIn: false,
        blocked: true,
      });
    });

    it("caches the verification instead of re-running the flow every poll", async () => {
      const { service, submit } = make({
        cookies: [cookie(SESSION_COOKIE)],
        open: true,
        flows: { output: { nickname: "阿甲", profileHref: "" } },
      });

      await service.status();
      await service.status();
      await service.status();

      expect(submit).toHaveBeenCalledTimes(1);
    });
  });

  describe("cookie jar", () => {
    it("regenerates a corrupt jar instead of failing", async () => {
      await mkdir(dir, { recursive: true });
      await writeFile(cookieFile, "{ not json", { mode: 0o600 });
      const { service } = make({
        cookies: [cookie(SESSION_COOKIE)],
        open: true,
        flows: { output: { nickname: "阿甲", profileHref: "" } },
      });

      expect(await service.status()).toMatchObject({ loggedIn: true });
      const raw = await readFile(cookieFile, "utf8");
      expect(() => JSON.parse(raw)).not.toThrow();
    });

    it("ignores a jar without a cookies array", async () => {
      await writeFile(cookieFile, JSON.stringify({ savedAt: "now" }), {
        mode: 0o600,
      });
      const { service } = make();

      expect(await service.status()).toMatchObject({ phase: "anonymous" });
    });
  });

  describe("logout", () => {
    it("cancels a pending scan, clears cookies and empties the jar", async () => {
      await writeJar([cookie(SESSION_COOKIE)]);
      const { service, browser, cancel } = make({
        flows: { runs: { "run-xhs-login-scan": scanning() } },
      });
      await service.qrCode();

      await service.logout();

      expect(cancel).toHaveBeenCalledWith("run-xhs-login-scan");
      expect(browser.clearCookies).toHaveBeenCalled();
      const raw = await readFile(cookieFile, "utf8");
      expect(JSON.parse(raw).cookies).toEqual([]);
    });
  });
});
