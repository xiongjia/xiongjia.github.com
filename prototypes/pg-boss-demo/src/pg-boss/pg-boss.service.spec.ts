import { Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { ModuleRef } from "@nestjs/core";
import { Test } from "@nestjs/testing";
import { PgBoss } from "pg-boss";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { buildPgBossConfig, buildConnectionString } from "./pg-boss.config";
import { PgBossService } from "./pg-boss.service";

/**
 * Unit tests for PgBossService, following the NestJS testing guide
 * (https://docs.nestjs.com/fundamentals/testing): a testing module is compiled
 * with Test.createTestingModule and the PgBoss instance (constructor-injected)
 * is replaced with a `useValue` mock — no module-level mocks, no real DB.
 */

type BossMock = {
  on: Mock;
  start: Mock;
  stop: Mock;
  createQueue: Mock;
  work: Mock;
  send: Mock;
  complete: Mock;
  cancel: Mock;
  retry: Mock;
  getQueueStats: Mock;
  getDb: () => { executeSql: Mock };
  isInstalled: Mock;
  schemaVersion: Mock;
  deleteJob: Mock;
};

function createBossMock(): BossMock {
  const executeSql = vi.fn().mockResolvedValue({ rows: [] });
  return {
    on: vi.fn(),
    start: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
    createQueue: vi.fn().mockResolvedValue(undefined),
    work: vi.fn().mockResolvedValue(undefined),
    send: vi.fn().mockResolvedValue("job-1"),
    complete: vi.fn().mockResolvedValue({}),
    cancel: vi.fn().mockResolvedValue({}),
    retry: vi.fn().mockResolvedValue({}),
    getQueueStats: vi.fn().mockResolvedValue([]),
    getDb: () => ({ executeSql }),
    isInstalled: vi.fn().mockResolvedValue(true),
    schemaVersion: vi.fn().mockResolvedValue(27),
    deleteJob: vi.fn().mockResolvedValue({}),
  };
}

type ConfigMock = { get: Mock };

function createConfigMock(env: Record<string, string> = {}): ConfigMock {
  return {
    get: vi.fn((key: string, fallback?: string) =>
      key in env ? env[key] : fallback,
    ),
  };
}

describe("PgBossService", () => {
  let boss: BossMock;
  let config: ConfigMock;
  let moduleRef: { get: Mock };
  let service: PgBossService;

  /** The env values the ConfigService mock returns for the current test. */
  let env: Record<string, string>;

  beforeEach(async () => {
    env = {};
    boss = createBossMock();
    config = createConfigMock(env);
    moduleRef = { get: vi.fn().mockReturnValue({ run: vi.fn() }) };

    const moduleRefTesting = await Test.createTestingModule({
      providers: [
        PgBossService,
        { provide: ConfigService, useValue: config },
        { provide: PgBoss, useValue: boss },
        { provide: ModuleRef, useValue: moduleRef },
      ],
    }).compile();

    service = moduleRefTesting.get(PgBossService);
  });

  function setEnv(values: Record<string, string>): void {
    Object.assign(env, values);
  }

  describe("lifecycle", () => {
    it("listens to the pg-boss error event on module init", async () => {
      await service.onModuleInit();
      expect(boss.on).toHaveBeenCalledWith("error", expect.any(Function));
    });

    it("starts pg-boss and registers the three demo queues with configured options", async () => {
      setEnv({
        PGBOSS_RETRY_LIMIT: "4",
        PGBOSS_RETRY_DELAY: "7",
        PGBOSS_RETRY_BACKOFF: "false",
        PGBOSS_EXPIRE_SECONDS: "120",
        PGBOSS_DELETE_AFTER_SECONDS: "1800",
        PGBOSS_WORKER_CONCURRENCY: "5",
      });

      await service.onModuleInit();

      expect(boss.start).toHaveBeenCalledTimes(1);
      expect(boss.createQueue).toHaveBeenCalledTimes(3);
      expect(boss.createQueue.mock.calls.map((call) => call[0])).toEqual([
        "echo",
        "flaky",
        "slow",
      ]);
      for (const call of boss.createQueue.mock.calls) {
        expect(call[1]).toMatchObject({
          retryLimit: 4,
          retryDelay: 7,
          retryBackoff: false,
          expireInSeconds: 120,
          deleteAfterSeconds: 1800,
        });
      }
      expect(boss.work).toHaveBeenCalledTimes(3);
      for (const call of boss.work.mock.calls) {
        expect(call[1]).toMatchObject({ localConcurrency: 5, batchSize: 1 });
      }
    });

    it("resolves the handler classes through the DI container (ModuleRef)", async () => {
      await service.onModuleInit();
      expect(moduleRef.get).toHaveBeenCalledTimes(3);
      // each work handler calls handler.run(jobs, ctx)
      for (const call of boss.work.mock.calls) {
        await call[2]([{ id: "j1" }]);
      }
      expect(moduleRef.get.mock.results[0].value.run).toHaveBeenCalled();
    });

    it("stops pg-boss on application shutdown", async () => {
      await service.onModuleInit();
      await service.onApplicationShutdown();
      expect(boss.stop).toHaveBeenCalledTimes(1);
    });

    it("propagates a start() failure instead of swallowing it", async () => {
      boss.start.mockRejectedValueOnce(new Error("db down"));
      await expect(service.onModuleInit()).rejects.toThrow("db down");
    });
  });

  describe("delegations", () => {
    it("send() forwards queue, data and options and returns the id", async () => {
      boss.send.mockResolvedValueOnce("abc");
      const id = await service.send("echo", { message: "hi" }, { priority: 3 });
      expect(id).toBe("abc");
      expect(boss.send).toHaveBeenCalledWith(
        "echo",
        { message: "hi" },
        { priority: 3 },
      );
    });

    it("send() returns null when the job was not enqueued (dedup)", async () => {
      boss.send.mockResolvedValueOnce(null);
      await expect(service.send("echo", {})).resolves.toBeNull();
    });

    it("cancel() and retry() forward queue + id", async () => {
      await service.cancel("slow", "job-9");
      await service.retry("slow", "job-9");
      expect(boss.cancel).toHaveBeenCalledWith("slow", "job-9");
      expect(boss.retry).toHaveBeenCalledWith("slow", "job-9");
    });

    it("getQueueStats() queries each registered queue and flattens the results", async () => {
      boss.getQueueStats
        .mockResolvedValueOnce([{ name: "echo", queuedCount: 1 }])
        .mockResolvedValueOnce([{ name: "flaky", queuedCount: 2 }])
        .mockResolvedValueOnce([{ name: "slow", queuedCount: 3 }]);
      const stats = await service.getQueueStats();
      expect(boss.getQueueStats).toHaveBeenCalledTimes(3);
      expect(stats.map((s) => s.name)).toEqual(["echo", "flaky", "slow"]);
    });

    it("health() reports db up with the schema version", async () => {
      boss.isInstalled.mockResolvedValueOnce(true);
      boss.schemaVersion.mockResolvedValueOnce(27);
      await expect(service.health()).resolves.toEqual({
        db: "up",
        installed: true,
        schemaVersion: 27,
      });
    });

    it("health() reports db down when the DB queries fail", async () => {
      boss.isInstalled.mockRejectedValueOnce(new Error("connection refused"));
      // Silence the expected error log and assert the failure is reported.
      const errorSpy = vi
        .spyOn(Logger.prototype, "error")
        .mockImplementation(() => undefined);
      await expect(service.health()).resolves.toEqual({
        db: "down",
        installed: false,
        schemaVersion: null,
      });
      expect(errorSpy).toHaveBeenCalled();
      errorSpy.mockRestore();
    });

    it("deleteJob() forwards queue + id (test cleanup helper)", async () => {
      await service.deleteJob("echo", "job-1");
      expect(boss.deleteJob).toHaveBeenCalledWith("echo", "job-1");
    });
  });

  describe("read-only SQL queries", () => {
    it("listJobs() queries the pgboss.job table with queue + state filter", async () => {
      setEnv({ PGBOSS_SCHEMA: "myschema" });
      await service.onModuleInit();
      const executeSql = boss.getDb().executeSql;
      executeSql.mockResolvedValueOnce({
        rows: [
          {
            id: "j1",
            name: "echo",
            state: "completed",
            data: { message: "hi" },
            output: { received: "hi" },
            retry_count: 0,
            retry_limit: 2,
            retry_delay: 0,
            priority: 0,
            created_on: new Date("2026-01-01T00:00:00Z"),
            started_on: new Date("2026-01-01T00:00:01Z"),
            completed_on: new Date("2026-01-01T00:00:02Z"),
          },
        ],
      });

      const jobs = await service.listJobs("echo", "completed", 10);

      const sql = String(executeSql.mock.calls[0][0]);
      expect(sql).toContain("FROM myschema.job");
      expect(sql).toContain("state = $2");
      expect(executeSql.mock.calls[0][1]).toEqual(["echo", "completed", 10]);
      expect(jobs).toHaveLength(1);
      expect(jobs[0]).toMatchObject({
        id: "j1",
        queue: "echo",
        state: "completed",
        createdAt: "2026-01-01T00:00:00.000Z",
      });
    });

    it("findJobById() returns null when no row matches", async () => {
      boss.getDb().executeSql.mockResolvedValueOnce({ rows: [] });
      await expect(service.findJobById("missing")).resolves.toBeNull();
    });
  });
});

describe("pg-boss.config", () => {
  it("builds the config from ConfigService values with sensible fallbacks", () => {
    const config = createConfigMock({
      DB_HOST: "db.local",
      DB_PORT: "5433",
      DB_USER: "u",
      DB_PASSWORD: "p",
      DB_NAME: "d",
      PGBOSS_SCHEMA: "boss",
      PGBOSS_WORKER_CONCURRENCY: "5",
    });
    const parsed = buildPgBossConfig(config as unknown as ConfigService);
    expect(parsed).toMatchObject({
      host: "db.local",
      port: 5433,
      user: "u",
      password: "p",
      database: "d",
      schema: "boss",
      workerConcurrency: 5,
    });
    expect(buildConnectionString(parsed)).toBe(
      "postgres://u:p@db.local:5433/d",
    );
  });

  it("falls back to defaults for missing values", () => {
    const config = createConfigMock({});
    const parsed = buildPgBossConfig(config as unknown as ConfigService);
    expect(parsed).toMatchObject({
      host: "127.0.0.1",
      port: 5432,
      user: "pgboss",
      schema: "pgboss",
      retryLimit: 2,
      retryBackoff: true,
      workerConcurrency: 3,
    });
  });
});
