//! System metrics collection for the Tauri demo.
//!
//! The collector keeps a long-lived `System` handle so that CPU usage is
//! computed from the delta between two refreshes, and a bounded history
//! buffer that feeds the frontend line chart.

use std::collections::VecDeque;
use std::sync::{Mutex, MutexGuard};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::Serialize;
use sysinfo::{Disks, System};
use thiserror::Error;

/// Number of history points kept for the line chart (one point per poll).
pub const HISTORY_CAPACITY: usize = 60;
/// How many processes the bar chart shows.
pub const TOP_PROCESS_COUNT: usize = 8;
/// Minimum delay between two recorded history points.
///
/// Samples closer together than this are dropped instead of appended, which
/// keeps bursts from skewing the chart: React StrictMode runs effects twice in
/// development, and several windows could poll the same state at once.
pub const MIN_SAMPLE_SPACING_MS: u64 = 500;
/// How long a disk reading is reused before the mount points are read again.
///
/// `Disks::refresh` re-stats every mount, which measured ~10 ms per call on a
/// laptop (about half of a snapshot) and can be far slower for network mounts,
/// while free space changes slowly. The frontend polls every 2 s, so a 10 s
/// cache removes ~80% of that cost.
pub const DISK_REFRESH_INTERVAL_MS: u64 = 10_000;

/// Failure modes when reading the metrics state.
#[derive(Debug, Error)]
pub enum MetricsError {
    /// A writer panicked while holding one of the internal mutexes.
    #[error("{0} lock poisoned")]
    LockPoisoned(&'static str),
}

/// Usage of a single logical CPU core.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CpuCore {
    pub core: usize,
    pub usage: f32,
}

/// Space usage of one mounted volume.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiskUsage {
    /// Volume label as reported by the OS (empty for anonymous mounts).
    pub name: String,
    pub mount_point: String,
    pub total: u64,
    pub available: u64,
    pub used: u64,
}

/// Resident memory of a single process.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessUsage {
    pub pid: u32,
    pub name: String,
    pub memory: u64,
}

/// A single point in time, returned to the frontend on every poll.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot {
    pub timestamp_ms: u64,
    pub cpu_usage: f32,
    pub cores: Vec<CpuCore>,
    pub memory_used: u64,
    pub memory_total: u64,
    pub swap_used: u64,
    pub swap_total: u64,
    pub disks: Vec<DiskUsage>,
    pub top_processes: Vec<ProcessUsage>,
    pub uptime_secs: u64,
    /// How many points the frontend should expect the history to hold.
    pub history_capacity: usize,
}

/// One point of the CPU / memory line chart.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HistoryPoint {
    pub timestamp_ms: u64,
    pub cpu: f32,
    pub memory: f32,
}

/// Percentage of `used` out of `total`, guarding against division by zero.
pub fn percent(used: u64, total: u64) -> f32 {
    if total == 0 {
        0.0
    } else {
        (used as f64 / total as f64 * 100.0) as f32
    }
}

/// Appends a point, dropping the oldest ones once the buffer is full.
///
/// A `capacity` of zero keeps the buffer empty instead of looping forever.
pub fn push_history(buffer: &mut VecDeque<HistoryPoint>, point: HistoryPoint, capacity: usize) {
    if capacity == 0 {
        buffer.clear();
        return;
    }
    while buffer.len() >= capacity {
        buffer.pop_front();
    }
    buffer.push_back(point);
}

/// Whether the cached disk reading is old enough to be refreshed.
///
/// A reading timestamped in the future (clock jump) counts as stale, so the
/// cache is rebuilt instead of being served forever.
pub fn should_refresh_disks(refreshed_at: Option<Instant>, now: Instant) -> bool {
    match refreshed_at {
        None => true,
        Some(last) => now
            .checked_duration_since(last)
            .is_none_or(|age| age >= Duration::from_millis(DISK_REFRESH_INTERVAL_MS)),
    }
}

/// Reads the current usage of every mount point.
fn read_disks(disks: &Disks) -> Vec<DiskUsage> {
    disks
        .list()
        .iter()
        .map(|disk| {
            let total = disk.total_space();
            let available = disk.available_space();
            DiskUsage {
                name: disk.name().to_string_lossy().into_owned(),
                mount_point: disk.mount_point().to_string_lossy().into_owned(),
                total,
                available,
                used: total.saturating_sub(available),
            }
        })
        .collect()
}

/// Cache for the disk reading, refreshed at most every `DISK_REFRESH_INTERVAL_MS`.
struct DiskCache {
    disks: Disks,
    cached_usage: Vec<DiskUsage>,
    refreshed_at: Option<Instant>,
}

impl DiskCache {
    fn new() -> Self {
        let disks = Disks::new_with_refreshed_list();
        Self {
            cached_usage: read_disks(&disks),
            disks,
            refreshed_at: Some(Instant::now()),
        }
    }

    /// Returns the reading, re-reading every mount first when it went stale.
    ///
    /// Taking `&mut self` is deliberate: the call may re-stat the mounts, so it
    /// must not be mistaken for a plain accessor.
    fn usage(&mut self) -> &[DiskUsage] {
        let now = Instant::now();
        if should_refresh_disks(self.refreshed_at, now) {
            self.disks.refresh(true);
            self.cached_usage = read_disks(&self.disks);
            self.refreshed_at = Some(now);
        }
        &self.cached_usage
    }
}

/// Whether a sample at `timestamp_ms` is far enough from the last recorded one.
pub fn should_record(buffer: &VecDeque<HistoryPoint>, timestamp_ms: u64) -> bool {
    buffer
        .back()
        .is_none_or(|last| timestamp_ms.saturating_sub(last.timestamp_ms) >= MIN_SAMPLE_SPACING_MS)
}

/// Keeps the `limit` biggest processes, ordered by memory usage (descending).
///
/// Only the biggest entries are partitioned and sorted, because this runs on
/// every poll while the process table holds hundreds of entries.
pub fn top_processes(mut processes: Vec<ProcessUsage>, limit: usize) -> Vec<ProcessUsage> {
    if limit == 0 || processes.is_empty() {
        return Vec::new();
    }
    if processes.len() > limit {
        processes.select_nth_unstable_by_key(limit, |process| std::cmp::Reverse(process.memory));
        processes.truncate(limit);
    }
    processes.sort_by_key(|process| std::cmp::Reverse(process.memory));
    processes
}

/// Wall clock in milliseconds, or `0` if the system clock is before the epoch.
fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or_default()
}

/// Locks a mutex, turning poisoning into a recoverable error.
fn lock<'a, T>(mutex: &'a Mutex<T>, name: &'static str) -> Result<MutexGuard<'a, T>, MetricsError> {
    mutex.lock().map_err(|_| MetricsError::LockPoisoned(name))
}

/// Everything read from the long-lived `System` handle in one refresh cycle.
struct SystemReading {
    cpu_usage: f32,
    cores: Vec<CpuCore>,
    processes: Vec<ProcessUsage>,
    memory_used: u64,
    memory_total: u64,
    swap_used: u64,
    swap_total: u64,
}

/// Long-lived collector stored in the Tauri app state.
pub struct MetricsState {
    system: Mutex<System>,
    disks: Mutex<DiskCache>,
    history: Mutex<VecDeque<HistoryPoint>>,
}

impl MetricsState {
    /// Builds the collector and takes a first CPU reading as a baseline.
    pub fn new() -> Self {
        let mut system = System::new_all();
        // CPU usage is the delta between two refreshes, so the first snapshot
        // after this call can still read 0%.
        system.refresh_cpu_usage();
        Self {
            system: Mutex::new(system),
            disks: Mutex::new(DiskCache::new()),
            history: Mutex::new(VecDeque::with_capacity(HISTORY_CAPACITY)),
        }
    }

    /// Samples the machine and records the point in the history buffer.
    pub fn snapshot(&self) -> Result<Snapshot, MetricsError> {
        let timestamp_ms = now_ms();

        // The three locks are taken one after another (never nested for longer
        // than needed) so a slow disk refresh cannot block a concurrent
        // history read.
        let reading = {
            let mut system = lock(&self.system, "system")?;
            system.refresh_cpu_usage();
            system.refresh_memory();
            system.refresh_processes(sysinfo::ProcessesToUpdate::All, true);

            let cores = system
                .cpus()
                .iter()
                .enumerate()
                .map(|(index, cpu)| CpuCore {
                    core: index,
                    usage: cpu.cpu_usage(),
                })
                .collect();

            let processes = system
                .processes()
                .iter()
                .map(|(pid, process)| ProcessUsage {
                    pid: pid.as_u32(),
                    name: process.name().to_string_lossy().into_owned(),
                    memory: process.memory(),
                })
                .collect();

            SystemReading {
                cpu_usage: system.global_cpu_usage(),
                cores,
                processes,
                memory_used: system.used_memory(),
                memory_total: system.total_memory(),
                swap_used: system.used_swap(),
                swap_total: system.total_swap(),
            }
        };

        let disk_usage: Vec<DiskUsage> = {
            let mut cache = lock(&self.disks, "disks")?;
            // A `Snapshot` owns its data, so each entry is copied once here —
            // the same strings `sysinfo` would have allocated when reading the
            // mounts directly.
            cache.usage().to_vec()
        };

        let snapshot = Snapshot {
            timestamp_ms,
            cpu_usage: reading.cpu_usage,
            cores: reading.cores,
            memory_used: reading.memory_used,
            memory_total: reading.memory_total,
            swap_used: reading.swap_used,
            swap_total: reading.swap_total,
            disks: disk_usage,
            top_processes: top_processes(reading.processes, TOP_PROCESS_COUNT),
            uptime_secs: System::uptime(),
            history_capacity: HISTORY_CAPACITY,
        };

        let point = HistoryPoint {
            timestamp_ms,
            cpu: snapshot.cpu_usage,
            memory: percent(snapshot.memory_used, snapshot.memory_total),
        };
        let mut history = lock(&self.history, "history")?;
        if should_record(&history, timestamp_ms) {
            push_history(&mut history, point, HISTORY_CAPACITY);
        }

        Ok(snapshot)
    }

    /// Returns a copy of the recorded history, oldest first.
    pub fn history(&self) -> Result<Vec<HistoryPoint>, MetricsError> {
        let history = lock(&self.history, "history")?;
        Ok(history.iter().cloned().collect())
    }
}

impl Default for MetricsState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn point(timestamp_ms: u64, cpu: f32, memory: f32) -> HistoryPoint {
        HistoryPoint {
            timestamp_ms,
            cpu,
            memory,
        }
    }

    #[test]
    fn percent_handles_zero_total() {
        assert_eq!(percent(0, 0), 0.0);
        assert_eq!(percent(50, 100), 50.0);
    }

    #[test]
    fn push_history_drops_oldest_when_full() {
        let mut buffer = VecDeque::new();
        for value in 0..5 {
            push_history(&mut buffer, point(value, value as f32, 0.0), 3);
        }
        let cpus: Vec<f32> = buffer.iter().map(|p| p.cpu).collect();
        assert_eq!(cpus, vec![2.0, 3.0, 4.0]);
    }

    #[test]
    fn push_history_with_zero_capacity_keeps_nothing() {
        let mut buffer = VecDeque::from([point(0, 1.0, 0.0)]);
        push_history(&mut buffer, point(1, 2.0, 0.0), 0);

        assert!(buffer.is_empty());
    }

    #[test]
    fn should_record_requires_minimum_spacing() {
        let empty = VecDeque::new();
        assert!(should_record(&empty, 1_000));

        let buffer = VecDeque::from([point(1_000, 1.0, 1.0)]);
        assert!(!should_record(&buffer, 1_000 + MIN_SAMPLE_SPACING_MS - 1));
        assert!(should_record(&buffer, 1_000 + MIN_SAMPLE_SPACING_MS));
        // A clock that jumps backwards must not wedge the buffer.
        assert!(!should_record(&buffer, 500));
    }

    #[test]
    fn should_refresh_disks_honours_the_ttl() {
        let now = Instant::now();
        assert!(should_refresh_disks(None, now));
        assert!(!should_refresh_disks(
            Some(now - Duration::from_millis(DISK_REFRESH_INTERVAL_MS - 1)),
            now
        ));
        assert!(should_refresh_disks(
            Some(now - Duration::from_millis(DISK_REFRESH_INTERVAL_MS)),
            now
        ));
        // A clock that jumps backwards must not wedge the cache.
        assert!(should_refresh_disks(
            Some(now + Duration::from_secs(5)),
            now
        ));
    }

    #[test]
    fn disk_cache_serves_repeated_reads_without_refreshing() {
        let mut cache = DiskCache::new();
        let refreshed_at = cache.refreshed_at;
        let first = cache.usage().len();

        let second = cache.usage().len();

        assert_eq!(second, first);
        assert_eq!(
            cache.refreshed_at, refreshed_at,
            "second read must stay cached"
        );
    }

    #[test]
    fn snapshots_reuse_the_cached_disk_reading() {
        let state = MetricsState::new();
        let _ = state.snapshot().expect("first snapshot");
        let first = state.disks.lock().expect("disks lock").refreshed_at;

        let _ = state.snapshot().expect("second snapshot");
        let second = state.disks.lock().expect("disks lock").refreshed_at;

        assert_eq!(
            first, second,
            "the second snapshot must not re-stat the mounts"
        );

        // The other direction: a cache that expired must be refreshed by the
        // next snapshot (this also proves `snapshot` really goes through it).
        state.disks.lock().expect("disks lock").refreshed_at = None;
        let _ = state.snapshot().expect("third snapshot");
        assert!(
            state
                .disks
                .lock()
                .expect("disks lock")
                .refreshed_at
                .is_some(),
            "a stale cache must be refreshed by the next snapshot"
        );
    }

    #[test]
    fn top_processes_sorts_by_memory_and_truncates() {
        let make = |pid, memory| ProcessUsage {
            pid,
            name: format!("p{pid}"),
            memory,
        };
        let result = top_processes(vec![make(1, 10), make(2, 50), make(3, 30)], 2);
        assert_eq!(result.iter().map(|p| p.pid).collect::<Vec<_>>(), vec![2, 3]);

        assert!(top_processes(vec![make(1, 10)], 0).is_empty());
        assert!(top_processes(Vec::new(), 4).is_empty());
    }

    #[test]
    fn snapshot_reports_the_local_machine() {
        let state = MetricsState::new();
        let first = state.snapshot().expect("first snapshot");
        assert!(!first.cores.is_empty(), "expected at least one CPU core");
        assert!(first.memory_total > 0, "expected a non-zero memory total");
        assert!(first.cpu_usage >= 0.0);
        assert!(first.top_processes.len() <= TOP_PROCESS_COUNT);
        assert_eq!(state.history().expect("history").len(), 1);

        // Two samples taken within the minimum spacing collapse into one point.
        let second = state.snapshot().expect("second snapshot");
        assert!(second.timestamp_ms >= first.timestamp_ms);
        assert_eq!(state.history().expect("history").len(), 1);
    }

    #[test]
    fn history_is_bounded_by_the_capacity() {
        let state = MetricsState::new();
        {
            let mut history = state.history.lock().expect("history lock");
            for index in 0..HISTORY_CAPACITY * 2 {
                let timestamp = index as u64 * MIN_SAMPLE_SPACING_MS;
                push_history(&mut history, point(timestamp, 1.0, 1.0), HISTORY_CAPACITY);
            }
        }

        let history = state.history().expect("history");
        assert_eq!(history.len(), HISTORY_CAPACITY);
        // The first `HISTORY_CAPACITY` points (index 0..60) got dropped.
        assert_eq!(
            history[0].timestamp_ms,
            HISTORY_CAPACITY as u64 * MIN_SAMPLE_SPACING_MS
        );
    }
}
