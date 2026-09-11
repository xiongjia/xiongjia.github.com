//! On-disk layout helpers: file naming, directory listing, the writer lock and
//! the append-only active file handle.
//!
//! A database directory contains:
//!
//! ```text
//! <dir>/
//! ├── LOCK            # exclusive writer lock (flock), one open process at a time
//! ├── 000000.data     # immutable merged/rotated data files
//! ├── 000000.hint     # optional keydir acceleration file, written by merge
//! ├── 000001.data
//! └── 000002.data     # the active file (highest id) — the only file we append to
//! ```
//!
//! `merge` additionally builds `<dir>.merge/` next to the directory, with a
//! `.merge-ready` marker that tells the next `open` whether the leftovers are a
//! complete generation to move in or a half-written attempt to discard.

use std::fs::{self, File, OpenOptions};
use std::io::{Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

use crate::error::{Error, Result};

pub const DATA_EXT: &str = "data";
pub const HINT_EXT: &str = "hint";
pub const LOCK_FILE_NAME: &str = "LOCK";
/// Suffix of the temporary directory `merge` builds its output in. It is a
/// sibling of the database directory, so the final moves are plain renames.
pub const MERGE_DIR_SUFFIX: &str = ".merge";
/// Marker file inside the merge directory. `merge` writes and fsyncs it only
/// after every merged file and hint file is complete, so its presence proves
/// that the leftovers in `<dir>.merge` are a usable generation.
pub const MERGE_MARKER_NAME: &str = ".merge-ready";
/// Marker file written into a backup directory once every file has been copied.
/// Its absence means the backup was interrupted and holds only a prefix.
pub const BACKUP_MARKER_NAME: &str = ".backup-complete";

/// Zero-padded name of a data file (`42 -> "000042.data"`), so a lexicographic
/// directory listing is also the id order.
pub fn data_file_name(file_id: u32) -> String {
    format!("{file_id:06}.{DATA_EXT}")
}

/// Zero-padded name of a hint file (`42 -> "000042.hint"`).
pub fn hint_file_name(file_id: u32) -> String {
    format!("{file_id:06}.{HINT_EXT}")
}

/// Path of a data file inside `dir`.
pub fn data_file_path(dir: &Path, file_id: u32) -> PathBuf {
    dir.join(data_file_name(file_id))
}

/// Path of a hint file inside `dir`.
pub fn hint_file_path(dir: &Path, file_id: u32) -> PathBuf {
    dir.join(hint_file_name(file_id))
}

/// Path of the backup completion marker inside a backup directory.
pub fn backup_marker_path(dir: &Path) -> PathBuf {
    dir.join(BACKUP_MARKER_NAME)
}

/// Directory `merge` writes into: `<dir>.merge` next to the database directory.
pub fn merge_dir_path(dir: &Path) -> PathBuf {
    let name = dir
        .file_name()
        .map(|name| name.to_string_lossy().into_owned())
        .unwrap_or_else(|| "bitcask".to_string());
    dir.with_file_name(format!("{name}{MERGE_DIR_SUFFIX}"))
}

/// Every `*.data` file in `dir`, sorted by ascending file id.
///
/// Directories that merely match the pattern (a hand-made `000005.data/`, a
/// mount point) are ignored, but links to regular files are followed with
/// `Path::is_file` — a segment may legitimately live behind a symlink.
pub fn list_data_files(dir: &Path) -> Result<Vec<(u32, PathBuf)>> {
    let entries = fs::read_dir(dir).map_err(|error| Error::io_path(dir, error))?;
    let mut files = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|error| Error::io_path(dir, error))?;
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        if path.extension().and_then(|ext| ext.to_str()) != Some(DATA_EXT) {
            continue;
        }
        let Some(stem) = path.file_stem().and_then(|stem| stem.to_str()) else {
            continue;
        };
        let Ok(file_id) = stem.parse::<u32>() else {
            continue;
        };
        files.push((file_id, path));
    }
    files.sort_by_key(|(file_id, _)| *file_id);
    Ok(files)
}

/// Open a data file for reading only.
pub fn open_read(path: &Path) -> Result<File> {
    File::open(path).map_err(|error| Error::io_path(path, error))
}

/// Open a data file for appending (creating it if needed).
pub fn open_append(path: &Path) -> Result<File> {
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| Error::io_path(path, error))
}

/// Take the exclusive writer lock for `dir`.
///
/// `std::fs::File::try_lock` maps to `flock(2)` on Unix and `LockFileEx` on
/// Windows, so the lock dies with the process even on a hard crash.
pub fn lock_writer(dir: &Path) -> Result<File> {
    let path = dir.join(LOCK_FILE_NAME);
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(&path)
        .map_err(|error| Error::io_path(&path, error))?;
    match file.try_lock() {
        Ok(()) => Ok(file),
        Err(std::fs::TryLockError::WouldBlock) => Err(Error::Locked(dir.to_path_buf())),
        Err(std::fs::TryLockError::Error(error)) => Err(Error::io_path(&path, error)),
    }
}

/// Mark the merge output in `<dir>.merge` as complete and durable.
///
/// Called after every merged file and hint file has been written and synced,
/// and before the first rename. If the process dies later, the next `open`
/// knows the leftovers can be moved into the database directory instead of
/// being thrown away.
pub fn write_merge_marker(dir: &Path) -> Result<()> {
    let path = merge_dir_path(dir).join(MERGE_MARKER_NAME);
    let mut file = File::create(&path).map_err(|error| Error::io_path(&path, error))?;
    file.write_all(b"merge output complete\n")
        .map_err(|error| Error::io_path(&path, error))?;
    file.sync_all()
        .map_err(|error| Error::io_path(&path, error))?;
    Ok(())
}

/// Finish or discard a merge that was interrupted by a crash.
///
/// * With the [`MERGE_MARKER_NAME`] marker present, the files in `<dir>.merge`
///   are a complete generation whose ids are above everything in the database
///   directory, so they are moved in first: whether the previous process died
///   before the renames, in the middle of them, or after them, the newest
///   version of every record ends up on disk.
/// * Without the marker the merge never finished writing its output, and the
///   original files are untouched at that point, so the directory is simply
///   deleted.
///
/// A file that already exists in the database directory is left alone (its
/// merge-directory twin is dropped with the directory); that cannot happen for
/// a real merge, whose ids are all fresh.
pub fn recover_merge_dir(dir: &Path) -> Result<()> {
    let merge_dir = merge_dir_path(dir);
    if !merge_dir.exists() {
        return Ok(());
    }
    let marked = merge_dir.join(MERGE_MARKER_NAME).exists();
    if marked {
        let entries =
            fs::read_dir(&merge_dir).map_err(|error| Error::io_path(&merge_dir, error))?;
        for entry in entries {
            let entry = entry.map_err(|error| Error::io_path(&merge_dir, error))?;
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            let extension = path.extension().and_then(|extension| extension.to_str());
            if !matches!(extension, Some(DATA_EXT) | Some(HINT_EXT)) {
                continue;
            }
            let Some(file_name) = path.file_name() else {
                continue;
            };
            let destination = dir.join(file_name);
            if destination.exists() {
                continue;
            }
            fs::rename(&path, &destination).map_err(|error| Error::io_path(&path, error))?;
        }
    }
    fs::remove_dir_all(&merge_dir).map_err(|error| Error::io_path(&merge_dir, error))?;
    Ok(())
}

/// The only file a running instance appends to. Rotating replaces this value
/// with a handle on the next file id.
#[derive(Debug)]
pub struct ActiveFile {
    /// Id of this file (also encoded in its name).
    pub id: u32,
    /// Absolute or relative path of the data file.
    pub path: PathBuf,
    writer: File,
    /// Number of bytes written so far = offset of the next record.
    pub size: u64,
}

impl ActiveFile {
    /// Create a brand-new (empty) active file with `file_id`.
    pub fn create(dir: &Path, file_id: u32) -> Result<Self> {
        let path = data_file_path(dir, file_id);
        let writer = open_append(&path)?;
        Ok(Self {
            id: file_id,
            path,
            writer,
            size: 0,
        })
    }

    /// Reopen an existing data file for appending; the size comes from the
    /// filesystem (the loader has already truncated any torn tail).
    pub fn open_existing(dir: &Path, file_id: u32) -> Result<Self> {
        let path = data_file_path(dir, file_id);
        let size = fs::metadata(&path)
            .map_err(|error| Error::io_path(&path, error))?
            .len();
        let writer = open_append(&path)?;
        Ok(Self {
            id: file_id,
            path,
            writer,
            size,
        })
    }

    /// Append encoded bytes, returning the offset the record starts at.
    pub fn append(&mut self, bytes: &[u8]) -> Result<u64> {
        let offset = self.size;
        self.writer
            .write_all(bytes)
            .map_err(|error| Error::io_path(&self.path, error))?;
        self.size += bytes.len() as u64;
        Ok(offset)
    }

    /// Flush the file's data to disk (`fsync`).
    pub fn sync(&mut self) -> Result<()> {
        self.writer
            .sync_data()
            .map_err(|error| Error::io_path(&self.path, error))
    }
}

/// Read `length` bytes at `offset` from a file handle.
///
/// Seeking is why the core engine takes `&mut self`: a `File` owns its cursor,
/// so reads are serialised (which is exactly what the `Mutex` in the async
/// wrapper relies on). Errors carry no path — the caller adds one with
/// [`crate::error::Error::with_path`] when it knows which segment failed.
pub fn read_at(file: &mut File, offset: u64, length: usize) -> Result<Vec<u8>> {
    let mut buffer = vec![0u8; length];
    file.seek(SeekFrom::Start(offset)).map_err(Error::io)?;
    std::io::Read::read_exact(file, &mut buffer).map_err(Error::io)?;
    Ok(buffer)
}
