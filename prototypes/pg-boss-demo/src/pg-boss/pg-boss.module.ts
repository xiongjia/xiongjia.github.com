import { Global, Module } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { PgBoss } from "pg-boss";
import { EchoJob } from "./handlers/echo.job";
import { FlakyJob } from "./handlers/flaky.job";
import { SlowJob } from "./handlers/slow.job";
import { NotificationService } from "./notification.service";
import { buildConnectionString, buildPgBossConfig } from "./pg-boss.config";
import { PgBossService } from "./pg-boss.service";

/**
 * Global module exposing PgBossService to every module (jobs, queues, ...).
 *
 * The PgBoss instance itself is a provider (factory reading @nestjs/config,
 * i.e. `.env.dev.local`), injected into PgBossService — which lets tests
 * replace it with `{ provide: PgBoss, useValue: mock }`.
 * The job handlers live here too: they are @Injectable() classes that
 * PgBossService resolves through the DI container (ModuleRef.get), so they can
 * inject other providers like NotificationService.
 */
@Global()
@Module({
  providers: [
    {
      provide: PgBoss,
      useFactory: (configService: ConfigService) => {
        const config = buildPgBossConfig(configService);
        return new PgBoss({
          connectionString: buildConnectionString(config),
          schema: config.schema,
        });
      },
      inject: [ConfigService],
    },
    PgBossService,
    NotificationService,
    EchoJob,
    FlakyJob,
    SlowJob,
  ],
  exports: [PgBossService],
})
export class PgBossModule {}
