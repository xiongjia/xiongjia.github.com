import { Controller, Get } from "@nestjs/common";
import { ApiOkResponse, ApiOperation, ApiTags } from "@nestjs/swagger";
import type { QueueStats } from "pg-boss";
import { PgBossService } from "../pg-boss/pg-boss.service";

@ApiTags("queues")
@Controller("queues")
export class QueuesController {
  constructor(private readonly pgBoss: PgBossService) {}

  @Get()
  @ApiOperation({
    summary: "List queues with live stats",
    description:
      "v12 getQueueStats: deferred/queued/ready/active/failed/total counts per queue. Completed jobs are cleaned up by deleteAfterSeconds, so they do not show up here.",
  })
  @ApiOkResponse({ description: "Queue stats per queue" })
  list(): Promise<QueueStats[]> {
    return this.pgBoss.getQueueStats();
  }
}
