import {
  Controller,
  Get,
  Header,
  Res,
  ServiceUnavailableException,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { ApiOkResponse, ApiOperation, ApiTags } from "@nestjs/swagger";
import type { Response } from "express";
import { readFile } from "node:fs/promises";
import { EngineNotReadyError } from "../browser/backends";
import { BrowserService } from "../browser/browser.service";
import { apiPath } from "../common/api";
import { selfBaseUrl } from "../common/self-url";
import { DEMO_PAGE_HTML, DEMO_SELECTORS } from "./demo.page";

export interface DemoVisitResult {
  /** URL the browser actually opened. */
  url: string;
  title: string;
  heading: string;
  /** Text of the element that only becomes visible 1s after load. */
  delayedText: string;
  /** Text after clicking the button — proves interaction works. */
  clickResult: string;
  userAgent: string;
  screenshotPath: string;
  elapsedMs: number;
}

/**
 * Browser self-check. No Xiaohongshu, no login, no network: if this controller
 * works, the engine (launch, DOM, interaction, screenshot) works.
 */
@ApiTags("demo")
@Controller("demo")
export class DemoController {
  constructor(
    private readonly browser: BrowserService,
    private readonly config: ConfigService,
  ) {}

  @Get()
  @Header("Content-Type", "text/html; charset=utf-8")
  @ApiOperation({ summary: "The static self-check page" })
  page(): string {
    return DEMO_PAGE_HTML;
  }

  @Get("visit")
  @ApiOperation({
    summary: "Open the self-check page in the browser and report what it saw",
  })
  @ApiOkResponse({
    description: "DOM snapshot, interaction result, screenshot path, timing",
  })
  async visit(): Promise<DemoVisitResult> {
    const url = `${selfBaseUrl(this.config)}${apiPath("demo")}`;
    const startedAt = Date.now();

    return this.withBrowserErrors(async () =>
      this.browser.withPage(async (page) => {
        await page.goto(url, { waitUntil: "domcontentloaded" });

        // The delayed element proves waitForSelector + script execution.
        await page.waitForSelector(DEMO_SELECTORS.delayed, {
          state: "visible",
          timeout: 5_000,
        });
        await page.click(DEMO_SELECTORS.bump);

        const title = await page.title();
        const heading =
          (await page.textContent(DEMO_SELECTORS.title))?.trim() ?? "";
        const delayedText =
          (await page.textContent(DEMO_SELECTORS.delayed))?.trim() ?? "";
        const clickResult =
          (await page.textContent(DEMO_SELECTORS.status))?.trim() ?? "";
        const userAgent = await page.evaluate(() => navigator.userAgent);
        const screenshotPath = await this.browser.screenshot(
          page,
          "demo-visit",
        );

        return {
          url,
          title,
          heading,
          delayedText,
          clickResult,
          userAgent,
          screenshotPath,
          elapsedMs: Date.now() - startedAt,
        };
      }),
    );
  }

  @Get("screenshot")
  @ApiOperation({ summary: "Screenshot of the self-check page (image/png)" })
  async screenshot(@Res() res: Response): Promise<void> {
    const path = await this.withBrowserErrors(async () =>
      this.browser.withPage(async (page) => {
        await page.goto(`${selfBaseUrl(this.config)}${apiPath("demo")}`, {
          waitUntil: "domcontentloaded",
        });
        await page.waitForSelector(DEMO_SELECTORS.delayed, {
          state: "visible",
          timeout: 5_000,
        });
        return this.browser.screenshot(page, "demo");
      }),
    );

    const buffer = await readFile(path);
    res.setHeader("Content-Type", "image/png");
    res.setHeader("Content-Length", String(buffer.byteLength));
    res.end(buffer);
  }

  /** A missing engine build (or refusing license) is an operator problem, not a server bug. */
  private async withBrowserErrors<T>(run: () => Promise<T>): Promise<T> {
    try {
      return await run();
    } catch (error) {
      if (error instanceof EngineNotReadyError) {
        throw new ServiceUnavailableException(error.message);
      }
      throw error;
    }
  }
}
