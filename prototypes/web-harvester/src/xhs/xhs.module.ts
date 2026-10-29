import { Module } from "@nestjs/common";
import { FlowsModule } from "../flows/flows.module";
import { XhsService } from "./xhs.service";
import { XhsController } from "./xhs.controller";

/** Xiaohongshu operations. Login first; read actions land in the next milestone. */
@Module({
  imports: [FlowsModule],
  controllers: [XhsController],
  providers: [XhsService],
  exports: [XhsService],
})
export class XhsModule {}
