//! `tiny-bitcask` — a minimal Bitcask-style KV store, driven from the command
//! line.
//!
//! ```text
//! tiny-bitcask --dir ./data put user:1 alice
//! tiny-bitcask --dir ./data get user:1
//! tiny-bitcask --dir ./data stats
//! tiny-bitcask --dir ./data merge
//! ```

use std::path::PathBuf;
use std::process::ExitCode;
use std::time::{Duration, Instant};

use clap::{Parser, Subcommand};

use tiny_bitcask::async_engine::AsyncBitcask;
use tiny_bitcask::engine::{Bitcask, Options, Stats};
use tiny_bitcask::{datafile, error};

#[derive(Debug, Parser)]
#[command(
    name = "tiny-bitcask",
    version,
    about = "Minimal Bitcask store: append-only data files + in-memory keydir"
)]
struct Cli {
    /// Database directory (created on first use; held locked while the command runs).
    #[arg(long, global = true, default_value = "./data")]
    dir: PathBuf,

    /// Rotate the active data file once appending would exceed this size.
    #[arg(long, global = true, default_value_t = 64 * 1024 * 1024)]
    max_file_size: u64,

    /// fsync after every write (durable, much slower).
    #[arg(long, global = true)]
    sync: bool,

    /// Re-read and CRC-check every record on `get` (slower, catches corruption
    /// that appears while the store is open).
    #[arg(long, global = true)]
    verify_reads: bool,

    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Store a value (overwrites an existing key).
    Put { key: String, value: String },
    /// Read a key (printed as UTF-8 text).
    Get { key: String },
    /// Delete a key by appending a tombstone.
    Del { key: String },
    /// List live keys in lexicographic order.
    List,
    /// List the data files that make up the store.
    Files,
    /// Print keydir / disk statistics.
    Stats,
    /// Compact: rewrite live records only, write hint files.
    Merge,
    /// Benchmark the synchronous engine against the async wrapper (temporary dir).
    Bench {
        /// Number of puts per phase.
        #[arg(long, default_value_t = 10_000)]
        ops: usize,
        /// Concurrent tasks for the async phases.
        #[arg(long, default_value_t = 8)]
        concurrency: usize,
    },
}

#[tokio::main]
async fn main() -> ExitCode {
    let cli = Cli::parse();
    match run(cli).await {
        Ok(code) => code,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}

/// Exit code used when a key is simply absent (argument errors use clap's 2).
const EXIT_NOT_FOUND: u8 = 3;

async fn run(cli: Cli) -> error::Result<ExitCode> {
    let options = Options::default()
        .with_max_file_size(cli.max_file_size)
        .with_sync_writes(cli.sync)
        .with_verify_reads(cli.verify_reads);

    let code = match cli.command {
        Command::Put { key, value } => {
            let mut db = Bitcask::open(&cli.dir, options)?;
            db.put(key.as_bytes(), value.as_bytes())?;
            println!(
                "OK put {key:?} ({} bytes, live keys: {})",
                value.len(),
                db.len()
            );
            ExitCode::SUCCESS
        }
        Command::Get { key } => {
            let mut db = Bitcask::open(&cli.dir, options)?;
            match db.get(key.as_bytes())? {
                Some(value) => {
                    println!("{}", String::from_utf8_lossy(&value));
                    ExitCode::SUCCESS
                }
                // A missing key is not an error but a distinct exit code, so
                // shell callers can branch on it.
                None => {
                    eprintln!("not found: {key}");
                    ExitCode::from(EXIT_NOT_FOUND)
                }
            }
        }
        Command::Del { key } => {
            let mut db = Bitcask::open(&cli.dir, options)?;
            if db.delete(key.as_bytes())? {
                println!("OK deleted {key:?} (live keys: {})", db.len());
                ExitCode::SUCCESS
            } else {
                eprintln!("no such key: {key}");
                ExitCode::from(EXIT_NOT_FOUND)
            }
        }
        Command::List => {
            let db = Bitcask::open(&cli.dir, options)?;
            for key in db.keys() {
                println!("{}", String::from_utf8_lossy(&key));
            }
            ExitCode::SUCCESS
        }
        Command::Files => {
            let db = Bitcask::open(&cli.dir, options)?;
            let active = db.active_file_id();
            for (file_id, path) in datafile::list_data_files(db.dir())? {
                let size = std::fs::metadata(&path)
                    .map_err(|error| error::Error::io_path(&path, error))?
                    .len();
                let hint = datafile::hint_file_path(db.dir(), file_id);
                let role = if file_id == active {
                    "active"
                } else {
                    "immutable"
                };
                let hint = if hint.exists() { "hint" } else { "-" };
                println!(
                    "{:06}.data  {role:>9}  {:>10}  {hint:>4}",
                    file_id,
                    human_bytes(size)
                );
            }
            ExitCode::SUCCESS
        }
        Command::Stats => {
            print_stats(&Bitcask::open(&cli.dir, options)?.stats()?);
            ExitCode::SUCCESS
        }
        Command::Merge => {
            let mut db = Bitcask::open(&cli.dir, options)?;
            let merged = db.merge()?;
            println!(
                "merge: {} -> {} files, {} -> {} on disk, {} live keys",
                merged.files_before,
                merged.files_after,
                human_bytes(merged.bytes_before),
                human_bytes(merged.bytes_after),
                merged.live_keys
            );
            print_stats(&db.stats()?);
            ExitCode::SUCCESS
        }
        Command::Bench { ops, concurrency } => {
            bench(ops, concurrency).await?;
            ExitCode::SUCCESS
        }
    };
    Ok(code)
}

fn print_stats(stats: &Stats) {
    println!("files:      {}", stats.file_count);
    println!("live keys:  {}", stats.live_keys);
    println!("live bytes: {}", human_bytes(stats.live_bytes));
    println!("disk bytes: {}", human_bytes(stats.disk_bytes));
    println!(
        "stale:      {} (reclaim with `merge`)",
        human_bytes(stats.stale_bytes)
    );
}

/// Compare the synchronous engine with the async wrapper, then demo the async
/// backup path. Everything happens in a throwaway directory.
async fn bench(ops: usize, concurrency: usize) -> error::Result<()> {
    let concurrency = concurrency.max(1);
    let per_task = (ops / concurrency).max(1);
    let temp = tempfile::TempDir::new().map_err(error::Error::io)?;
    let db = AsyncBitcask::open(temp.path().join("db"), Options::default()).await?;
    let value = vec![b'x'; 64];

    let started = Instant::now();
    for index in 0..ops {
        db.put(format!("seq:{index:08}").into_bytes(), value.clone())
            .await?;
    }
    let sequential = started.elapsed();

    let started = Instant::now();
    let mut tasks = Vec::with_capacity(concurrency);
    for task in 0..concurrency {
        let db = db.clone();
        let value = value.clone();
        tasks.push(tokio::spawn(async move {
            for index in 0..per_task {
                db.put(format!("par:{task}:{index:08}").into_bytes(), value.clone())
                    .await?;
            }
            Ok::<usize, error::Error>(per_task)
        }));
    }
    let mut concurrent_puts = 0usize;
    for task in tasks {
        concurrent_puts += task
            .await
            .map_err(|error| error::Error::Task(error.to_string()))??;
    }
    let concurrent_writes = started.elapsed();

    let started = Instant::now();
    let mut reads = 0usize;
    let mut tasks = Vec::with_capacity(concurrency);
    for task in 0..concurrency {
        let db = db.clone();
        tasks.push(tokio::spawn(async move {
            let mut reads = 0usize;
            for index in 0..per_task {
                let key = format!("par:{task}:{index:08}").into_bytes();
                if db.get(key).await?.is_some() {
                    reads += 1;
                }
            }
            Ok::<usize, error::Error>(reads)
        }));
    }
    for task in tasks {
        reads += task
            .await
            .map_err(|error| error::Error::Task(error.to_string()))??;
    }
    let concurrent_reads = started.elapsed();

    println!("{:<34}{:>10}{:>16}", "phase", "ops", "throughput");
    println!(
        "{:<34}{:>10}{:>16}",
        "async puts (sequential await)",
        ops,
        format_throughput(ops, sequential)
    );
    println!(
        "{:<34}{:>10}{:>16}",
        format!("async puts ({concurrency} concurrent tasks)"),
        concurrent_puts,
        format_throughput(concurrent_puts, concurrent_writes)
    );
    println!(
        "{:<34}{:>10}{:>16}",
        format!("async gets ({concurrency} concurrent tasks)"),
        reads,
        format_throughput(reads, concurrent_reads)
    );

    let backup = temp.path().join("backup");
    let copied = db.backup_to(&backup).await?;
    let stats = db.stats().await?;
    println!(
        "\nbackup: copied {} ({} data files) with tokio::fs -> {}",
        human_bytes(copied),
        stats.file_count,
        backup.display()
    );
    println!("total keys after benchmark: {}", db.len().await?);
    Ok(())
}

fn format_throughput(ops: usize, elapsed: Duration) -> String {
    if elapsed.as_secs_f64() <= 0.0 {
        return "-".to_string();
    }
    format!("{:.0} ops/s", ops as f64 / elapsed.as_secs_f64())
}

fn human_bytes(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["B", "KiB", "MiB", "GiB", "TiB"];
    let mut value = bytes as f64;
    let mut unit = 0;
    while value >= 1024.0 && unit < UNITS.len() - 1 {
        value /= 1024.0;
        unit += 1;
    }
    if unit == 0 {
        format!("{bytes} B")
    } else {
        format!("{value:.2} {}", UNITS[unit])
    }
}
