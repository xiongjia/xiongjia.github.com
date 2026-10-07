/**
 * Static fixtures for the component / hook tests.
 *
 * Distinct from the browser mock in `lib/ipc.ts` (`mockHostSnapshot` /
 * `mockHostHistory`): that one replaces the Rust host at runtime, these are
 * plain data handed to components under test.
 */

import type { HistoryPoint, Snapshot } from "@/lib/ipc";

export const snapshotFixture: Snapshot = {
  timestampMs: new Date(2026, 0, 1, 10, 3, 7).getTime(),
  cpuUsage: 41.6,
  cores: [
    { core: 0, usage: 12.5 },
    { core: 1, usage: 88 },
  ],
  memoryUsed: 8 * 1024 ** 3,
  memoryTotal: 16 * 1024 ** 3,
  swapUsed: 512 * 1024 ** 2,
  swapTotal: 2 * 1024 ** 3,
  disks: [
    {
      name: "Macintosh HD",
      mountPoint: "/",
      total: 100 * 1024 ** 3,
      available: 40 * 1024 ** 3,
      used: 60 * 1024 ** 3,
    },
    {
      name: "Data",
      mountPoint: "/System/Volumes/Data",
      total: 100 * 1024 ** 3,
      available: 40 * 1024 ** 3,
      used: 60 * 1024 ** 3,
    },
  ],
  topProcesses: [
    { pid: 1, name: "tauri-demo", memory: 400 * 1024 ** 2 },
    { pid: 2, name: "node", memory: 300 * 1024 ** 2 },
    { pid: 3, name: "WindowServer", memory: 200 * 1024 ** 2 },
  ],
  uptimeSecs: 2 * 86400 + 3 * 3600 + 4 * 60,
  historyCapacity: 60,
};

export const historyFixture: HistoryPoint[] = [
  { timestampMs: snapshotFixture.timestampMs - 4_000, cpu: 20, memory: 60 },
  { timestampMs: snapshotFixture.timestampMs - 2_000, cpu: 35, memory: 61 },
  { timestampMs: snapshotFixture.timestampMs, cpu: 41.6, memory: 62 },
];
