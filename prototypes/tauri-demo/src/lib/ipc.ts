/**
 * Typed wrappers around the Rust commands, plus a mock used when the app is
 * opened in a plain browser (`pnpm dev`) so the UI can be developed and
 * DOM-checked without a Tauri window.
 */

import { invoke, isTauri } from "@tauri-apps/api/core";

export interface CpuCore {
  core: number;
  usage: number;
}

export interface DiskUsage {
  name: string;
  mountPoint: string;
  total: number;
  available: number;
  used: number;
}

export interface ProcessUsage {
  pid: number;
  name: string;
  memory: number;
}

export interface Snapshot {
  timestampMs: number;
  cpuUsage: number;
  cores: CpuCore[];
  memoryUsed: number;
  memoryTotal: number;
  swapUsed: number;
  swapTotal: number;
  disks: DiskUsage[];
  topProcesses: ProcessUsage[];
  uptimeSecs: number;
  historyCapacity: number;
}

export interface HistoryPoint {
  timestampMs: number;
  cpu: number;
  memory: number;
}

/** Returns true when running inside the Tauri webview, false in a plain browser. */
export function isDesktopApp(): boolean {
  return isTauri();
}

export async function fetchSnapshot(): Promise<Snapshot> {
  if (!isDesktopApp()) {
    return mockHostSnapshot();
  }
  return invoke<Snapshot>("system_snapshot");
}

export async function fetchHistory(): Promise<HistoryPoint[]> {
  if (!isDesktopApp()) {
    return [...mockHostHistory];
  }
  return invoke<HistoryPoint[]>("system_history");
}

// --- Browser mock ---------------------------------------------------------

/** Mirrors `HISTORY_CAPACITY` in `src-tauri/src/metrics.rs`. */
const MOCK_HISTORY_CAPACITY = 60;
const MOCK_CORES = 8;
const mockHostHistory: HistoryPoint[] = [];

const MOCK_PROCESSES: ProcessUsage[] = [
  { pid: 421, name: "tauri-demo", memory: 412 * 1024 * 1024 },
  { pid: 1180, name: "WindowServer", memory: 986 * 1024 * 1024 },
  { pid: 733, name: "node", memory: 318 * 1024 * 1024 },
  { pid: 91, name: "kernel_task", memory: 274 * 1024 * 1024 },
  { pid: 902, name: "Code Helper", memory: 655 * 1024 * 1024 },
  { pid: 1204, name: "Google Chrome", memory: 512 * 1024 * 1024 },
];

function sineWave(now: number, offset: number, amplitude: number, base: number): number {
  const phase = (now % 60_000) / 60_000;
  return Math.min(100, Math.max(0, base + amplitude * Math.sin((phase + offset) * Math.PI * 2)));
}

function mockHostSnapshot(): Snapshot {
  const now = Date.now();
  const cpu = sineWave(now, 0, 22, 34);
  const memory = sineWave(now, 0.35, 6, 62);
  const memoryTotal = 16 * 1024 * 1024 * 1024;
  const snapshot: Snapshot = {
    timestampMs: now,
    cpuUsage: cpu,
    cores: Array.from({ length: MOCK_CORES }, (_, core) => ({
      core,
      usage: sineWave(now, core / MOCK_CORES, 18, 32),
    })),
    memoryUsed: Math.round((memory / 100) * memoryTotal),
    memoryTotal,
    swapUsed: 512 * 1024 * 1024,
    swapTotal: 2 * 1024 * 1024 * 1024,
    disks: [
      {
        name: "Macintosh HD",
        mountPoint: "/",
        total: 994 * 1024 ** 3,
        available: 214 * 1024 ** 3,
        used: 780 * 1024 ** 3,
      },
      {
        name: "Data",
        mountPoint: "/System/Volumes/Data",
        total: 994 * 1024 ** 3,
        available: 214 * 1024 ** 3,
        used: 780 * 1024 ** 3,
      },
    ],
    topProcesses: MOCK_PROCESSES.map((process) => ({ ...process })),
    uptimeSecs: 3 * 86_400 + 7 * 3_600,
    historyCapacity: MOCK_HISTORY_CAPACITY,
  };

  mockHostHistory.push({ timestampMs: now, cpu, memory });
  while (mockHostHistory.length > MOCK_HISTORY_CAPACITY) {
    mockHostHistory.shift();
  }
  return snapshot;
}
