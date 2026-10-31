import { Controller, Get, Post, Query } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import {
  ApiOkResponse,
  ApiOperation,
  ApiQuery,
  ApiTags,
} from "@nestjs/swagger";
import { BrowserService, type OpenContext } from "./browser.service";

export interface BrowserStatusResponse {
  /** `HARVEST_BROWSER_IDLE_MS` — `0` means idle contexts are never closed. */
  idleMs: number;
  contexts: OpenContext[];
}

export interface CloseResponse {
  /** Profiles whose context was actually open and got closed. */
  closed: string[];
}

/**
 * Browser lifecycle surface.
 *
 * Everything else in this host keeps the browser warm on purpose; these two
 * routes are the manual counterpart to `HARVEST_BROWSER_IDLE_MS`, for "I am done
 * for today, give the memory back" — closing a context never loses the session,
 * because the profile directory stays on disk.
 */
@ApiTags("browser")
@Controller("browser")
export class BrowserController {
  constructor(
    private readonly browser: BrowserService,
    private readonly config: ConfigService,
  ) {}

  @Get()
  @ApiOperation({
    summary: "Open browser contexts, what they run and how long they sat idle",
  })
  status(): BrowserStatusResponse {
    return {
      idleMs: this.config.get<number>("HARVEST_BROWSER_IDLE_MS") ?? 0,
      contexts: this.browser.status(),
    };
  }

  @Post("close")
  @ApiOperation({
    summary: "Close open browser contexts now (all, or ?profile=<name>)",
    description:
      "The persistent profile directory is untouched, so the next run launches again with the same cookies and fingerprint.",
  })
  @ApiQuery({ name: "profile", required: false })
  @ApiOkResponse({ description: "Profiles that were open and are now closed" })
  async close(@Query("profile") profile?: string): Promise<CloseResponse> {
    const closed =
      profile === undefined || profile === ""
        ? await this.browser.closeAll()
        : (await this.browser.close(profile))
          ? [profile]
          : [];
    return { closed };
  }
}
