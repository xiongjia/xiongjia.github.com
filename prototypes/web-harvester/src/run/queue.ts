import { Injectable } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";

/** Thrown when a profile already has more work queued than it may hold. */
export class QueueFullError extends Error {
  constructor(
    readonly profile: string,
    readonly limit: number,
  ) {
    super(`profile "${profile}" already has ${limit} runs queued`);
    this.name = "QueueFullError";
  }
}

export interface QueueSnapshot {
  /** Run currently holding the profile, if any. */
  running: string | null;
  /** Runs waiting, oldest first. */
  queued: string[];
}

/**
 * One serial queue per profile.
 *
 * Serialisation is per profile, not global: two accounts must not use the same
 * browser context at the same time, but they can run in parallel. Depth is capped
 * so a caller cannot queue work faster than the browser drains it.
 */
@Injectable()
export class RunQueue {
  private readonly tails = new Map<string, Promise<void>>();
  private readonly waiting = new Map<string, string[]>();
  private readonly active = new Map<string, string>();

  constructor(private readonly config: ConfigService) {}

  get limit(): number {
    return this.config.get<number>("HARVEST_QUEUE_DEPTH") ?? 8;
  }

  depth(profile: string): number {
    return (
      (this.active.has(profile) ? 1 : 0) +
      (this.waiting.get(profile)?.length ?? 0)
    );
  }

  snapshot(profile: string): QueueSnapshot {
    return {
      running: this.active.get(profile) ?? null,
      queued: [...(this.waiting.get(profile) ?? [])],
    };
  }

  /** Queue `task` behind everything already queued for `profile`. */
  submit(
    profile: string,
    runId: string,
    task: () => Promise<void>,
  ): Promise<void> {
    if (this.depth(profile) >= this.limit) {
      throw new QueueFullError(profile, this.limit);
    }
    // Claim the profile immediately when nothing holds it, so a snapshot right
    // after `submit` already reports the run as active rather than queued.
    if (this.depth(profile) === 0) {
      this.active.set(profile, runId);
    } else {
      this.waiting.set(profile, [...(this.waiting.get(profile) ?? []), runId]);
    }

    const previous = this.tails.get(profile) ?? Promise.resolve();
    const run = previous.then(async () => {
      this.markStarted(profile, runId);
      try {
        await task();
      } finally {
        this.active.delete(profile);
      }
    });
    // Keep the chain alive after a failure; callers await `run` itself.
    this.tails.set(
      profile,
      run.catch(() => undefined),
    );
    return run;
  }

  /** Drop a run that was cancelled before it ever started. */
  drop(profile: string, runId: string): boolean {
    const queued = this.waiting.get(profile) ?? [];
    const index = queued.indexOf(runId);
    if (index === -1) {
      return false;
    }
    this.waiting.set(
      profile,
      queued.filter((candidate) => candidate !== runId),
    );
    return true;
  }

  private markStarted(profile: string, runId: string): void {
    this.waiting.set(
      profile,
      (this.waiting.get(profile) ?? []).filter(
        (candidate) => candidate !== runId,
      ),
    );
    this.active.set(profile, runId);
  }
}
