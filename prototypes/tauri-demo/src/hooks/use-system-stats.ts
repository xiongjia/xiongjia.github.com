import { useEffect, useState } from "react";

import { fetchHistory, fetchSnapshot, type HistoryPoint, type Snapshot } from "@/lib/ipc";

const POLL_INTERVAL_MS = 2_000;
/** Floor for the poll interval, so a caller cannot busy-poll the IPC bridge. */
const MIN_POLL_INTERVAL_MS = 250;
/** A request that never settles must not wedge polling forever. */
const DEFAULT_REQUEST_TIMEOUT_MS = 10_000;

interface SystemStats {
  snapshot: Snapshot | null;
  history: HistoryPoint[];
  error: string | null;
}

/**
 * Polls the Rust side every couple of seconds. CPU usage in `sysinfo` is the
 * delta between two refreshes, so a 2s interval gives stable readings.
 *
 * Each poll appends a point to the Rust history buffer, so ticks that fire
 * while a request is still running are skipped instead of queued. A request
 * that does not answer within the request timeout is abandoned (its late result
 * is ignored) so a wedged IPC channel cannot freeze the dashboard. The timeout
 * is derived from `intervalMs`, always staying above one interval so a long
 * poll period cannot time out by construction.
 *
 * The Rust side additionally drops samples arriving within
 * `MIN_SAMPLE_SPACING_MS` of the previous one (React StrictMode runs effects
 * twice in development, and several windows can poll the same state).
 */
export function useSystemStats(intervalMs: number = POLL_INTERVAL_MS): SystemStats {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const pollIntervalMs = Number.isFinite(intervalMs)
      ? Math.max(intervalMs, MIN_POLL_INTERVAL_MS)
      : POLL_INTERVAL_MS;
    const requestTimeoutMs = Math.max(DEFAULT_REQUEST_TIMEOUT_MS, pollIntervalMs * 2);
    let cancelled = false;
    // Guards are per effect run: StrictMode's second mount must still poll.
    let inFlight = false;
    let generation = 0;
    const pendingTimeouts = new Set<number>();

    async function tick() {
      if (inFlight || cancelled) {
        return;
      }
      inFlight = true;
      const current = ++generation;
      const timeout = window.setTimeout(() => {
        pendingTimeouts.delete(timeout);
        if (current !== generation) {
          return;
        }
        // Abandon the hung attempt: invalidate it and let the next tick retry.
        generation += 1;
        inFlight = false;
        if (!cancelled) {
          setError(`No response from the metrics backend after ${requestTimeoutMs / 1000}s`);
        }
      }, requestTimeoutMs);
      pendingTimeouts.add(timeout);

      try {
        const nextSnapshot = await fetchSnapshot();
        const nextHistory = await fetchHistory();
        if (cancelled || current !== generation) {
          return;
        }
        setSnapshot(nextSnapshot);
        setHistory(nextHistory);
        setError(null);
      } catch (cause) {
        if (!cancelled && current === generation) {
          setError(cause instanceof Error ? cause.message : String(cause));
        }
      } finally {
        window.clearTimeout(timeout);
        pendingTimeouts.delete(timeout);
        if (current === generation) {
          inFlight = false;
        }
      }
    }

    void tick();
    const timer = window.setInterval(() => void tick(), pollIntervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      for (const id of pendingTimeouts) {
        window.clearTimeout(id);
      }
      pendingTimeouts.clear();
    };
  }, [intervalMs]);

  return { snapshot, history, error };
}
