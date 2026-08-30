#!/usr/bin/env node
/**
 * Start the @pg-boss/dashboard web UI against the same Postgres the app uses.
 *
 * Reads DB_* (and PGBOSS_SCHEMA) from .env.dev.local, falling back to .env —
 * exactly like the app does — and builds the DATABASE_URL for the dashboard.
 *
 * Usage:  pnpm dashboard            # http://localhost:3001
 *         DASHBOARD_PORT=3100 pnpm dashboard
 *
 * Prerequisite: the pg-boss schema must exist (start the app once, or run the
 * app / a worker so boss.start() creates it).
 */
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";

function parseEnvFile(path) {
  if (!existsSync(path)) {
    return {};
  }
  const out = {};
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (trimmed === "" || trimmed.startsWith("#")) {
      continue;
    }
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (match) {
      out[match[1]] = match[2].replace(/^["']|["']$/g, "");
    }
  }
  return out;
}

const envFromFiles = {
  ...parseEnvFile(".env"),
  ...parseEnvFile(".env.dev.local"),
};

const user = envFromFiles.DB_USER ?? "pgboss";
const password = envFromFiles.DB_PASSWORD ?? "pgboss";
const host = envFromFiles.DB_HOST ?? "127.0.0.1";
const port = envFromFiles.DB_PORT ?? "5432";
const database = envFromFiles.DB_NAME ?? "pgboss";
// Host is not URL-encoded: IPv6 hosts must stay literal inside brackets
// (`[::1]`); encoding their colons would break the connection string.
const formatHost = (value) => (value.includes(":") ? `[${value}]` : value);
const databaseUrl = `postgres://${encodeURIComponent(user)}:${encodeURIComponent(password)}@${formatHost(host)}:${port}/${encodeURIComponent(database)}`;

const dashboardPort = process.env.DASHBOARD_PORT ?? "3001";

const child = spawn("pnpm", ["exec", "pg-boss-dashboard"], {
  stdio: "inherit",
  env: {
    ...process.env,
    DATABASE_URL: databaseUrl,
    PGBOSS_SCHEMA: envFromFiles.PGBOSS_SCHEMA ?? "pgboss",
    PORT: dashboardPort,
  },
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
