import {
  Controller,
  Delete,
  Get,
  HttpException,
  Res,
  ServiceUnavailableException,
} from "@nestjs/common";
import { ApiOkResponse, ApiOperation, ApiTags } from "@nestjs/swagger";
import type { Response } from "express";
import type { LoginStatus } from "./xhs.service";
import { XhsService } from "./xhs.service";

/**
 * Xiaohongshu session endpoints.
 *
 * Kept deliberately small: this milestone is "get a session, keep it", the read
 * operations (feeds/search/note) come next.
 */
@ApiTags("xhs")
@Controller("xhs")
export class XhsController {
  constructor(private readonly xhs: XhsService) {}

  @Get("login/qrcode")
  @ApiOperation({
    summary:
      "QR code for logging in (image/png); scan it while the run that produced it keeps the page open",
  })
  async qrCode(@Res() res: Response): Promise<void> {
    const { png, runId, source } = await this.xhs
      .qrCode()
      .catch((error: unknown) => {
        if (error instanceof HttpException) {
          throw error;
        }
        throw new ServiceUnavailableException(
          `Could not open the Xiaohongshu login page: ${error instanceof Error ? error.message : String(error)}`,
        );
      });

    res.setHeader("Content-Type", "image/png");
    res.setHeader("Content-Length", String(png.byteLength));
    // `pending` = the page is still painting; the selector is known only once the
    // run finishes, and the run outlives this response on purpose.
    res.setHeader("X-QR-Source", source ?? "pending");
    res.setHeader("X-Login-Run", runId);
    res.end(png);
  }

  @Get("login/status")
  @ApiOperation({
    summary:
      "Where the session stands; follows the pending scan run and saves the jar once a login lands",
  })
  @ApiOkResponse({
    description:
      "{ phase, loggedIn, verified, sessionCookie, account, loginRunId, savedAt } — `loggedIn` is true only for a verified session, a guest web_session is not one",
  })
  status(): Promise<LoginStatus> {
    return this.xhs.status();
  }

  @Delete("login")
  @ApiOperation({ summary: "Forget the session (clears cookies and the jar)" })
  async logout(): Promise<{ ok: true }> {
    await this.xhs.logout();
    return { ok: true };
  }
}
