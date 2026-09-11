//! `tiny-bitcask` — a minimal Bitcask-style KV store.
//!
//! The crate is split so the storage logic can be tested (and reused) without
//! the CLI:
//!
//! * [`entry`] — binary codecs for data records and hint records,
//! * [`datafile`] — file naming, the writer lock, the append-only active file,
//! * [`engine`] — the Bitcask engine itself: log + keydir + merge,
//! * [`async_engine`] — a `tokio` façade over the synchronous engine,
//! * [`error`] — the shared error type.
//!
//! The design notes (on-disk format, data flow, deviations from the paper) live
//! in `prototypes/tiny-bitcask/README.md`.

pub mod async_engine;
pub mod datafile;
pub mod engine;
pub mod entry;
pub mod error;

pub use engine::{Bitcask, KeyDirEntry, MergeStats, Options, Stats, MIN_FILE_SIZE};
