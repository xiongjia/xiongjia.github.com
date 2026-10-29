import { ServiceUnavailableException } from "@nestjs/common";
import type { Response } from "express";
import { describe, expect, it, vi } from "vitest";
import type { LoginStatus } from "./xhs.service";
import { XhsService } from "./xhs.service";
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

function makeService(overrides: Partial<XhsService> = {}) {
  const service = {
    qrCode: vi.fn(async () => ({
      png: Buffer.from("png"),
      source: "img.qrcode-img",
    })),
    status: vi.fn(async () => STATUS),
    logout: vi.fn(async () => undefined),
    ...overrides,
  } as unknown as XhsService;
  return service;
}

describe("XhsController", () => {
  it("streams the QR code with its source", async () => {
    const controller = new XhsController(makeService());
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
    );
    const { res } = makeRes();

    await expect(controller.qrCode(res)).rejects.toBeInstanceOf(
      ServiceUnavailableException,
    );
  });

  it("passes the login status through", async () => {
    const controller = new XhsController(makeService());

    await expect(controller.status()).resolves.toEqual(STATUS);
  });

  it("reports logout", async () => {
    const service = makeService();
    const controller = new XhsController(service);

    await expect(controller.logout()).resolves.toEqual({ ok: true });
    expect(service.logout).toHaveBeenCalledTimes(1);
  });
});
