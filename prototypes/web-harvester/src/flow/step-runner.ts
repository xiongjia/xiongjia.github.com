import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import type { Locator, Page } from "playwright-core";
import { FlowError } from "./errors";
import type { FlowFile, FlowStep, SelectorSpec } from "./schema";
import { interpolate, type TemplateScope } from "./template";

/** One executed step, in order: this is the "scenario log" of a run. */
export interface StepTrace {
  /** `<step>.<action>`, the same key `usedSelectors` uses (e.g. `3.click`). */
  step: string;
  action: FlowStep["action"];
  /** The step's own sentence, when it has one. */
  desc?: string;
  /** For `include` steps: the flow file that ran. */
  fragment?: string;
  ok: boolean;
  /** Wall-clock duration, so "did we actually wait" is answerable. */
  ms: number;
  /** Number of retries performed before the step passed (or gave up). */
  retries?: number;
  /** True when a `when` guard skipped the step. */
  skipped?: boolean;
  error?: { code: string; message: string };
}

/** What the run learned about the page, independent of the flow's own output. */
export interface RunMeta {
  /** Every step that was reached, in order, with its outcome. */
  steps: StepTrace[];
  url: string;
  userAgent: string;
  /** Resolved selector per step, keyed `<step>.<action>` (e.g. `3.click`). */
  usedSelectors: Record<string, string>;
  /** Screenshots written under the run's `artifacts/` directory. */
  screenshots: Record<string, string>;
  /** Time spent waiting on the flow's `throttle` before the run started. */
  throttleMs?: number;
}

export interface RunContext extends TemplateScope {
  page: Page;
  meta: RunMeta;
  /** Absolute `artifacts/` directory; `null` runs without writing files. */
  artifactsDir: string | null;
  signal?: AbortSignal;
  /** Resolve a flow by name — what `use` steps call. Absent = no composition. */
  resolve?: (name: string) => Promise<FlowFile>;
  /** Internal: fragments on the stack, for cycle detection. */
  fragments?: string[];
}

const DEFAULT_TIMEOUT = 5_000;
/** `include` may nest, but not forever: 5 levels is well past useful composition. */
const MAX_FRAGMENT_DEPTH = 5;
const WAIT_STATE = { state: "visible" as const };

/** Execute a whole flow: steps first, then the `output` mapping. */
export async function runFlow(
  flow: FlowFile,
  ctx: RunContext,
): Promise<{ output: Record<string, unknown>; meta: RunMeta }> {
  try {
    await runSteps(flow.steps, ctx);

    const output: Record<string, unknown> = {};
    for (const [key, varName] of Object.entries(flow.output ?? {})) {
      if (!Object.hasOwn(ctx.vars, varName)) {
        throw new FlowError(
          "no-output-var",
          `output.${key} refers to "${varName}", which no step captured`,
        );
      }
      output[key] = ctx.vars[varName];
    }
    return { output, meta: ctx.meta };
  } catch (error) {
    // The page is still open here: a failed run should leave a picture behind.
    if (ctx.artifactsDir !== null) {
      await mkdir(ctx.artifactsDir, { recursive: true }).catch(() => undefined);
      await ctx.page
        .screenshot({
          path: join(ctx.artifactsDir, "failure.png"),
          fullPage: true,
        })
        .then(() => {
          ctx.meta.screenshots.failure = "artifacts/failure.png";
        })
        .catch(() => undefined);
    }
    throw error;
  } finally {
    // Also on failure: a failed run should still say which page it died on.
    // Guarded — a page the site closed itself must not mask the real error.
    ctx.meta.url = pageUrl(ctx.page);
    ctx.meta.userAgent = await ctx.page
      .evaluate(() => navigator.userAgent)
      .catch(() => "");
  }
}

/** Run steps in order; `prefix` keeps nested (`if`) selector keys unique. */
async function runSteps(
  steps: FlowStep[],
  ctx: RunContext,
  prefix = "",
): Promise<void> {
  for (const [index, step] of steps.entries()) {
    if (ctx.signal?.aborted) {
      throw new FlowError("cancelled", "run cancelled before the next step");
    }
    const key = `${prefix}${index + 1}.`;
    const trace: StepTrace = {
      step: `${key}${step.action}`,
      action: step.action,
      ok: false,
      ms: 0,
    };
    if (step.desc) {
      trace.desc = step.desc;
    }
    if (step.action === "include") {
      trace.fragment = step.flow;
    }
    ctx.meta.steps.push(trace);
    const guard = step.when === undefined ? null : guardOf(step.when, ctx);
    if (guard === false) {
      trace.skipped = true;
      trace.ok = true;
      continue;
    }

    const startedAt = Date.now();
    const attempts = step.retry?.attempts ?? 1;
    const delayMs = step.retry?.delayMs ?? 0;
    try {
      for (let attempt = 1; ; attempt += 1) {
        try {
          await runStep(step, ctx, key);
          trace.ok = true;
          break;
        } catch (error) {
          if (attempt >= attempts) {
            trace.error = {
              code: error instanceof FlowError ? error.code : "error",
              message: message(error),
            };
            throw error;
          }
          trace.retries = attempt;
          await ctx.page.waitForTimeout(delayMs).catch(() => undefined);
        }
      }
    } finally {
      trace.ms = Date.now() - startedAt;
    }
  }
}

async function runStep(
  step: FlowStep,
  ctx: RunContext,
  key: string,
): Promise<void> {
  const { page } = ctx;

  switch (step.action) {
    case "goto": {
      // A relative href read from the page (`/user/profile/x`) resolves against
      // the current URL instead of failing as "Invalid url".
      const raw = interpolate(step.url, ctx);
      const url = resolveUrl(raw, page);
      await page.goto(url, { waitUntil: "domcontentloaded" });
      return;
    }

    case "wait": {
      if (step.selector === undefined) {
        await page.waitForTimeout(step.ms ?? 0);
        return;
      }
      const used = await waitForAny(page, step.selector, ctx, {
        state: step.state ?? WAIT_STATE.state,
        timeout: step.timeout ?? DEFAULT_TIMEOUT,
      });
      ctx.meta.usedSelectors[`${key}wait`] = used;
      return;
    }

    case "click": {
      const hit = await actionTarget(page, step.selector, ctx, step.optional);
      if (!hit) {
        return;
      }
      ctx.meta.usedSelectors[`${key}click`] = hit.used;
      await hit.locator
        .click({ timeout: step.timeout ?? DEFAULT_TIMEOUT })
        .catch((error: unknown) => {
          throw new FlowError(
            "timeout",
            `click on ${hit.used} failed: ${message(error)}`,
          );
        });
      return;
    }

    case "fill": {
      const hit = await actionTarget(page, step.selector, ctx);
      if (!hit) {
        throw new FlowError("selector-not-found", "fill target disappeared");
      }
      ctx.meta.usedSelectors[`${key}fill`] = hit.used;
      await hit.locator
        .fill(interpolate(step.value, ctx), {
          timeout: step.timeout ?? DEFAULT_TIMEOUT,
        })
        .catch((error: unknown) => {
          throw new FlowError(
            "timeout",
            `fill on ${hit.used} failed: ${message(error)}`,
          );
        });
      return;
    }

    case "press": {
      if (step.selector === undefined) {
        await page.keyboard.press(step.key);
        return;
      }
      const hit = await firstMatch(page, step.selector, ctx);
      if (!hit) {
        throw new FlowError("selector-not-found", "press target disappeared");
      }
      ctx.meta.usedSelectors[`${key}press`] = hit.used;
      await hit.locator.press(step.key);
      return;
    }

    case "text": {
      const hit = await firstMatch(page, step.selector, ctx, step.optional);
      if (!hit) {
        ctx.vars[step.as] = "";
        return;
      }
      ctx.meta.usedSelectors[`${key}text`] = hit.used;
      ctx.vars[step.as] = ((await hit.locator.textContent()) ?? "").trim();
      return;
    }

    case "extract": {
      const items = candidates(step.item, ctx);
      const fields: Record<
        string,
        { selectors: string[]; attr: string | null }
      > = {};
      for (const [field, spec] of Object.entries(step.fields)) {
        fields[field] =
          typeof spec === "string" || Array.isArray(spec)
            ? { selectors: candidates(spec, ctx), attr: null }
            : { selectors: candidates(spec.selector, ctx), attr: spec.attr };
      }
      ctx.meta.usedSelectors[`${key}extract`] = items[0] ?? "";
      const rows = await page.evaluate(
        ({ itemSelectors, fieldSelectors, limit }) => {
          const pick = (root: ParentNode, list: string[]): Element[] => {
            for (const selector of list) {
              // ":scope" is the row itself — Firefox answers null for
              // `element.querySelector(":scope")`, so it is handled here.
              if (selector === ":scope" && root instanceof Element) {
                return [root];
              }
              const found = [...root.querySelectorAll(selector)];
              if (found.length > 0) {
                return found;
              }
            }
            return [];
          };
          return pick(document, itemSelectors)
            .slice(0, limit)
            .map((row) => {
              const out: Record<string, string | null> = {};
              for (const [field, spec] of Object.entries(fieldSelectors)) {
                const element = pick(row, spec.selectors)[0] ?? null;
                if (!element) {
                  out[field] = null;
                } else if (spec.attr) {
                  out[field] = element.getAttribute(spec.attr)?.trim() ?? null;
                } else {
                  out[field] = (element.textContent ?? "").trim();
                }
              }
              return out;
            });
        },
        {
          itemSelectors: items,
          fieldSelectors: fields,
          limit: step.limit ?? 200,
        },
      );
      ctx.vars[step.as] = step.uniqueBy
        ? uniqueRows(rows, step.uniqueBy)
        : rows;
      return;
    }

    case "screenshot": {
      if (ctx.artifactsDir === null) {
        throw new FlowError(
          "assert-failed",
          "this run has no artifacts directory",
        );
      }
      const name = step.name ?? "screenshot";
      const file = `${name}.png`;
      await mkdir(ctx.artifactsDir, { recursive: true });
      const path = join(ctx.artifactsDir, file);
      if (step.selector === undefined) {
        await page.screenshot({ path, fullPage: step.fullPage ?? true });
      } else {
        const hit = await firstMatch(page, step.selector, ctx);
        if (!hit) {
          throw new FlowError(
            "selector-not-found",
            "screenshot target vanished",
          );
        }
        ctx.meta.usedSelectors[`${key}screenshot`] = hit.used;
        await hit.locator.screenshot({ path });
      }
      ctx.meta.screenshots[name] = `artifacts/${file}`;
      return;
    }

    case "scroll": {
      await scrollContainer(page, step, ctx, key);
      return;
    }

    case "attribute": {
      const hit = await firstMatch(page, step.selector, ctx, step.optional);
      if (!hit) {
        ctx.vars[step.as] = "";
        return;
      }
      ctx.meta.usedSelectors[`${key}attribute`] = hit.used;
      ctx.vars[step.as] =
        (await hit.locator.getAttribute(step.name))?.trim() ?? "";
      return;
    }

    case "assertNotBlocked": {
      const body = await page.evaluate(() => document.body?.innerText ?? "");
      for (const pattern of step.patterns) {
        if (matches(body, pattern)) {
          throw new FlowError(
            "blocked",
            `page matched blocked pattern "${pattern}" — the site answered with a risk-control page`,
          );
        }
      }
      return;
    }

    case "include": {
      await runFragment(step.flow, ctx, key);
      return;
    }

    case "if": {
      const hit = await findAny(page, step.selector, ctx, step.state);
      const branch = hit ? step.then : step.else;
      if (branch) {
        await runSteps(branch, ctx, key);
      }
      return;
    }

    default: {
      const unreachable: never = step;
      throw new Error(`unhandled flow step: ${JSON.stringify(unreachable)}`);
    }
  }
}

/**
 * Splice another flow file's steps in at this point.
 *
 * The fragment shares the page, the captured `vars` and the caller's `input`, so
 * it reads `{{input.x}}` like the including flow does. That is what makes a long
 * flow splittable: `include` is a call, not a copy.
 */
async function runFragment(
  name: string,
  ctx: RunContext,
  key: string,
): Promise<void> {
  if (!ctx.resolve) {
    throw new FlowError(
      "bad-fragment",
      `cannot run "${name}": this run has no flow resolver`,
    );
  }
  const stack = (ctx.fragments ??= []);
  if (stack.includes(name)) {
    throw new FlowError(
      "bad-fragment",
      `fragment cycle: ${[...stack, name].join(" → ")}`,
    );
  }
  if (stack.length >= MAX_FRAGMENT_DEPTH) {
    throw new FlowError(
      "bad-fragment",
      `fragments nested deeper than ${MAX_FRAGMENT_DEPTH} (${stack.join(" → ")})`,
    );
  }

  const fragment = await ctx.resolve(name).catch((error: unknown) => {
    throw new FlowError("bad-fragment", message(error));
  });
  if (fragment.kind !== "fragment") {
    throw new FlowError(
      "bad-fragment",
      `"${name}" is a flow, not a fragment — add "kind": "fragment" to it, or include a fragment instead`,
    );
  }

  stack.push(name);
  try {
    await runSteps(fragment.steps, ctx, key);
  } finally {
    stack.pop();
  }
}

/**
 * Scroll a container until it stops moving or stops growing.
 *
 * The container's own `scrollTop` is moved, never the window: chat panels and
 * relation lists scroll inside a `div`. `end` is the default stop condition;
 * `grow` keeps going while the content is still being appended (lazy lists).
 */
async function scrollContainer(
  page: Page,
  step: Extract<FlowStep, { action: "scroll" }>,
  ctx: RunContext,
  key: string,
): Promise<void> {
  const list = candidates(step.target, ctx);
  const by = step.by ?? 1_000;
  const settleMs = step.settleMs ?? 400;
  const maxRounds = step.maxRounds ?? 50;
  const until = step.until ?? "end";

  for (let round = 1; round <= maxRounds; round += 1) {
    const probe = await page.evaluate(
      ({ selectors, pixels }) => {
        const isScrollable = (element: Element): boolean => {
          const node = element as HTMLElement;
          return node.scrollHeight > node.clientHeight + 20;
        };
        let scroller: HTMLElement | null = null;
        let found = false;
        for (const selector of selectors) {
          const candidate = document.querySelector(selector);
          if (!candidate) {
            continue;
          }
          found = true;
          if (isScrollable(candidate)) {
            scroller = candidate as HTMLElement;
            break;
          }
        }
        if (!found) {
          return null;
        }
        if (!scroller) {
          // Present but short: there is nothing to scroll, so this is a no-op
          // rather than "selector not found".
          return { scrollable: false, before: 0, after: 0 };
        }
        const before = scroller.scrollTop;
        scroller.scrollBy(0, pixels);
        return {
          scrollable: true,
          before,
          after: scroller.scrollTop,
          heightBefore: scroller.scrollHeight,
          heightAfter: scroller.scrollHeight,
        };
      },
      { selectors: list, pixels: by },
    );

    if (!probe) {
      throw new FlowError(
        "selector-not-found",
        `none of ${JSON.stringify(list)} matched`,
      );
    }
    ctx.meta.usedSelectors[`${key}scroll`] = list[0];

    if (!probe.scrollable) {
      return;
    }

    const done =
      until === "end"
        ? probe.after === probe.before
        : probe.heightAfter === probe.heightBefore;
    if (done) {
      return;
    }
    if (settleMs > 0) {
      await page.waitForTimeout(settleMs);
    }
  }
}

/** Interpolate every candidate — templates are legal inside selectors too. */
function candidates(selector: SelectorSpec, scope: TemplateScope): string[] {
  const list = Array.isArray(selector) ? selector : [selector];
  return list.map((candidate) => interpolate(candidate, scope));
}

/** First candidate that matches at least once; throws when none does. */
/**
 * Target for `click` / `fill`.
 *
 * One selector goes straight to Playwright, which waits for the element to
 * appear and become actionable — that is the behaviour people expect from a
 * click. With several candidates the pick is by existence (a fallback list, not
 * a wait list); use `wait` first when the element shows up late.
 */
async function actionTarget(
  page: Page,
  selector: SelectorSpec,
  ctx: RunContext,
  optional?: boolean,
): Promise<{ locator: Locator; used: string } | null> {
  const list = candidates(selector, ctx);
  if (list.length === 1) {
    return { locator: page.locator(list[0]).first(), used: list[0] };
  }
  return firstMatch(page, selector, ctx, optional);
}

/** First candidate that matches at least once; throws when none does. */
async function firstMatch(
  page: Page,
  selector: SelectorSpec,
  ctx: RunContext,
  optional?: boolean,
): Promise<{ locator: Locator; used: string } | null> {
  for (const candidate of candidates(selector, ctx)) {
    const locator = page.locator(candidate).first();
    if ((await safeCount(locator)) > 0) {
      return { locator, used: candidate };
    }
  }
  if (optional) {
    return null;
  }
  throw new FlowError(
    "selector-not-found",
    `none of ${JSON.stringify(candidates(selector, ctx))} matched`,
  );
}

async function findAny(
  page: Page,
  selector: SelectorSpec,
  ctx: RunContext,
  state: "visible" | "attached" = "visible",
): Promise<boolean> {
  for (const candidate of candidates(selector, ctx)) {
    const locator = page.locator(candidate).first();
    if (state === "visible") {
      // Default on purpose: "wait until it is on screen" is the common intent,
      // and an attached-but-hidden element is usually not what a branch means.
      if (await locator.isVisible().catch(() => false)) {
        return true;
      }
    } else if ((await safeCount(locator)) > 0) {
      return true;
    }
  }
  return false;
}

/**
 * Wait until one of the candidates reaches `state`.
 *
 * Deliberately does not pre-check `count()`: an element that does not exist yet
 * is exactly what `wait` is for, and Playwright's `waitFor` waits for it to
 * appear as well as for it to become visible. Several candidates are combined
 * with `locator.or(...)`, so any of them satisfies the wait.
 */
async function waitForAny(
  page: Page,
  selector: SelectorSpec,
  ctx: RunContext,
  options: { state: "visible" | "attached"; timeout: number },
): Promise<string> {
  const list = candidates(selector, ctx);
  const fail =
    (label: string) =>
    (error: unknown): never => {
      throw new FlowError(
        "timeout",
        `${label} did not become ${options.state} within ${options.timeout}ms: ${message(error)}`,
      );
    };

  if (list.length === 1) {
    await page
      .locator(list[0])
      .first()
      .waitFor({ state: options.state, timeout: options.timeout })
      .catch(fail(list[0]));
    return list[0];
  }

  const combined = list
    .map((candidate) => page.locator(candidate))
    .reduce((left, right) => left.or(right));
  await combined
    .first()
    .waitFor({ state: options.state, timeout: options.timeout })
    .catch(fail(JSON.stringify(list)));

  // Attribute the hit so `usedSelectors` still says which candidate won.
  for (const candidate of list) {
    if ((await safeCount(page.locator(candidate).first())) > 0) {
      return candidate;
    }
  }
  return list[0];
}

async function safeCount(locator: Locator): Promise<number> {
  return locator.count().catch(() => 0);
}

/** Patterns are regexes, but a literal string still has to work. */
function matches(text: string, pattern: string): boolean {
  try {
    return new RegExp(pattern).test(text);
  } catch {
    return text.includes(pattern);
  }
}

/** `{{input.key}}` / `{{vars.key}}` / the same with a leading `!`. */
const SIMPLE_GUARD = /^!?\{\{\s*(input|vars)\.([A-Za-z0-9._-]+)\s*\}\}$/;

/** `when` truthiness, with a leading `!` for "only when absent". */
function guardOf(template: string, ctx: RunContext): boolean {
  // An optional input the caller never sent is simply false — a guard must not
  // turn "not provided" into a `bad-template` error.
  const simple = SIMPLE_GUARD.exec(template);
  if (simple) {
    const bag = simple[1] === "input" ? ctx.input : ctx.vars;
    if (!Object.hasOwn(bag, simple[2])) {
      return template.startsWith("!");
    }
  }

  const value = interpolate(template, ctx);
  const negated = value.startsWith("!");
  const body = (negated ? value.slice(1) : value).trim();
  const truthy =
    body !== "" && body !== "false" && body !== "0" && body !== "null";
  return negated ? !truthy : truthy;
}

/** Keep the first row per value combination, e.g. one row per nickname. */
function uniqueRows(
  rows: Array<Record<string, string | null>>,
  fields: string[],
): Array<Record<string, string | null>> {
  const seen = new Set<string>();
  return rows.filter((row) => {
    const key = JSON.stringify(fields.map((field) => row[field] ?? null));
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function resolveUrl(raw: string, page: Page): string {
  try {
    return new URL(raw, pageUrl(page) || undefined).toString();
  } catch {
    return raw;
  }
}

function pageUrl(page: Page): string {
  try {
    return page.url();
  } catch {
    return "";
  }
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
