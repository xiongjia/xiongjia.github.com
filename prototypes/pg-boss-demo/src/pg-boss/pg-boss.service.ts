import {
  Inject,
  Injectable,
  Logger,
  OnApplicationShutdown,
  OnModuleInit,
} from "@nestjs/common";
import { ModuleRef } from "@nestjs/core";
import { ConfigService } from "@nestjs/config";
import { PgBoss, type QueueOptions, type SendOptions } from "pg-boss";
import type { QueueStats } from "pg-boss";
import { buildPgBossConfig } from "./pg-boss.config";
import {
  buildRegistry,
  type HandlerContext,
  type JobHandlerRegistration,
} from "./handlers/registry";
import type { QueueName } from "./pg-boss.constants";
import { isRegisteredQueue, REGISTERED_QUEUES } from "./pg-boss.constants";
import type {
  HealthStatus,
  JobDetail,
  JobListItem,
  JobPayload,
  JobState,
  PgBossConfig,
} from "./pg-boss.types";
import { toJobDetail, toJobListItem, toJobRow } from "./pg-boss.types";

/**
 * NestJS wrapper around pg-boss 12.
 *
 * - Owns the PgBoss lifecycle: `start()` on module init, `stop()` on shutdown.
 * - The PgBoss instance is constructor-injected (provided by PgBossModule from
 *   @nestjs/config values — see pg-boss.config.ts) so tests can replace it
 *   with a mock via Test.createTestingModule({ provide: PgBoss, useValue }).
 * - Creates the demo queues and registers their workers from the handler registry.
 * - Exposes typed delegations for the REST layer (send / find / stats / cancel / retry).
 */
@Injectable()
export class PgBossService implements OnModuleInit, OnApplicationShutdown {
  private readonly logger = new Logger(PgBossService.name);
  private config: PgBossConfig | undefined;

  constructor(
    private readonly configService: ConfigService,
    private readonly moduleRef: ModuleRef,
    @Inject(PgBoss) private readonly boss: PgBoss,
  ) {}

  // --- lifecycle ---------------------------------------------------------

  async onModuleInit(): Promise<void> {
    const config = buildPgBossConfig(this.configService);
    this.config = config;

    // pg-boss emits internal errors (connection drops, maintenance failures)
    // through the 'error' event — without a listener they crash the process.
    this.boss.on("error", (error: Error) => {
      this.logger.error(`pg-boss error: ${error.message}`, error.stack);
    });

    await this.boss.start();
    this.logger.log(`pg-boss connected (schema '${config.schema}')`);

    const registry = buildRegistry(config.workerConcurrency);
    for (const registration of registry) {
      await this.setupQueue(registration, config);
    }
    this.logger.log(
      `queues ready: ${registry.map((r) => r.queue).join(", ")} (localConcurrency=${config.workerConcurrency})`,
    );
  }

  async onApplicationShutdown(): Promise<void> {
    await this.boss.stop();
    this.logger.log("pg-boss stopped");
  }

  private async setupQueue(
    registration: JobHandlerRegistration,
    config: PgBossConfig,
  ): Promise<void> {
    await this.boss.createQueue(registration.queue, this.queueOptions(config));
    // Handlers are @Injectable() classes: resolve them through the DI container
    // so their constructor-injected services (e.g. NotificationService) work.
    const handler = this.moduleRef.get(registration.handlerClass, {
      strict: false,
    });
    const ctx: HandlerContext = {
      complete: async (id, output) => {
        await this.boss.complete(registration.queue, id, output);
      },
    };
    await this.boss.work<JobPayload, void>(
      registration.queue,
      registration.workOptions,
      (jobs) => handler.run(jobs, ctx),
    );
    this.logger.log(
      `queue '${registration.queue}' registered (${registration.workOptions.localConcurrency} workers)`,
    );
  }

  private queueOptions(config: PgBossConfig): QueueOptions {
    return {
      retryLimit: config.retryLimit,
      retryDelay: config.retryDelay,
      retryBackoff: config.retryBackoff,
      expireInSeconds: config.expireInSeconds,
      deleteAfterSeconds: config.deleteAfterSeconds,
    };
  }

  // --- REST-layer delegations ---------------------------------------------

  /** Enqueue a job. Returns the job id, or null when it was not enqueued (e.g. singleton dedup). */
  async send(
    queue: QueueName,
    data: JobPayload,
    options?: SendOptions,
  ): Promise<string | null> {
    return this.boss.send(queue, data, options ?? {});
  }

  /** List jobs of a queue via read-only SQL (findJobs has no state filter in v12). */
  async listJobs(
    queue: string,
    state?: JobState,
    limit = 50,
  ): Promise<JobListItem[]> {
    const values: unknown[] = [queue];
    let where = "name = $1";
    if (state !== undefined) {
      values.push(state);
      where += ` AND state = $${values.length}`;
    }
    values.push(limit);
    // `schema` comes from PGBOSS_SCHEMA config (developer-set, not user input),
    // so interpolating it here is safe; queue/state/limit are parameterized.
    const sql =
      `SELECT id, name, state, data, output, retry_count, retry_limit, retry_delay, priority, created_on, started_on, completed_on ` +
      `FROM ${this.schema}.job WHERE ${where} ORDER BY created_on DESC LIMIT $${values.length}`;
    const { rows } = await this.boss.getDb().executeSql(sql, values);
    return rows.map((row) =>
      toJobListItem(toJobRow(row as Record<string, unknown>)),
    );
  }

  /** Fetch one job by id (any queue) via read-only SQL. */
  async findJobById(id: string): Promise<JobDetail | null> {
    const sql =
      `SELECT id, name, state, data, output, retry_count, retry_limit, retry_delay, priority, created_on, started_on, completed_on ` +
      `FROM ${this.schema}.job WHERE id = $1 LIMIT 1`;
    const { rows } = await this.boss.getDb().executeSql(sql, [id]);
    if (rows.length === 0) {
      return null;
    }
    return toJobDetail(toJobRow(rows[0] as Record<string, unknown>));
  }

  /** Cancel an unfinished job. */
  async cancel(queue: string, id: string): Promise<void> {
    await this.boss.cancel(queue, id);
  }

  /** Re-queue a failed job for another attempt. */
  async retry(queue: string, id: string): Promise<void> {
    await this.boss.retry(queue, id);
  }

  /** Delete one job — used by tests/e2e to leave no data behind. */
  async deleteJob(queue: string, id: string): Promise<void> {
    await this.boss.deleteJob(queue, id);
  }

  /** DB reachability + pg-boss schema state (isInstalled/schemaVersion hit the DB). */
  async health(): Promise<HealthStatus> {
    try {
      const installed = await this.boss.isInstalled();
      const schemaVersion = await this.boss.schemaVersion();
      return { db: "up", installed, schemaVersion };
    } catch (error) {
      this.logger.error(
        `health check failed: ${error instanceof Error ? error.message : String(error)}`,
      );
      return { db: "down", installed: false, schemaVersion: null };
    }
  }

  /** Live queue stats for every demo queue (v12: getQueueStats needs a queue name). */
  async getQueueStats(): Promise<QueueStats[]> {
    const results = await Promise.all(
      REGISTERED_QUEUES.map((queue) => this.boss.getQueueStats(queue)),
    );
    return results.flat();
  }

  /** True when the queue name is one of the registered demo queues. */
  isRegisteredQueue(queue: string): queue is QueueName {
    return isRegisteredQueue(queue);
  }

  // --- internals -----------------------------------------------------------

  private get schema(): string {
    return this.config?.schema ?? "pgboss";
  }
}
