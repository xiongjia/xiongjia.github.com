import { INestApplication } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import request from "supertest";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { AppModule } from "../src/app.module";
import { PgBossService } from "../src/pg-boss/pg-boss.service";

/**
 * End-to-end test against the real Postgres (docker compose) — run with:
 *
 *   pnpm db:start   # developer-run, once
 *   pnpm test:e2e
 *
 * The full Nest app boots (PgBossService connects to the real DB, registers
 * the demo queues and workers), jobs are enqueued over HTTP and polled until
 * completed. After the run the jobs created by this suite are deleted via
 * PgBossService.deleteJob — anything you enqueued manually is left untouched.
 */

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForJobState(
  app: INestApplication,
  id: string,
  expected: string,
  timeoutMs = 15000,
): Promise<Record<string, unknown>> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await request(app.getHttpServer()).get(`/jobs/${id}`);
    if (res.status === 404) {
      throw new Error(`job ${id} not found while waiting for '${expected}'`);
    }
    if (res.status === 200 && res.body.state === expected) {
      return res.body;
    }
    await sleep(300);
  }
  throw new Error(
    `job ${id} did not reach '${expected}' within ${timeoutMs}ms`,
  );
}

describe("jobs e2e (real Postgres)", () => {
  let app: INestApplication | undefined;
  const createdJobIds: string[] = [];

  beforeAll(async () => {
    app = await NestFactory.create(AppModule, { logger: false });
    app.enableShutdownHooks();
    await app.listen(0); // random port — never collides with the dev server
  });

  afterAll(async () => {
    // Clean up only the jobs this suite created (leave manual data alone).
    if (app === undefined) {
      return;
    }
    const pgBoss = app.get(PgBossService);
    for (const id of createdJobIds) {
      try {
        await pgBoss.deleteJob("echo", id);
      } catch (error) {
        console.warn(`cleanup skipped for job ${id}: ${String(error)}`);
      }
    }
    await app.close();
  });

  it("GET /health reports the DB and pg-boss schema as up", async () => {
    const res = await request(app.getHttpServer()).get("/health").expect(200);
    expect(res.body).toMatchObject({
      db: "up",
      installed: true,
    });
    expect(typeof res.body.schemaVersion).toBe("number");
  });

  it("enqueues an echo job, polls it to completed and returns the result", async () => {
    const createRes = await request(app.getHttpServer())
      .post("/jobs")
      .send({ type: "echo", payload: { message: "e2e hello" } })
      .expect(201);

    const id = createRes.body.id as string;
    expect(typeof id).toBe("string");
    createdJobIds.push(id);

    const job = await waitForJobState(app, id, "completed");
    expect(job.output).toMatchObject({ received: "e2e hello" });
  });

  it("rejects an unknown queue type with 400", async () => {
    await request(app.getHttpServer())
      .post("/jobs")
      .send({ type: "nope", payload: {} })
      .expect(400);
  });

  it("rejects a mistyped send option with 400", async () => {
    // retryLimit must be a number — a string must not reach pg-boss.
    await request(app.getHttpServer())
      .post("/jobs")
      .send({ type: "echo", payload: {}, options: { retryLimit: "5" } })
      .expect(400);
  });

  it("rejects a non-object payload with 400", async () => {
    await request(app.getHttpServer())
      .post("/jobs")
      .send({ type: "echo", payload: "just a string" })
      .expect(400);
  });
});
