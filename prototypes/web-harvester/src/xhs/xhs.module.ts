import { Module } from "@nestjs/common";
import { XhsDebugService } from "./debug.service";
import { XhsFollowingService } from "./following.service";
import { XhsLoginService } from "./login.service";
import { XhsController } from "./xhs.controller";

/** Xiaohongshu operations. Login first; read actions land in the next milestone. */
@Module({
  controllers: [XhsController],
  providers: [XhsLoginService, XhsFollowingService, XhsDebugService],
  exports: [XhsLoginService, XhsFollowingService, XhsDebugService],
})
export class XhsModule {}
