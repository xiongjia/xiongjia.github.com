//! Error type shared by every module of the engine.
//!
//! A hand-written enum (instead of a crate like `anyhow`) keeps the failure
//! modes explicit: the caller can tell "key is simply absent" from "the log is
//! corrupt" from "another process holds the writer lock".

use std::fmt;
use std::io;
use std::path::{Path, PathBuf};

/// Convenience alias used across the crate.
pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug)]
pub enum Error {
    /// Wraps an [`io::Error`], keeping the file path when one is known.
    Io {
        path: Option<PathBuf>,
        source: io::Error,
    },
    /// A data file could not be decoded (bad CRC32, truncated record, ...).
    Corrupt {
        file_id: u32,
        offset: u64,
        reason: String,
    },
    /// Another process already opened this directory for writing.
    Locked(PathBuf),
    /// `merge` rewrote the data successfully, but a superseded file could not
    /// be removed. The merge result is already in place (higher file ids win),
    /// so the leftover file is harmless and the next merge retries.
    PruneFailed { path: PathBuf, source: io::Error },
    /// The key is longer than the 2-byte key-size field can express.
    KeyTooLarge { size: usize, max: usize },
    /// The value is longer than the 4-byte value-size field can express (or
    /// than the tombstone sentinel allows).
    ValueTooLarge { size: usize, max: usize },
    /// An empty key cannot be told apart from a malformed record header.
    EmptyKey,
    /// An engine invariant or a hard limit was hit: this is a bug or an
    /// exhausted resource (for example the 32-bit file-id space), never bad
    /// input or a damaged database.
    Internal(String),
    /// A `spawn_blocking` task panicked or was cancelled.
    Task(String),
    /// A thread panicked while holding the engine mutex.
    Poisoned,
    /// The directory passed to `open` exists but is not a directory.
    NotADirectory(PathBuf),
}

impl Error {
    /// Wrap an [`io::Error`] when no path is associated with the operation.
    pub fn io(source: io::Error) -> Self {
        Error::Io { path: None, source }
    }

    /// Wrap an [`io::Error`] together with the path it happened on.
    pub fn io_path(path: impl AsRef<Path>, source: io::Error) -> Self {
        Error::Io {
            path: Some(path.as_ref().to_path_buf()),
            source,
        }
    }

    /// Build a [`Error::Corrupt`] with a human-readable reason.
    pub fn corrupt(file_id: u32, offset: u64, reason: impl Into<String>) -> Self {
        Error::Corrupt {
            file_id,
            offset,
            reason: reason.into(),
        }
    }

    /// Attach a path to an [`Error::Io`] that was built without one.
    ///
    /// Every other variant (including an `Io` error that already knows its
    /// path) is returned unchanged, so it is safe to apply to the result of a
    /// generic helper such as [`crate::datafile::read_at`].
    pub fn with_path(self, path: impl AsRef<Path>) -> Self {
        match self {
            Error::Io { path: None, source } => Error::Io {
                path: Some(path.as_ref().to_path_buf()),
                source,
            },
            other => other,
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Io {
                path: Some(path),
                source,
            } => write!(f, "io error on {}: {source}", path.display()),
            Error::Io { path: None, source } => write!(f, "io error: {source}"),
            Error::Corrupt {
                file_id,
                offset,
                reason,
            } => write!(
                f,
                "corrupt record in file {file_id} at offset {offset}: {reason}"
            ),
            Error::Locked(path) => write!(
                f,
                "database {} is already open (LOCK is held by another process)",
                path.display()
            ),
            Error::PruneFailed { path, source } => write!(
                f,
                "merge is committed, but the superseded file {} could not be removed: {source}",
                path.display()
            ),
            Error::KeyTooLarge { size, max } => {
                write!(f, "key is {size} bytes, the limit is {max} bytes")
            }
            Error::ValueTooLarge { size, max } => {
                write!(f, "value is {size} bytes, the limit is {max} bytes")
            }
            Error::EmptyKey => write!(f, "keys must not be empty"),
            Error::Internal(message) => write!(f, "internal error: {message}"),
            Error::Task(message) => write!(f, "background task failed: {message}"),
            Error::Poisoned => write!(f, "engine mutex was poisoned by a panicking thread"),
            Error::NotADirectory(path) => write!(f, "{} is not a directory", path.display()),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Error::Io { source, .. } | Error::PruneFailed { source, .. } => Some(source),
            _ => None,
        }
    }
}

impl From<io::Error> for Error {
    fn from(source: io::Error) -> Self {
        Error::io(source)
    }
}
