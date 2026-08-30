import { Module } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { HealthModule } from "./health/health.module";
import { JobsModule } from "./jobs/jobs.module";
import { PgBossModule } from "./pg-boss/pg-boss.module";
import { QueuesModule } from "./queues/queues.module";

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: [".env.dev.local", ".env"],
    }),
    PgBossModule,
    JobsModule,
    QueuesModule,
    HealthModule,
  ],
})
export class AppModule {}
