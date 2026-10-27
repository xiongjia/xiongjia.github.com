import { Module } from "@nestjs/common";
import { DemoController } from "./demo.controller";

/** Stable, offline target that proves the browser pipeline works. */
@Module({
  controllers: [DemoController],
})
export class DemoModule {}
