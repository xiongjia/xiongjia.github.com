import { BadRequestException, HttpException } from "@nestjs/common";
import type { Response } from "express";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueueFullError } from "../run/queue";
import type { RunRecord } from "../run/run";
import type { FlowService } from "./flow.service";
import { FlowsController } from "./flows.controller";

const RECORD: RunRecord = {
  id: "20260101T000000000Z-aaaaaa",
  flow: "demo-visit",
  profile: "main",
  state: "succeeded",
  createdAt: "2026-01-01T00:00:00.000Z",
  startedAt: "2026-01-01T00:00:01.000Z",
  finishedAt: "2026-01-01T00:00:02.000Z",
  input: {},
  meta: null,
  error: null,
};

function makeService() {
  const submit = vi.fn(async () => ({ record: RECORD, settled: false }));
  const service = {
    defaultProfile: "main",
    catalogue: vi.fn(async () => [
      {
        name: "demo-visit",
        kind: "flow" as const,
        includes: ["demo-read-page"],
      },
    ]),
    submit,
    get: vi.fn(async () => RECORD),
    output: vi.fn(async () => ({ heading: "x" })),
    list: vi.fn(async () => [RECORD]),
    cancel: vi.fn(async () => ({ ...RECORD, state: "cancelled" as const })),
    queueSnapshot: vi.fn(() => ({ running: RECORD.id, queued: ["q-1"] })),
    profileSummaries: vi.fn(async () => [
      {
        name: "main",
        engine: "camoufox" as const,
        os: "macos" as const,
        locale: "zh-CN",
        timezoneId: "Asia/Shanghai",
        hasBrowserDir: true,
        proxy: false,
      },
    ]),
    artifact: vi.fn(async () => ({
      buffer: Buffer.from("png"),
      contentType: "image/png",
    })),
    artifacts: vi.fn(async () => ({
      runId: RECORD.id,
      artifacts: ["visit.png", "failure.png"],
    })),
    updateProfile: vi.fn(async () => ({
      name: "main",
      engine: "camoufox" as const,
      os: "macos" as const,
      locale: "en-US",
      timezoneId: "Asia/Shanghai",
      hasBrowserDir: true,
      proxy: true,
    })),
    deleteProfile: vi.fn(async (name: string) => ({ deleted: name })),
  };
  return { service: service as unknown as FlowService, submit };
}

function makeRes() {
  const res = { status: vi.fn() } as unknown as Response;
  return { res, status: res.status as unknown as ReturnType<typeof vi.fn> };
}

describe("FlowsController", () => {
  let service: FlowService;
  let submit: ReturnType<typeof makeService>["submit"];
  let controller: FlowsController;

  beforeEach(() => {
    const made = makeService();
    service = made.service;
    submit = made.submit;
    controller = new FlowsController(service);
  });

  it("lists flows with their kind and include edges", async () => {
    expect(await controller.listFlows()).toEqual({
      flows: [
        { name: "demo-visit", kind: "flow", includes: ["demo-read-page"] },
      ],
      defaultProfile: "main",
    });
  });

  it("serves the flow DSL schema", () => {
    const schema = controller.flowSchema();
    expect(schema.$schema).toBe("https://json-schema.org/draft/2020-12/schema");
    expect(JSON.stringify(schema)).toContain('"desc"');
  });

  it("runs with the flow's defaults when there is no body at all", async () => {
    const { res, status } = makeRes();

    const body = await controller.startRun("demo-visit", undefined, res);

    expect(status).toHaveBeenCalledWith(202);
    expect(body.profile).toBe("main");
    expect(submit).toHaveBeenCalledWith("demo-visit", {
      profile: "main",
      input: undefined,
      waitMs: undefined,
    });
  });

  it("rejects a body it cannot read instead of crashing", async () => {
    const { res } = makeRes();
    const cases: unknown[] = [
      "text",
      7,
      [],
      { input: 5 },
      { input: [] },
      { profile: 7 },
      { inp: {} },
    ];

    for (const body of cases) {
      await expect(
        controller.startRun("demo-visit", body, res),
      ).rejects.toBeInstanceOf(BadRequestException);
    }
  });

  it("answers 202 while the run is still queued", async () => {
    const { res, status } = makeRes();
    const body = await controller.startRun("demo-visit", {}, res);

    expect(status).toHaveBeenCalledWith(202);
    expect(body.pollUrl).toBe("/api/v1/runs/20260101T000000000Z-aaaaaa");
    expect(body.settled).toBe(false);
    expect(submit).toHaveBeenCalledWith("demo-visit", {
      profile: "main",
      input: undefined,
      waitMs: undefined,
    });
  });

  it("answers 200 when ?wait= covered the whole run", async () => {
    const { res, status } = makeRes();
    submit.mockResolvedValueOnce({ record: RECORD, settled: true });

    const body = await controller.startRun("demo-visit", {}, res, "5000");

    expect(status).toHaveBeenCalledWith(200);
    expect(body.settled).toBe(true);
    expect(submit).toHaveBeenCalledWith("demo-visit", {
      profile: "main",
      input: undefined,
      waitMs: 5_000,
    });
  });

  it("caps ?wait= and ignores nonsense", async () => {
    const { res } = makeRes();
    await controller.startRun(
      "demo-visit",
      { profile: "second" },
      res,
      "999999",
    );
    expect(submit).toHaveBeenLastCalledWith("demo-visit", {
      profile: "second",
      input: undefined,
      waitMs: 60_000,
    });

    await controller.startRun("demo-visit", {}, res, "soon");
    expect(submit).toHaveBeenLastCalledWith("demo-visit", {
      profile: "main",
      input: undefined,
      waitMs: undefined,
    });
  });

  it("passes the caller's input straight through", async () => {
    const { res } = makeRes();
    await controller.startRun("demo-visit", { input: { url: "x" } }, res);
    expect(submit).toHaveBeenCalledWith("demo-visit", {
      profile: "main",
      input: { url: "x" },
      waitMs: undefined,
    });
  });

  it("parses run filters and clamps the limit", async () => {
    await controller.listRuns("running,queued", "main", "demo-visit", "20");
    expect(service.list).toHaveBeenCalledWith({
      state: ["running", "queued"],
      profile: "main",
      flow: "demo-visit",
      limit: 20,
    });

    await controller.listRuns();
    expect(service.list).toHaveBeenLastCalledWith({
      state: undefined,
      profile: undefined,
      flow: undefined,
      limit: 20,
    });

    await controller.listRuns(undefined, undefined, undefined, "9999");
    expect(service.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 200 }),
    );
  });

  it("rejects an unknown run state", async () => {
    await expect(controller.listRuns("napping")).rejects.toBeInstanceOf(
      BadRequestException,
    );
  });

  it("serves output, single runs and cancels", async () => {
    expect(await controller.runOutput(RECORD.id)).toEqual({ heading: "x" });
    expect((await controller.getRun(RECORD.id)).pollUrl).toBe(
      `/api/v1/runs/${RECORD.id}`,
    );
    expect((await controller.cancelRun(RECORD.id)).state).toBe("cancelled");
  });

  it("lists profiles without leaking the preset", async () => {
    expect(await controller.listProfiles()).toEqual({
      defaultProfile: "main",
      profiles: [
        {
          name: "main",
          engine: "camoufox",
          os: "macos",
          locale: "zh-CN",
          timezoneId: "Asia/Shanghai",
          hasBrowserDir: true,
          proxy: false,
        },
      ],
    });
  });

  it("streams a run artifact", async () => {
    const res = {
      status: vi.fn(),
      setHeader: vi.fn(),
      end: vi.fn(),
    } as unknown as Response;

    await controller.runArtifact(RECORD.id, "visit.png", res);

    expect(service.artifact).toHaveBeenCalledWith(RECORD.id, "visit.png");
    expect(
      (res as unknown as { setHeader: ReturnType<typeof vi.fn> }).setHeader,
    ).toHaveBeenCalledWith("Content-Type", "image/png");
    expect(
      (res as unknown as { end: ReturnType<typeof vi.fn> }).end,
    ).toHaveBeenCalled();
  });

  it("lists a run's artifacts", async () => {
    expect(await controller.runArtifacts(RECORD.id)).toEqual({
      runId: RECORD.id,
      artifacts: ["visit.png", "failure.png"],
    });
  });

  it("streams run events until the run is terminal", async () => {
    const res = {
      setHeader: vi.fn(),
      flushHeaders: vi.fn(),
      write: vi.fn(),
      end: vi.fn(),
      on: vi.fn(),
    } as unknown as Response;

    await controller.runEvents(RECORD.id, res);

    const typed = res as unknown as {
      setHeader: ReturnType<typeof vi.fn>;
      write: ReturnType<typeof vi.fn>;
      end: ReturnType<typeof vi.fn>;
      on: ReturnType<typeof vi.fn>;
    };
    expect(typed.setHeader).toHaveBeenCalledWith(
      "Content-Type",
      "text/event-stream",
    );
    expect(typed.write).toHaveBeenCalledWith(expect.stringContaining("data: "));
    expect(typed.end).toHaveBeenCalled();
    expect(typed.on).toHaveBeenCalledWith("close", expect.any(Function));
  });

  it("patches a profile and rejects a body that is not an object", async () => {
    expect(
      await controller.updateProfile("main", { locale: "en-US" }),
    ).toMatchObject({ locale: "en-US" });
    expect(service.updateProfile).toHaveBeenCalledWith("main", {
      locale: "en-US",
    });

    await expect(
      controller.updateProfile("main", "nope"),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it("deletes a profile", async () => {
    expect(await controller.deleteProfile("second")).toEqual({
      deleted: "second",
    });
  });

  it("reports the queue of a profile", () => {
    expect(controller.queue("main")).toEqual({
      profile: "main",
      running: RECORD.id,
      queued: ["q-1"],
    });
  });

  it("maps a full queue to 429", async () => {
    submit.mockRejectedValueOnce(new QueueFullError("main", 8));
    const { res } = makeRes();

    const error = await controller
      .startRun("demo-visit", {}, res)
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(HttpException);
    expect((error as HttpException).getStatus()).toBe(429);
  });

  it("maps a broken flow to 400, keeping its message", async () => {
    submit.mockRejectedValueOnce(new Error('unknown flow "nope"'));
    const { res } = makeRes();

    const error = await controller
      .startRun("nope", {}, res)
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(BadRequestException);
    expect((error as BadRequestException).message).toContain("unknown flow");
  });
});
