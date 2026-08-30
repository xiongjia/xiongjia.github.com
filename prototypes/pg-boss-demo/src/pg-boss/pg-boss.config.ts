import { ConfigService } from "@nestjs/config";
import type { PgBossConfig } from "./pg-boss.types";

/**
 * Configuration assembly shared by the PgBossModule factory (which builds the
 * PgBoss instance) and PgBossService (which derives queue options from it).
 * All values come from @nestjs/config, i.e. `.env.dev.local` → `.env`.
 */

export function buildPgBossConfig(configService: ConfigService): PgBossConfig {
  return {
    host: readString(configService, "DB_HOST", "127.0.0.1"),
    port: readNumber(configService, "DB_PORT", 5432),
    user: readString(configService, "DB_USER", "pgboss"),
    password: readString(configService, "DB_PASSWORD", "pgboss"),
    database: readString(configService, "DB_NAME", "pgboss"),
    schema: readString(configService, "PGBOSS_SCHEMA", "pgboss"),
    retryLimit: readNumber(configService, "PGBOSS_RETRY_LIMIT", 2),
    retryDelay: readNumber(configService, "PGBOSS_RETRY_DELAY", 5),
    retryBackoff: readBoolean(configService, "PGBOSS_RETRY_BACKOFF", true),
    expireInSeconds: readNumber(configService, "PGBOSS_EXPIRE_SECONDS", 300),
    deleteAfterSeconds: readNumber(
      configService,
      "PGBOSS_DELETE_AFTER_SECONDS",
      3600,
    ),
    workerConcurrency: readNumber(
      configService,
      "PGBOSS_WORKER_CONCURRENCY",
      3,
    ),
  };
}

export function buildConnectionString(config: PgBossConfig): string {
  return `postgres://${config.user}:${config.password}@${config.host}:${config.port}/${config.database}`;
}

function readString(
  configService: ConfigService,
  key: string,
  fallback: string,
): string {
  return configService.get<string>(key) ?? fallback;
}

function readNumber(
  configService: ConfigService,
  key: string,
  fallback: number,
): number {
  const raw = configService.get<string>(key);
  if (raw === undefined || raw === "") {
    return fallback;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readBoolean(
  configService: ConfigService,
  key: string,
  fallback: boolean,
): boolean {
  const raw = configService.get<string>(key);
  if (raw === undefined) {
    return fallback;
  }
  return raw === "true";
}
