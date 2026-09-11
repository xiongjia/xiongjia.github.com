//! Async façade over the synchronous core engine.
//!
//! The engine does blocking file I/O, so the honest way to make it awaitable is
//! to move each operation onto a blocking thread pool instead of sprinkling
//! `tokio::fs` calls through the storage code:
//!
//! * `spawn_blocking` hands the call to Tokio's blocking pool, keeping the async
//!   worker threads free to poll other tasks;
//! * `Arc<Mutex<Bitcask>>` shares the single writer (and the cursor-based
//!   readers) between tasks;
//! * the operations themselves stay ordinary `Result`-returning functions, so
//!   the same code is used by the sync CLI path and by the tests.
//!
//! `tokio::fs` is used where it genuinely helps: [`AsyncBitcask::backup_to`]
//! streams the data files out with real async file copies.

use std::path::Path;
use std::sync::{Arc, Mutex};

use crate::datafile;
use crate::engine::{Bitcask, MergeStats, Options, Stats};
use crate::error::{Error, Result};

/// A cheap-to-clone handle to the shared engine.
#[derive(Clone)]
pub struct AsyncBitcask {
    inner: Arc<Mutex<Bitcask>>,
}

impl AsyncBitcask {
    /// Open the database without blocking the caller's async thread.
    pub async fn open(dir: impl AsRef<Path>, options: Options) -> Result<Self> {
        let dir = dir.as_ref().to_path_buf();
        let db = tokio::task::spawn_blocking(move || Bitcask::open(dir, options))
            .await
            .map_err(|error| Error::Task(error.to_string()))??;
        Ok(Self {
            inner: Arc::new(Mutex::new(db)),
        })
    }

    /// Store `value` under `key`, overwriting any previous version.
    pub async fn put(&self, key: Vec<u8>, value: Vec<u8>) -> Result<()> {
        self.with_engine(move |db| db.put(&key, &value)).await
    }

    /// Read `key`; `None` when it is absent or deleted.
    pub async fn get(&self, key: Vec<u8>) -> Result<Option<Vec<u8>>> {
        self.with_engine(move |db| db.get(&key)).await
    }

    /// Delete `key`, returning whether it was live before the call.
    pub async fn delete(&self, key: Vec<u8>) -> Result<bool> {
        self.with_engine(move |db| db.delete(&key)).await
    }

    /// Live keys in lexicographic order.
    pub async fn keys(&self) -> Result<Vec<Vec<u8>>> {
        self.with_engine(|db| Ok(db.keys())).await
    }

    /// Number of live keys.
    pub async fn len(&self) -> Result<usize> {
        self.with_engine(|db| Ok(db.len())).await
    }

    /// Whether the store has no live keys.
    pub async fn is_empty(&self) -> Result<bool> {
        self.with_engine(|db| Ok(db.is_empty())).await
    }

    /// Keydir and on-disk statistics.
    pub async fn stats(&self) -> Result<Stats> {
        self.with_engine(|db| db.stats()).await
    }

    /// Compact the store (see [`Bitcask::merge`]).
    pub async fn merge(&self) -> Result<MergeStats> {
        self.with_engine(|db| db.merge()).await
    }

    /// Copy every data (and hint) file into `dest` using `tokio::fs`.
    ///
    /// Files are first copied into a staging directory next to `dest` and then
    /// renamed into place, so a backup can only ever contain *complete* files:
    /// a crash leaves an earlier (openable, consistent) prefix of the database
    /// plus a `.<name>.partial` directory rather than a torn data file (any
    /// previous staging directory with that name is discarded on the next run).
    /// A completion marker (`.backup-complete`) is written as the last step, so
    /// a tool can tell a finished backup from an interrupted prefix; it is
    /// removed again at the start of every run.
    ///
    /// This is the Bitcask backup story: rotated files are immutable, so
    /// copying them block by block is a correct backup.
    pub async fn backup_to(&self, dest: impl AsRef<Path>) -> Result<u64> {
        let dest = dest.as_ref().to_path_buf();
        let (dir, files) = self
            .with_engine(|db| {
                let dir = db.dir().to_path_buf();
                let files = datafile::list_data_files(&dir)?;
                Ok((dir, files))
            })
            .await?;

        let name = dest
            .file_name()
            .map(|name| name.to_string_lossy().into_owned())
            .unwrap_or_else(|| "backup".to_string());
        // Dot-prefixed so the staging path is unlikely to collide with (and
        // delete) a directory the user actually cares about.
        let staging = dest.with_file_name(format!(".{name}.partial"));
        if tokio::fs::try_exists(&staging)
            .await
            .map_err(|error| Error::io_path(&staging, error))?
        {
            tokio::fs::remove_dir_all(&staging)
                .await
                .map_err(|error| Error::io_path(&staging, error))?;
        }
        tokio::fs::create_dir_all(&staging)
            .await
            .map_err(|error| Error::io_path(&staging, error))?;
        tokio::fs::create_dir_all(&dest)
            .await
            .map_err(|error| Error::io_path(&dest, error))?;

        // A marker left by an earlier run must not survive into this one: the
        // backup is only complete once the last file below has been placed.
        let marker = datafile::backup_marker_path(&dest);
        if tokio::fs::try_exists(&marker)
            .await
            .map_err(|error| Error::io_path(&marker, error))?
        {
            tokio::fs::remove_file(&marker)
                .await
                .map_err(|error| Error::io_path(&marker, error))?;
        }

        let mut copied = 0u64;
        let mut copied_files = 0usize;
        for (file_id, source) in files {
            copied +=
                copy_into(&staging, &dest, &source, &datafile::data_file_name(file_id)).await?;
            copied_files += 1;
            // A missing or unreadable hint file just means the restored copy
            // will rescan its data file; only regular files are copied.
            let hint_source = datafile::hint_file_path(&dir, file_id);
            let has_hint = tokio::fs::metadata(&hint_source)
                .await
                .map(|metadata| metadata.is_file())
                .unwrap_or(false);
            if has_hint {
                copied += copy_into(
                    &staging,
                    &dest,
                    &hint_source,
                    &datafile::hint_file_name(file_id),
                )
                .await?;
                copied_files += 1;
            }
        }
        tokio::fs::remove_dir_all(&staging)
            .await
            .map_err(|error| Error::io_path(&staging, error))?;

        let summary = format!("files={copied_files} bytes={copied}\n");
        tokio::fs::write(&marker, summary)
            .await
            .map_err(|error| Error::io_path(&marker, error))?;
        Ok(copied)
    }

    /// Run one synchronous engine call on the blocking pool.
    async fn with_engine<T, F>(&self, operation: F) -> Result<T>
    where
        F: FnOnce(&mut Bitcask) -> Result<T> + Send + 'static,
        T: Send + 'static,
    {
        let db = Arc::clone(&self.inner);
        tokio::task::spawn_blocking(move || {
            let mut db = db.lock().map_err(|_| Error::Poisoned)?;
            operation(&mut db)
        })
        .await
        .map_err(|error| Error::Task(error.to_string()))?
    }
}

/// Copy `source` into `staging` and rename it to `dest/<name>`.
///
/// The rename makes each file appear in the backup atomically, so a crash can
/// leave a partial *set* of files but never a torn file.
async fn copy_into(staging: &Path, dest: &Path, source: &Path, name: &str) -> Result<u64> {
    let staged = staging.join(name);
    let copied = tokio::fs::copy(source, &staged)
        .await
        .map_err(|error| Error::io_path(source, error))?;
    let target = dest.join(name);
    tokio::fs::rename(&staged, &target)
        .await
        .map_err(|error| Error::io_path(&target, error))?;
    Ok(copied)
}
