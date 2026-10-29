import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Page } from "playwright-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FlowError } from "./errors";
import { FLOW_API_VERSION, parseFlow, type FlowFile } from "./schema";
import { runFlow, type RunContext } from "./step-runner";

const UA = "Mozilla/5.0 (Macintosh) Firefox/156.0";

interface FakeOptions {
  /** Selectors the fake page "has". */
  elements?: Record<string, string>;
  bodyText?: string;
  rows?: Record<string, Array<Record<string, string | null>>>;
}

function makePage(options: FakeOptions = {}): Page {
  const elements = options.elements ?? {};
  const locatorFor = (selector: string) => {
    const present = selector in elements;
    const locator = {
      count: vi.fn(async () => (present ? 1 : 0)),
      click: vi.fn(async () => {
        if (!present) throw new Error(`no element ${selector}`);
      }),
      fill: vi.fn(async () => {
        if (!present) throw new Error(`no element ${selector}`);
      }),
      press: vi.fn(async () => undefined),
      textContent: vi.fn(async () => (present ? elements[selector] : null)),
      isVisible: vi.fn(async () => present),
      waitFor: vi.fn(async () => {
        if (!present) throw new Error("Timeout exceeded");
      }),
      screenshot: vi.fn(async ({ path }: { path: string }) => {
        await import("node:fs/promises").then((fs) =>
          fs.writeFile(path, "png"),
        );
      }),
    };
    return locator;
  };
  const locators = new Map<string, ReturnType<typeof locatorFor>>();

  return {
    goto: vi.fn(async () => null),
    waitForTimeout: vi.fn(async () => undefined),
    url: () => "https://example.test/demo",
    keyboard: { press: vi.fn(async () => undefined) },
    screenshot: vi.fn(async ({ path }: { path: string }) => {
      const fs = await import("node:fs/promises");
      await fs.writeFile(path, "png");
    }),
    locator: (selector: string) => {
      const cached = locators.get(selector) ?? locatorFor(selector);
      locators.set(selector, cached);
      return { first: () => cached };
    },
    evaluate: vi.fn(async (fn: unknown, arg?: unknown) => {
      if (arg && typeof arg === "object" && "itemSelectors" in arg) {
        const { itemSelectors } = arg as { itemSelectors: string[] };
        return options.rows?.[itemSelectors[0]] ?? [];
      }
      return String(fn).includes("innerText") ? (options.bodyText ?? "") : UA;
    }),
  } as unknown as Page;
}

function makeFlow(steps: unknown[], output?: Record<string, string>): FlowFile {
  return parseFlow({
    name: "test",
    apiVersion: FLOW_API_VERSION,
    steps,
    output,
  });
}

function makeContext(
  page: Page,
  overrides: Partial<RunContext> = {},
): RunContext {
  return {
    page,
    input: {},
    self: "http://127.0.0.1:8765",
    vars: {},
    meta: {
      url: "",
      userAgent: "",
      usedSelectors: {},
      screenshots: {},
      steps: [],
    },
    artifactsDir: null,
    ...overrides,
  };
}

describe("runFlow", () => {
  let artifactsDir: string;

  beforeEach(async () => {
    artifactsDir = await mkdtemp(join(tmpdir(), "harvester-artifacts-"));
  });

  afterEach(async () => {
    await rm(artifactsDir, { recursive: true, force: true });
  });

  it("walks steps, captures values and maps them to output", async () => {
    const page = makePage({ elements: { "#title": " harvester demo page " } });
    const flow = makeFlow(
      [
        { action: "goto", url: "{{self}}/api/v1/demo" },
        { action: "wait", selector: "#title" },
        { action: "text", selector: "#title", as: "heading" },
      ],
      { heading: "heading" },
    );

    const { output, meta } = await runFlow(flow, makeContext(page));

    expect(output).toEqual({ heading: "harvester demo page" });
    expect(meta.url).toBe("https://example.test/demo");
    expect(meta.userAgent).toBe(UA);
    expect(meta.usedSelectors).toEqual({
      "2.wait": "#title",
      "3.text": "#title",
    });
    expect(page.goto).toHaveBeenCalledWith(
      "http://127.0.0.1:8765/api/v1/demo",
      {
        waitUntil: "domcontentloaded",
      },
    );
  });

  it("records a scenario log of every step", async () => {
    const page = makePage({ elements: { "#title": "hello" } });
    const flow = makeFlow([
      { desc: "open the page", action: "goto", url: "{{self}}/demo" },
      {
        desc: "read the heading",
        action: "text",
        selector: "#title",
        as: "heading",
      },
      { action: "wait", ms: 10 },
    ]);

    const { meta } = await runFlow(flow, makeContext(page));

    expect(
      meta.steps.map(({ step, desc, ok }) => ({ step, desc, ok })),
    ).toEqual([
      { step: "1.goto", desc: "open the page", ok: true },
      { step: "2.text", desc: "read the heading", ok: true },
      { step: "3.wait", desc: undefined, ok: true },
    ]);
    for (const trace of meta.steps) {
      expect(typeof trace.ms).toBe("number");
    }
  });

  it("runs a fragment with the caller's page, input and variables", async () => {
    const page = makePage({ elements: { "#title": "hello", "#bump": "" } });
    const fragment = parseFlow({
      name: "read-title",
      apiVersion: FLOW_API_VERSION,
      kind: "fragment",
      steps: [
        { action: "text", selector: "#title", as: "heading" },
        { action: "click", selector: "{{input.button}}" },
      ],
    });
    const flow = makeFlow(
      [
        { desc: "read it", action: "include", flow: "read-title" },
        { action: "text", selector: "#title", as: "again" },
      ],
      { heading: "heading", again: "again" },
    );
    const ctx = makeContext(page, {
      input: { button: "#bump" },
      resolve: async (name) => {
        expect(name).toBe("read-title");
        return fragment;
      },
    });

    const { output } = await runFlow(flow, ctx);

    expect(output).toEqual({ heading: "hello", again: "hello" });
    // The fragment resolved {{input.button}} against the caller's input.
    expect(ctx.meta.usedSelectors["1.2.click"]).toBe("#bump");
    expect(ctx.meta.steps.map((step) => step.step)).toEqual([
      "1.include",
      "1.1.text",
      "1.2.click",
      "2.text",
    ]);
    expect(ctx.meta.steps[0]).toMatchObject({
      action: "include",
      fragment: "read-title",
      desc: "read it",
      ok: true,
    });
  });

  it("refuses a fragment cycle instead of hanging", async () => {
    const flow = makeFlow([{ action: "include", flow: "loop-a" }]);
    const loopA = parseFlow({
      name: "loop-a",
      kind: "fragment",
      apiVersion: FLOW_API_VERSION,
      steps: [{ action: "include", flow: "loop-b" }],
    });
    const loopB = parseFlow({
      name: "loop-b",
      kind: "fragment",
      apiVersion: FLOW_API_VERSION,
      steps: [{ action: "include", flow: "loop-a" }],
    });
    const fragments: Record<string, typeof loopA> = {
      "loop-a": loopA,
      "loop-b": loopB,
    };
    const ctx = makeContext(makePage(), {
      resolve: async (name) => fragments[name],
    });

    await expect(runFlow(flow, ctx)).rejects.toMatchObject({
      code: "bad-fragment",
      message: "fragment cycle: loop-a → loop-b → loop-a",
    });
  });

  it("refuses to include something that is not a fragment", async () => {
    const flow = makeFlow([{ action: "include", flow: "plain-flow" }]);
    const plain = parseFlow({
      name: "plain-flow",
      apiVersion: FLOW_API_VERSION,
      steps: [{ action: "goto", url: "https://example.test/" }],
    });
    const ctx = makeContext(makePage(), { resolve: async () => plain });

    await expect(runFlow(flow, ctx)).rejects.toMatchObject({
      code: "bad-fragment",
      message: /is a flow, not a fragment/,
    });
  });

  it("refuses an include step when no resolver was provided", async () => {
    const flow = makeFlow([{ action: "include", flow: "anything" }]);
    await expect(runFlow(flow, makeContext(makePage()))).rejects.toMatchObject({
      code: "bad-fragment",
      message: /no flow resolver/,
    });
  });

  it("surfaces a fragment that cannot be loaded", async () => {
    const flow = makeFlow([{ action: "include", flow: "missing" }]);
    const ctx = makeContext(makePage(), {
      resolve: async () => {
        throw new Error('unknown flow "missing"');
      },
    });

    await expect(runFlow(flow, ctx)).rejects.toMatchObject({
      code: "bad-fragment",
      message: 'unknown flow "missing"',
    });
  });

  it("marks the step that failed and keeps what it knew about the page", async () => {
    const flow = makeFlow([
      { desc: "click the button", action: "click", selector: "#missing" },
    ]);
    const ctx = makeContext(makePage());

    await expect(runFlow(flow, ctx)).rejects.toMatchObject({
      // One selector is handed to Playwright, which waits and then times out.
      code: "timeout",
    });

    expect(ctx.meta.steps).toEqual([
      {
        step: "1.click",
        action: "click",
        desc: "click the button",
        ok: false,
        ms: expect.any(Number),
        error: {
          code: "timeout",
          message: "click on #missing failed: no element #missing",
        },
      },
    ]);
    expect(ctx.meta.url).toBe("https://example.test/demo");
    expect(ctx.meta.userAgent).toBe(UA);
  });

  it("uses the first candidate that exists", async () => {
    const page = makePage({ elements: { "#bump": "clicked" } });
    const flow = makeFlow([
      { action: "click", selector: ["#missing", "#bump"] },
      { action: "text", selector: ["#nope", "#bump"], as: "clickResult" },
    ]);

    const ctx = makeContext(page);
    await runFlow(flow, ctx);

    expect(ctx.meta.usedSelectors).toEqual({
      "1.click": "#bump",
      "2.text": "#bump",
    });
    expect(ctx.vars.clickResult).toBe("clicked");
  });

  it("fails with selector-not-found when no candidate matches", async () => {
    const flow = makeFlow([{ action: "click", selector: ["#a", "#b"] }]);
    await expect(runFlow(flow, makeContext(makePage()))).rejects.toMatchObject({
      code: "selector-not-found",
      message: 'none of ["#a","#b"] matched',
    });
  });

  it("waits for an element that does not exist yet", async () => {
    // `count()` stays 0 the whole time: the element only appears later, which is
    // exactly what `wait` has to handle.
    const appeared: string[] = [];
    const late = {
      url: () => "",
      evaluate: async () => "",
      locator: () => ({
        first: () => ({
          count: async () => 0,
          waitFor: async () => {
            appeared.push("waited");
          },
        }),
      }),
    } as unknown as Page;
    const flow = makeFlow([
      { action: "wait", selector: "#late", state: "visible", timeout: 700 },
    ]);

    const ctx = makeContext(late);
    await runFlow(flow, ctx);

    expect(appeared).toEqual(["waited"]);
    expect(ctx.meta.usedSelectors["1.wait"]).toBe("#late");
  });

  it("waits for any of several candidates and reports the one that showed up", async () => {
    const combined: string[] = [];
    interface Wrapped {
      first: () => unknown;
      or: () => Wrapped;
    }
    const page = {
      url: () => "",
      evaluate: async () => "",
      locator: (selector: string): Wrapped => {
        const present = selector === "#second";
        const inner = {
          count: async () => (present ? 1 : 0),
          waitFor: async () => {
            combined.push(selector);
          },
        };
        const wrapped: Wrapped = { first: () => inner, or: () => wrapped };
        return wrapped;
      },
    } as unknown as Page;
    const flow = makeFlow([
      {
        action: "wait",
        selector: ["#first", "#second"],
        state: "visible",
        timeout: 700,
      },
    ]);

    const ctx = makeContext(page);
    await runFlow(flow, ctx);

    expect(combined).toEqual(["#first"]);
    expect(ctx.meta.usedSelectors["1.wait"]).toBe("#second");
  });

  it("clicks an element that is not there yet", async () => {
    // A single selector is handed to Playwright, which waits for it.
    const clicked: string[] = [];
    const late = {
      url: () => "",
      evaluate: async () => "",
      locator: (selector: string) => ({
        first: () => ({
          count: async () => 0,
          click: async () => {
            clicked.push(selector);
          },
        }),
      }),
    } as unknown as Page;
    const flow = makeFlow([{ action: "click", selector: "#late" }]);

    const ctx = makeContext(late);
    await runFlow(flow, ctx);

    expect(clicked).toEqual(["#late"]);
    expect(ctx.meta.usedSelectors["1.click"]).toBe("#late");
  });

  it("times out when the element never becomes visible", async () => {
    const neverVisible = {
      url: () => "",
      evaluate: async () => "",
      locator: () => ({
        first: () => ({
          count: async () => 1,
          waitFor: async () => {
            throw new Error("Timeout exceeded");
          },
        }),
      }),
    } as unknown as Page;
    const flow = makeFlow([
      { action: "wait", selector: "#late", state: "visible", timeout: 50 },
    ]);

    await expect(
      runFlow(flow, makeContext(neverVisible)),
    ).rejects.toMatchObject({ code: "timeout" });
  });

  it("reads an attribute into a variable", async () => {
    const page = {
      url: () => "",
      evaluate: async () => "",
      locator: () => ({
        first: () => ({
          count: async () => 1,
          getAttribute: async (name: string) =>
            name === "href" ? " /user/profile/abc " : null,
        }),
      }),
    } as unknown as Page;
    const flow = makeFlow(
      [
        {
          action: "attribute",
          selector: [".user a", "a[href*='/user/profile']"],
          name: "href",
          as: "href",
        },
      ],
      { href: "href" },
    );

    const ctx = makeContext(page);
    const { output } = await runFlow(flow, ctx);

    expect(output.href).toBe("/user/profile/abc");
    expect(ctx.meta.usedSelectors["1.attribute"]).toBe(".user a");
  });

  it("can read an attribute per row in extract", async () => {
    const page = makePage();
    page.evaluate = (async () => [
      { name: "a", avatar: "https://img/a.png" },
    ]) as unknown as Page["evaluate"];
    const flow = makeFlow(
      [
        {
          action: "extract",
          item: ".row",
          fields: {
            name: "[class*='name']",
            avatar: { selector: "img", attr: "src" },
          },
          as: "rows",
        },
      ],
      { rows: "rows" },
    );

    const { output } = await runFlow(flow, makeContext(page));
    expect(output.rows).toEqual([{ name: "a", avatar: "https://img/a.png" }]);
  });

  it("skips a guarded step unless its template is truthy", async () => {
    const page = makePage({ elements: { "#title": "hello" } });
    const flow = makeFlow(
      [
        { action: "goto", url: "https://example.test/always" },
        {
          when: "{{input.profileId}}",
          action: "goto",
          url: "https://example.test/{{input.profileId}}",
        },
        {
          when: "!{{input.profileId}}",
          action: "goto",
          url: "https://example.test/own",
        },
      ],
      {},
    );

    const ctx = makeContext(page, { input: {} });
    await runFlow(flow, ctx);

    expect(page.goto).toHaveBeenCalledTimes(2);
    expect(page.goto).toHaveBeenLastCalledWith(
      "https://example.test/own",
      expect.anything(),
    );
    expect(ctx.meta.steps.map((step) => step.skipped ?? false)).toEqual([
      false,
      true,
      false,
    ]);
  });

  it("templates can read captured variables", async () => {
    const page = makePage({ elements: { "#title": "t" } });
    page.locator = ((selector: string) => ({
      first: () => ({
        count: async () => 1,
        getAttribute: async () => "https://example.test/page",
        textContent: async () => selector,
      }),
    })) as unknown as Page["locator"];
    const flow = makeFlow([
      { action: "attribute", selector: "#link", name: "href", as: "href" },
      { action: "goto", url: "{{vars.href}}" },
    ]);

    await runFlow(flow, makeContext(page));

    expect(page.goto).toHaveBeenLastCalledWith(
      "https://example.test/page",
      expect.anything(),
    );
  });

  it("extracts rows as JSON", async () => {
    const page = makePage({
      rows: { "body p": [{ text: "first" }, { text: "second" }] },
    });
    const flow = makeFlow(
      [
        {
          action: "extract",
          item: "body p",
          fields: { text: "p" },
          as: "paragraphs",
          limit: 10,
        },
      ],
      { paragraphs: "paragraphs" },
    );

    const { output } = await runFlow(flow, makeContext(page));
    expect(output.paragraphs).toEqual([{ text: "first" }, { text: "second" }]);
  });

  it("writes a screenshot into artifacts and records its path", async () => {
    const page = makePage();
    const flow = makeFlow([{ action: "screenshot", name: "visit" }]);
    const ctx = makeContext(page, { artifactsDir });

    const { meta } = await runFlow(flow, ctx);

    expect(meta.screenshots.visit).toBe("artifacts/visit.png");
    expect(await readFile(join(artifactsDir, "visit.png"), "utf8")).toBe("png");
  });

  it("flags a risk-control page instead of returning junk", async () => {
    const page = makePage({ bodyText: "安全限制: error_code=300012" });
    const flow = makeFlow([
      { action: "assertNotBlocked", patterns: ["安全限制"] },
    ]);
    await expect(runFlow(flow, makeContext(page))).rejects.toMatchObject({
      code: "blocked",
    });
  });

  it("runs the else branch when the selector is absent", async () => {
    const page = makePage({ elements: { "#fallback": "fallback" } });
    const flow = makeFlow(
      [
        {
          action: "if",
          selector: "#nope",
          then: [{ action: "text", selector: "#nope", as: "went" }],
          else: [{ action: "text", selector: "#fallback", as: "went" }],
        },
      ],
      { went: "went" },
    );

    const { output } = await runFlow(flow, makeContext(page));
    expect(output.went).toBe("fallback");
  });

  it("branches on visibility when asked to", async () => {
    const hidden = {
      url: () => "https://example.test/demo",
      evaluate: async () => "",
      goto: async () => null,
      locator: () => ({
        first: () => ({
          count: async () => 1,
          isVisible: async () => false,
          textContent: async () => "hidden text",
        }),
      }),
    } as unknown as Page;
    const flow = makeFlow([
      {
        action: "if",
        selector: "#hidden",
        state: "visible",
        then: [{ action: "text", selector: "#hidden", as: "went" }],
        else: [{ action: "goto", url: "https://example.test/else" }],
      },
    ]);

    const { output } = await runFlow(flow, makeContext(hidden));

    // The element exists but is invisible, so `else` ran and nothing was captured.
    expect(output).toEqual({});
  });

  it("drops duplicate rows when uniqueBy is given", async () => {
    const page = makePage({
      rows: {
        "body li": [
          { name: "a", desc: "1" },
          { name: "a", desc: "2" },
          { name: "b", desc: "3" },
        ],
      },
    });
    const flow = makeFlow(
      [
        {
          action: "extract",
          item: "body li",
          fields: { name: "span", desc: "em" },
          as: "rows",
          uniqueBy: ["name"],
        },
      ],
      { rows: "rows" },
    );

    const { output } = await runFlow(flow, makeContext(page));
    expect(output.rows).toEqual([
      { name: "a", desc: "1" },
      { name: "b", desc: "3" },
    ]);
  });

  it("scrolls a container until it stops moving", async () => {
    const rounds: number[] = [];
    let top = 0;
    const scroller = {
      url: () => "",
      evaluate: async (_fn: unknown, arg?: unknown) => {
        if (!arg) {
          return ""; // the run's user-agent probe
        }
        const before = top;
        top = Math.min(top + 100, 250);
        rounds.push(top);
        return {
          scrollable: true,
          before,
          after: top,
          heightBefore: 1_000,
          heightAfter: 1_000,
        };
      },
      waitForTimeout: async () => undefined,
    } as unknown as Page;
    const flow = makeFlow([
      { action: "scroll", target: ".panel", by: 100, settleMs: 0 },
    ]);

    const ctx = makeContext(scroller);
    await runFlow(flow, ctx);

    // 0→100→200→250→250: the last round does not move, so it stops there.
    expect(rounds).toEqual([100, 200, 250, 250]);
    expect(ctx.meta.usedSelectors["1.scroll"]).toBe(".panel");
  });

  it("treats a container that is not scrollable as already at the end", async () => {
    const page = {
      url: () => "",
      evaluate: async () => ({ scrollable: false, before: 0, after: 0 }),
      waitForTimeout: async () => undefined,
    } as unknown as Page;
    const flow = makeFlow([{ action: "scroll", target: ".short" }]);

    const ctx = makeContext(page);
    await runFlow(flow, ctx);

    expect(ctx.meta.usedSelectors["1.scroll"]).toBe(".short");
    expect(ctx.meta.steps[0].ok).toBe(true);
  });

  it("keeps scrolling while the content still grows", async () => {
    const heights = [1_000, 1_200, 1_200];
    let round = 0;
    const lazy = {
      url: () => "",
      evaluate: async (_fn: unknown, arg?: unknown) => {
        if (!arg) {
          return "";
        }
        const heightBefore = heights[round] ?? 1_200;
        round += 1;
        const heightAfter = heights[round] ?? 1_200;
        return {
          scrollable: true,
          before: round * 100,
          after: (round + 1) * 100,
          heightBefore,
          heightAfter,
        };
      },
      waitForTimeout: async () => undefined,
    } as unknown as Page;
    const flow = makeFlow([
      { action: "scroll", target: ".list", until: "grow", settleMs: 0 },
    ]);

    await runFlow(flow, makeContext(lazy));

    // 1000→1200 grows, 1200→1200 does not: two rounds, then stop.
    expect(round).toBe(2);
  });

  it("retries a failing step before giving up", async () => {
    let attempts = 0;
    const flaky = {
      url: () => "",
      evaluate: async () => "",
      waitForTimeout: async () => undefined,
      locator: () => ({
        first: () => ({
          count: async () => 1,
          click: async () => {
            attempts += 1;
            if (attempts < 3) {
              throw new Error("not ready");
            }
          },
        }),
      }),
    } as unknown as Page;
    const flow = makeFlow([
      {
        action: "click",
        selector: "#bump",
        retry: { attempts: 3, delayMs: 0 },
      },
    ]);

    const ctx = makeContext(flaky);
    await runFlow(flow, ctx);

    expect(attempts).toBe(3);
    expect(ctx.meta.steps[0]).toMatchObject({ ok: true, retries: 2 });
  });

  it("gives up after the last retry and reports the error", async () => {
    const flow = makeFlow([
      {
        action: "click",
        selector: "#never",
        retry: { attempts: 2, delayMs: 0 },
      },
    ]);
    const page = {
      url: () => "",
      evaluate: async () => "",
      waitForTimeout: async () => undefined,
      locator: () => ({
        first: () => ({
          count: async () => 1,
          click: async () => {
            throw new Error("still not ready");
          },
        }),
      }),
    } as unknown as Page;

    const ctx = makeContext(page);
    await expect(runFlow(flow, ctx)).rejects.toMatchObject({
      code: "timeout",
    });
    expect(ctx.meta.steps[0]).toMatchObject({ ok: false, retries: 1 });
  });

  it("leaves a failure screenshot behind", async () => {
    const flow = makeFlow([{ action: "click", selector: "#missing" }]);
    const ctx = makeContext(makePage(), { artifactsDir });

    await expect(runFlow(flow, ctx)).rejects.toBeTruthy();

    expect(ctx.meta.screenshots.failure).toBe("artifacts/failure.png");
    const png = await readFile(join(artifactsDir, "failure.png"), "utf8");
    expect(png).toBe("png");
  });

  it("refuses an output that no step captured", async () => {
    const flow = makeFlow([{ action: "text", selector: "#a", as: "a" }], {
      b: "missingVar",
    });
    const page = makePage({ elements: { "#a": "x" } });
    await expect(runFlow(flow, makeContext(page))).rejects.toMatchObject({
      code: "no-output-var",
    });
  });

  it("stops before the next step once cancelled", async () => {
    const controller = new AbortController();
    controller.abort();
    const flow = makeFlow([{ action: "goto", url: "https://example.test/" }]);
    const page = makePage();

    await expect(
      runFlow(flow, makeContext(page, { signal: controller.signal })),
    ).rejects.toBeInstanceOf(FlowError);
    expect(page.goto).not.toHaveBeenCalled();
  });
});
