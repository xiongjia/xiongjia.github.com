import { Module } from "@nestjs/common";
import { FlowLoader } from "../flow/loader";
import { RunQueue } from "../run/queue";
import { RunStore } from "../run/store";
import { FlowService } from "./flow.service";
import { FlowsController } from "./flows.controller";

/** Flow DSL execution: submit a run, poll it, fetch its JSON output. */
@Module({
  controllers: [FlowsController],
  providers: [FlowLoader, RunStore, RunQueue, FlowService],
  // XhsModule runs `xhs-login-qr` / `xhs-login-check` through this service.
  exports: [FlowService],
})
export class FlowsModule {}
