import {
  Controller,
  Delete,
  Get,
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
      "QR code for logging in (image/png); scan it with the Xiaohongshu app",
  })
  async qrCode(@Res() res: Response): Promise<void> {
    const { png, source } = await this.xhs.qrCode().catch((error: unknown) => {
      throw new ServiceUnavailableException(
        `Could not open the Xiaohongshu login page: ${error instanceof Error ? error.message : String(error)}`,
      );
    });

    res.setHeader("Content-Type", "image/png");
    res.setHeader("Content-Length", String(png.byteLength));
    res.setHeader("X-QR-Source", source);
    res.end(png);
  }

  @Get("login/status")
  @ApiOperation({
    summary:
      "Whether a session exists; saves the cookies on the first successful poll",
  })
  @ApiOkResponse({
    description: "{ loggedIn, cookieNames, qrSource, savedAt }",
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
