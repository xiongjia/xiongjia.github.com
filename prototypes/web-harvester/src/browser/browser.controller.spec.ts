import type { ConfigService } from "@nestjs/config";
import { describe, expect, it, vi } from "vitest";
import { BrowserController } from "./browser.controller";
import type { BrowserService, OpenContext } from "./browser.service";

function makeConfig(values: Record<string, unknown> = {}): ConfigService {
  const defaults: Record<string, unknown> = {
    HARVEST_BROWSER_IDLE_MS: 0,
    ...values,
  };
  return { get: (key: string) => defaults[key] } as unknown as ConfigService;
}

function makeBrowser(contexts: OpenContext[] = []) {
  const status = vi.fn(() => contexts);
  const close = vi.fn(async (profile: string) => profile === "main");
  const closeAll = vi.fn(async () => ["main"]);
  const browser = { status, close, closeAll } as unknown as BrowserService;
  return { browser, status, close, closeAll };
}

describe("BrowserController", () => {
  it("reports the idle switch and the open contexts", () => {
    const open: OpenContext[] = [
      { profile: "main", engine: "cloakbrowser", idleMs: 1_234, busy: false },
    ];
    const { browser } = makeBrowser(open);
    const controller = new BrowserController(
      browser,
      makeConfig({ HARVEST_BROWSER_IDLE_MS: 60_000 }),
    );

    expect(controller.status()).toEqual({ idleMs: 60_000, contexts: open });
  });

  it("closes every context when no profile is named", async () => {
    const { browser, closeAll, close } = makeBrowser();
    const controller = new BrowserController(browser, makeConfig());

    await expect(controller.close()).resolves.toEqual({ closed: ["main"] });
    expect(closeAll).toHaveBeenCalledTimes(1);
    expect(close).not.toHaveBeenCalled();
  });

  it("closes one profile on request", async () => {
    const { browser, close, closeAll } = makeBrowser();
    const controller = new BrowserController(browser, makeConfig());

    await expect(controller.close("main")).resolves.toEqual({
      closed: ["main"],
    });
    expect(close).toHaveBeenCalledWith("main");
    expect(closeAll).not.toHaveBeenCalled();
  });

  it("reports an empty list for a profile that was not open", async () => {
    const { browser } = makeBrowser();
    const controller = new BrowserController(browser, makeConfig());

    await expect(controller.close("second")).resolves.toEqual({ closed: [] });
  });

  it("treats an empty profile as 'all'", async () => {
    const { browser, closeAll } = makeBrowser();
    const controller = new BrowserController(browser, makeConfig());

    await controller.close("");

    expect(closeAll).toHaveBeenCalledTimes(1);
  });
});
