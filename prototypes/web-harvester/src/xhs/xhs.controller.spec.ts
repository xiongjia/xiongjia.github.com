import { ServiceUnavailableException } from "@nestjs/common";
import type { Response } from "express";
import { describe, expect, it, vi } from "vitest";
import type { FollowingDebugReport, XhsDebugService } from "./debug.service";
import type { FollowingResult, XhsFollowingService } from "./following.service";
import type { LoginStatus, XhsLoginService } from "./login.service";
import { XhsController } from "./xhs.controller";

function makeRes() {
  const headers: Record<string, string> = {};
  const res = {
    setHeader: vi.fn((key: string, value: string) => {
      headers[key] = value;
    }),
    end: vi.fn(),
  };
  return { res: res as unknown as Response, headers, end: res.end };
}

const STATUS: LoginStatus = {
  loggedIn: true,
  verified: true,
  blocked: false,
  account: { nickname: "测试用户", userId: "abc123" },
  cookieNames: ["web_session"],
  qrSource: "img.qrcode-img",
  savedAt: "2026-10-25T00:00:00.000Z",
  checkedAt: "2026-10-25T00:01:00.000Z",
};

const FOLLOWING: FollowingResult = {
  profileId: "5f8a1b2c",
  count: 1,
  items: [{ nickname: "阿乙", desc: "1篇笔记未看", avatarUrl: "a/1" }],
  triggerUsed: ".clickable:has-text('关注')",
  rowsSeen: 2,
  outputPath: "data/xhs-following.jsonl",
  elapsedMs: 1200,
};

function makeFollowing() {
  return {
    collect: vi.fn(async () => FOLLOWING),
  } as unknown as XhsFollowingService;
}

function makeDebug() {
  return {
    inspectFollowing: vi.fn(async () => ({ url: "u" }) as FollowingDebugReport),
  } as unknown as XhsDebugService;
}

function makeService(overrides: Partial<XhsLoginService> = {}) {
  const service = {
    qrCode: vi.fn(async () => ({
      png: Buffer.from("png"),
      source: "img.qrcode-img",
    })),
    status: vi.fn(async () => STATUS),
    logout: vi.fn(async () => undefined),
    ...overrides,
  } as unknown as XhsLoginService;
  return service;
}

describe("XhsController", () => {
  it("streams the QR code with its source", async () => {
    const controller = new XhsController(
      makeService(),
      makeFollowing(),
      makeDebug(),
    );
    const { res, headers, end } = makeRes();

    await controller.qrCode(res);

    expect(headers["Content-Type"]).toBe("image/png");
    expect(headers["Content-Length"]).toBe(
      String(Buffer.from("png").byteLength),
    );
    expect(headers["X-QR-Source"]).toBe("img.qrcode-img");
    expect(end).toHaveBeenCalledTimes(1);
  });

  it("turns a browser failure into 503 with the reason", async () => {
    const controller = new XhsController(
      makeService({
        qrCode: vi.fn(async () => {
          throw new Error("Xiaohongshu served its risk-control page");
        }),
      }),
      makeFollowing(),
      makeDebug(),
    );
    const { res } = makeRes();

    await expect(controller.qrCode(res)).rejects.toBeInstanceOf(
      ServiceUnavailableException,
    );
  });

  it("passes the login status through", async () => {
    const controller = new XhsController(
      makeService(),
      makeFollowing(),
      makeDebug(),
    );

    await expect(controller.status()).resolves.toEqual(STATUS);
  });

  it("collects the following list and maps failures to 503", async () => {
    const following = makeFollowing();
    const controller = new XhsController(makeService(), following, makeDebug());

    await expect(
      controller.followingList("10", "2", undefined),
    ).resolves.toEqual(FOLLOWING);
    expect(following.collect).toHaveBeenCalledWith({
      profileId: undefined,
      limit: 10,
      scrolls: 2,
    });

    const failing = new XhsController(
      makeService(),
      {
        collect: vi.fn(async () => Promise.reject(new Error("boom"))),
      } as unknown as XhsFollowingService,
      makeDebug(),
    );
    await expect(failing.followingList()).rejects.toBeInstanceOf(
      ServiceUnavailableException,
    );
  });

  it("drops non-numeric query values instead of passing NaN through", async () => {
    const following = makeFollowing();
    const controller = new XhsController(makeService(), following, makeDebug());

    await controller.followingList("abc", "-3", "  ");

    expect(following.collect).toHaveBeenCalledWith({
      profileId: undefined,
      limit: undefined,
      scrolls: undefined,
    });
  });

  it("inspects the profile page for debugging", async () => {
    const controller = new XhsController(
      makeService(),
      makeFollowing(),
      makeDebug(),
    );

    await expect(controller.debugFollowing("abc")).resolves.toMatchObject({
      url: "u",
    });

    const failing = new XhsController(makeService(), makeFollowing(), {
      inspectFollowing: vi.fn(async () =>
        Promise.reject(new Error("no session")),
      ),
    } as unknown as XhsDebugService);
    await expect(failing.debugFollowing()).rejects.toBeInstanceOf(
      ServiceUnavailableException,
    );
  });

  it("reports logout", async () => {
    const service = makeService();
    const controller = new XhsController(service, makeFollowing(), makeDebug());

    await expect(controller.logout()).resolves.toEqual({ ok: true });
    expect(service.logout).toHaveBeenCalledTimes(1);
  });
});
