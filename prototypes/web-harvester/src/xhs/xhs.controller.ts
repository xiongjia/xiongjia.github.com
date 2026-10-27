import {
  Controller,
  Delete,
  Get,
  Query,
  Res,
  ServiceUnavailableException,
} from "@nestjs/common";
import {
  ApiOkResponse,
  ApiOperation,
  ApiQuery,
  ApiTags,
} from "@nestjs/swagger";
import type { Response } from "express";
import { FollowingDebugReport, XhsDebugService } from "./debug.service";
import { FollowingResult, XhsFollowingService } from "./following.service";
import { LoginStatus, XhsLoginService } from "./login.service";

/**
 * Query strings are strings; nonsense must fall back to the service defaults
 * instead of turning into `NaN` comparisons that silently collect nothing.
 */
function positiveInt(
  value: string | undefined,
  allowZero = false,
): number | undefined {
  if (value === undefined || value.trim() === "") {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    return undefined;
  }
  if (allowZero ? parsed < 0 : parsed <= 0) {
    return undefined;
  }
  return parsed;
}

/**
 * Xiaohongshu session endpoints.
 *
 * Kept deliberately small: this milestone is "get a session, keep it", the read
 * operations (feeds/search/note) come next.
 */
@ApiTags("xhs")
@Controller("xhs")
export class XhsController {
  constructor(
    private readonly login: XhsLoginService,
    private readonly following: XhsFollowingService,
    private readonly debug: XhsDebugService,
  ) {}

  @Get("login/qrcode")
  @ApiOperation({
    summary:
      "QR code for logging in (image/png); scan it with the Xiaohongshu app",
  })
  async qrCode(@Res() res: Response): Promise<void> {
    const { png, source } = await this.login
      .qrCode()
      .catch((error: unknown) => {
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
    return this.login.status();
  }

  @Get("following")
  @ApiOperation({
    summary: "Collect the signed-in account's following / 粉丝 (JSONL on disk)",
  })
  @ApiOkResponse({
    description: "{ profileId, count, items, outputPath, elapsedMs }",
  })
  // All three are optional; without these decorators Swagger marks them required
  // and the UI refuses to send the request.
  @ApiQuery({ name: "limit", required: false, type: Number, example: 200 })
  @ApiQuery({ name: "scrolls", required: false, type: Number, example: 5 })
  @ApiQuery({ name: "profileId", required: false, type: String })
  followingList(
    @Query("limit") limit?: string,
    @Query("scrolls") scrolls?: string,
    @Query("profileId") profileId?: string,
  ): Promise<FollowingResult> {
    return this.following
      .collect({
        profileId: profileId?.trim() || undefined,
        limit: positiveInt(limit),
        scrolls: positiveInt(scrolls, true),
      })
      .catch((error: unknown) => {
        throw new ServiceUnavailableException(
          `Could not read the following list: ${error instanceof Error ? error.message : String(error)}`,
        );
      });
  }

  @Get("debug/following")
  @ApiOperation({
    summary:
      "Why is the following list empty? Dumps selectors, links, containers + a screenshot",
  })
  @ApiQuery({ name: "profileId", required: false, type: String })
  debugFollowing(
    @Query("profileId") profileId?: string,
  ): Promise<FollowingDebugReport> {
    return this.debug
      .inspectFollowing(profileId?.trim() || undefined)
      .catch((error: unknown) => {
        throw new ServiceUnavailableException(
          `Could not inspect the profile page: ${error instanceof Error ? error.message : String(error)}`,
        );
      });
  }

  @Delete("login")
  @ApiOperation({ summary: "Forget the session (clears cookies and the jar)" })
  async logout(): Promise<{ ok: true }> {
    await this.login.logout();
    return { ok: true };
  }
}
