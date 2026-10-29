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
import type { BrowserService } from "../browser/browser.service";
import type { FlowService } from "../flows/flow.service";
import type { RunRecord } from "../run/run";
import type { LoginStatus } from "./xhs.service";
import { XhsService } from "./xhs.service";

const PNG = Buffer.from("fake-png");
/** Duplicated on purpose: the service keeps it module-private. */
const SESSION_COOKIE = "web_session";

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

interface FlowOptions {
  runs?: Record<string, RunRecord>;
  output?: Record<string, unknown> | null;
}

function makeFlows(options: FlowOptions = {}) {
  const submit = vi.fn(async (name: string) => ({
    record: options.runs?.[name] ?? run(name),
    settled: true,
  }));
  const output = vi.fn(async () => options.output ?? {});
  const artifact = vi.fn(async () => ({
    buffer: PNG,
    contentType: "image/png",
  }));
  const flows = {
    submit,
    output,
    artifact,
    defaultProfile: "main",
  } as unknown as FlowService;
  return { flows, submit, output, artifact };
}

function makeBrowser(cookies: Cookie[] = []) {
  const addCookies = vi.fn(async () => undefined);
  const clearCookies = vi.fn(async () => undefined);
  const browser = {
    cookies: vi.fn(async () => cookies),
    addCookies,
    getContext: vi.fn(async () => ({ clearCookies })),
  } as unknown as BrowserService;
  return {
    browser,
    addCookies,
    clearCookies,
    setCookies: (next: Cookie[]) => cookies.splice(0, cookies.length, ...next),
  };
}

function makeConfig(cookieFile: string): ConfigService {
  return {
    get: (key: string) => {
      if (key === "HARVEST_XHS_COOKIES") return cookieFile;
      if (key === "HARVEST_XHS_SETTLE_MS") return 50;
      return undefined;
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

  function make(options: { cookies?: Cookie[]; flows?: FlowOptions } = {}): {
    service: XhsService;
    submit: ReturnType<typeof makeFlows>["submit"];
    artifact: ReturnType<typeof makeFlows>["artifact"];
    browser: ReturnType<typeof makeBrowser>;
  } {
    const browser = makeBrowser(options.cookies ?? []);
    const flows = makeFlows(options.flows);
    const service = new XhsService(
      browser.browser,
      makeConfig(cookieFile),
      flows.flows,
    );
    return { service, submit: flows.submit, artifact: flows.artifact, browser };
  }

  async function writeJar(cookies: Cookie[]) {
    // `status` writes the jar itself; seed one by writing the same shape.
    await writeFile(
      cookieFile,
      `${JSON.stringify({ savedAt: "2026-01-01T00:00:00.000Z", cookies }, null, 2)}\n`,
      { mode: 0o600 },
    );
  }

  describe("qrCode", () => {
    it("runs the qr flow and answers with its artifact", async () => {
      const { service, submit, artifact } = make({
        flows: {
          runs: {
            "xhs-login-qr": run("xhs-login-qr", {
              meta: {
                url: "https://www.xiaohongshu.com/explore",
                userAgent: "",
                usedSelectors: { "4.1.screenshot": "img.qrcode-img" },
                screenshots: { qr: "artifacts/qr.png" },
                steps: [],
              },
            }),
          },
        },
      });

      const qr = await service.qrCode();

      expect(qr).toEqual({ png: PNG, source: "img.qrcode-img" });
      expect(submit).toHaveBeenCalledWith("xhs-login-qr", {
        profile: "main",
        waitMs: expect.any(Number),
      });
      expect(artifact).toHaveBeenCalledWith("run-xhs-login-qr", "qr.png");
    });

    it("reports the viewport fallback when no QR selector matched", async () => {
      const { service } = make({
        flows: {
          runs: {
            "xhs-login-qr": run("xhs-login-qr", {
              meta: {
                url: "",
                userAgent: "",
                usedSelectors: {},
                screenshots: { qr: "artifacts/qr.png" },
                steps: [],
              },
            }),
          },
        },
      });

      expect((await service.qrCode()).source).toBe("viewport");
    });

    it("maps a blocked run to 503 with its reason", async () => {
      const { service } = make({
        flows: {
          runs: {
            "xhs-login-qr": run("xhs-login-qr", {
              state: "failed",
              error: { code: "blocked", message: "IP存在风险" },
            }),
          },
        },
      });

      const error = await service.qrCode().catch((caught: unknown) => caught);

      expect(error).toBeInstanceOf(ServiceUnavailableException);
      expect((error as ServiceUnavailableException).message).toContain(
        "blocked",
      );
    });
  });

  describe("status", () => {
    it("reports not logged in without touching a flow", async () => {
      const { service, submit } = make();

      const status: LoginStatus = await service.status();

      expect(status).toMatchObject({
        loggedIn: false,
        verified: false,
        blocked: false,
        account: null,
        cookieNames: [],
      });
      expect(submit).not.toHaveBeenCalled();
    });

    it("seeds saved cookies once and treats them as a session", async () => {
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

    it("returns the login-gated identity as proof and keeps a jar copy", async () => {
      const { service, submit } = make({
        cookies: [cookie(SESSION_COOKIE), cookie("a1")],
        flows: {
          output: { nickname: " 阿甲 ", profileHref: "/user/profile/5f8a1b2c" },
        },
      });

      const status = await service.status();

      expect(status).toMatchObject({
        loggedIn: true,
        verified: true,
        blocked: false,
        account: { nickname: "阿甲", userId: "5f8a1b2c" },
      });
      expect(submit).toHaveBeenCalledWith("xhs-login-check", expect.anything());
      expect((await stat(cookieFile)).mode & 0o777).toBe(0o600);
      const raw = await readFile(cookieFile, "utf8");
      expect(
        JSON.parse(raw).cookies.map((entry: Cookie) => entry.name),
      ).toEqual([SESSION_COOKIE, "a1"]);
    });

    it("reports a stale session as logged in but unverified", async () => {
      const { service } = make({
        cookies: [cookie(SESSION_COOKIE)],
        flows: {
          runs: {
            "xhs-login-check": run("xhs-login-check", {
              state: "failed",
              error: { code: "timeout", message: "sidebar never rendered" },
            }),
          },
        },
      });

      expect(await service.status()).toMatchObject({
        loggedIn: true,
        verified: false,
        blocked: false,
        account: null,
      });
    });

    it("surfaces the risk-control page instead of calling it stale", async () => {
      const { service } = make({
        cookies: [cookie(SESSION_COOKIE)],
        flows: {
          runs: {
            "xhs-login-check": run("xhs-login-check", {
              state: "failed",
              error: { code: "blocked", message: "安全限制" },
            }),
          },
        },
      });

      expect(await service.status()).toMatchObject({
        loggedIn: true,
        verified: false,
        blocked: true,
      });
    });

    it("caches the verification instead of re-running the flow every poll", async () => {
      const { service, submit } = make({
        cookies: [cookie(SESSION_COOKIE)],
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

      expect(await service.status()).toMatchObject({ loggedIn: false });
    });
  });

  describe("logout", () => {
    it("clears cookies and empties the jar", async () => {
      await writeJar([cookie(SESSION_COOKIE)]);
      const { service, browser } = make();

      await service.logout();

      expect(browser.clearCookies).toHaveBeenCalled();
      const raw = await readFile(cookieFile, "utf8");
      expect(JSON.parse(raw).cookies).toEqual([]);
    });
  });
});
