import type { ConfigService } from "@nestjs/config";
import type { Response } from "express";
import type { Page } from "patchright";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EngineNotReadyError } from "../browser/backends";
import type { BrowserService } from "../browser/browser.service";
import { DemoController } from "./demo.controller";
import { DEMO_PAGE_HTML } from "./demo.page";

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/156.0.0.0 Safari/537.36";

function makeConfig(values: Record<string, unknown> = {}): ConfigService {
  const defaults: Record<string, unknown> = {
    HARVEST_HOST: "127.0.0.1",
    HARVEST_PORT: 8765,
    ...values,
  };
  return { get: (key: string) => defaults[key] } as unknown as ConfigService;
}

function makePage(): Page {
  const texts: Record<string, string> = {
    "#title": " harvester demo page ",
    "#delayed": " delayed-ready ",
    "#status": " clicked ",
  };
  return {
    goto: vi.fn(async () => null),
    waitForSelector: vi.fn(async () => null),
    click: vi.fn(async () => undefined),
    title: vi.fn(async () => "harvester demo"),
    textContent: vi.fn(async (selector: string) => texts[selector] ?? null),
    evaluate: vi.fn(async () => UA),
  } as unknown as Page;
}

function makeBrowser(page: Page, screenshotPath: string, dataDir = "data") {
  const withPage = vi.fn(
    async <T>(fn: (page: Page) => Promise<T>): Promise<T> => fn(page),
  );
  const screenshot = vi.fn(async () => screenshotPath);
  const browser = {
    withPage,
    screenshot,
    dataDir,
  } as unknown as BrowserService;
  return { browser, withPage, screenshot };
}

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

describe("DemoController", () => {
  let dir: string;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "harvester-demo-"));
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("serves the inline page", () => {
    const { browser } = makeBrowser(makePage(), "unused");
    const controller = new DemoController(browser, makeConfig());

    expect(controller.page()).toBe(DEMO_PAGE_HTML);
  });

  it("visits the versioned demo route and reports what it saw", async () => {
    const page = makePage();
    const { browser, withPage, screenshot } = makeBrowser(
      page,
      "data/screenshots/demo.png",
    );
    const controller = new DemoController(browser, makeConfig());

    const result = await controller.visit();

    expect(withPage).toHaveBeenCalledTimes(1);
    expect(page.goto).toHaveBeenCalledWith(
      "http://127.0.0.1:8765/api/v1/demo",
      {
        waitUntil: "domcontentloaded",
      },
    );
    expect(page.waitForSelector).toHaveBeenCalledWith("#delayed", {
      state: "visible",
      timeout: 5_000,
    });
    expect(page.click).toHaveBeenCalledWith("#bump");
    expect(screenshot).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({
      url: "http://127.0.0.1:8765/api/v1/demo",
      title: "harvester demo",
      heading: "harvester demo page",
      delayedText: "delayed-ready",
      clickResult: "clicked",
      userAgent: UA,
      screenshotPath: "data/screenshots/demo.png",
    });
    expect(typeof result.elapsedMs).toBe("number");
  });

  it("uses loopback when the server binds to 0.0.0.0", async () => {
    const page = makePage();
    const { browser } = makeBrowser(page, "unused");
    const controller = new DemoController(
      browser,
      makeConfig({ HARVEST_HOST: "0.0.0.0" }),
    );

    const result = await controller.visit();

    expect(result.url).toBe("http://127.0.0.1:8765/api/v1/demo");
  });

  it("streams the screenshot as image/png", async () => {
    const file = join(dir, "shot.png");
    await writeFile(file, "fake-png");
    const { browser } = makeBrowser(makePage(), file);
    const controller = new DemoController(browser, makeConfig());
    const { res, headers, end } = makeRes();

    await controller.screenshot(res);

    expect(headers["Content-Type"]).toBe("image/png");
    expect(headers["Content-Length"]).toBe(String("fake-png".length));
    expect(end).toHaveBeenCalledTimes(1);
  });

  it("answers 503 when the engine is not ready", async () => {
    const { browser, withPage } = makeBrowser(makePage(), "unused");
    withPage.mockRejectedValueOnce(
      new EngineNotReadyError(
        "CloakBrowser's stealth Chromium build is not installed",
      ),
    );
    const controller = new DemoController(browser, makeConfig());

    await expect(controller.visit()).rejects.toMatchObject({ status: 503 });
  });

  it("leaves a genuine bug as a 500", async () => {
    const { browser, withPage } = makeBrowser(makePage(), "unused");
    withPage.mockRejectedValueOnce(new Error("boom"));
    const controller = new DemoController(browser, makeConfig());

    await expect(controller.visit()).rejects.toThrow("boom");
  });
});
