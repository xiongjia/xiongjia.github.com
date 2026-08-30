import { Controller, Get } from "@nestjs/common";
import { ApiOkResponse, ApiOperation, ApiTags } from "@nestjs/swagger";
import type { HealthStatus } from "../pg-boss/pg-boss.types";
import { PgBossService } from "../pg-boss/pg-boss.service";

@ApiTags("health")
@Controller("health")
export class HealthController {
  constructor(private readonly pgBoss: PgBossService) {}

  @Get()
  @ApiOperation({
    summary: "DB connectivity + pg-boss schema state",
    description:
      "Runs boss.isInstalled()/schemaVersion() against Postgres; db is 'down' when those queries fail.",
  })
  @ApiOkResponse({ description: "Health status" })
  check(): Promise<HealthStatus> {
    return this.pgBoss.health();
  }
}
