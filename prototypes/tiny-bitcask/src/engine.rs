//! The core Bitcask engine: an append-only log plus an in-memory keydir.
//!
//! Everything in this module is synchronous. Wrapping it in an async façade is
//! [`crate::async_engine`]'s job — see the README for the reasoning.

use std::collections::hash_map::Entry;
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufReader, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::datafile::{self, ActiveFile};
use crate::entry::{self, HintRecord, HEADER_SIZE, TOMBSTONE};
use crate::error::{Error, Result};

/// Tunables for [`Bitcask::open`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Options {
    /// Rotate the active file once appending another record would exceed this.
    /// Values below [`MIN_FILE_SIZE`] are clamped when the store is opened, so
    /// a struct literal with `0` behaves like the builder's minimum rather
    /// than producing one file per record.
    pub max_file_size: u64,
    /// Call `fsync` after every write (durable but much slower). Merge and
    /// rotation always sync.
    pub sync_writes: bool,
    /// Re-read the whole record and verify its CRC32 on every `get` (and check
    /// that the keydir points at the requested key) instead of trusting the
    /// keydir and reading only the value bytes. Off by default: the checksum is
    /// already verified whenever a file is *loaded*, so this only catches
    /// corruption that appears while the store is open, at the cost of reading
    /// the header again.
    pub verify_reads: bool,
}

/// Smallest rotation threshold the builder accepts: one record header plus a
/// byte. Anything smaller would still make progress, but it is almost always a
/// configuration mistake.
pub const MIN_FILE_SIZE: u64 = crate::entry::HEADER_SIZE as u64 + 1;

impl Default for Options {
    fn default() -> Self {
        Self {
            max_file_size: 64 * 1024 * 1024,
            sync_writes: false,
            verify_reads: false,
        }
    }
}

impl Options {
    /// Default options (64 MiB segments, no per-write `fsync`, fast reads).
    pub fn new() -> Self {
        Self::default()
    }

    /// Set the rotation threshold, clamped to [`MIN_FILE_SIZE`].
    pub fn with_max_file_size(mut self, max_file_size: u64) -> Self {
        self.max_file_size = max_file_size;
        self.clamped()
    }

    /// Turn per-write `fsync` on or off.
    pub fn with_sync_writes(mut self, sync_writes: bool) -> Self {
        self.sync_writes = sync_writes;
        self
    }

    /// Turn per-read CRC verification on or off.
    pub fn with_verify_reads(mut self, verify_reads: bool) -> Self {
        self.verify_reads = verify_reads;
        self
    }

    /// Clamp every field into a supported range.
    ///
    /// [`Bitcask::open`] applies this, so options built as a struct literal get
    /// the same guarantee as the builder methods.
    pub fn clamped(mut self) -> Self {
        self.max_file_size = self.max_file_size.max(MIN_FILE_SIZE);
        self
    }
}

/// Where the latest version of a key lives.
///
/// The paper's keydir stores `(file_id, offset, size)`; tiny-bitcask adds
/// `key_size` so a read can seek straight to the value without re-reading the
/// record header.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct KeyDirEntry {
    /// Data file holding the record.
    pub file_id: u32,
    /// Offset of the record header inside that file.
    pub offset: u64,
    /// Length of the key (1..=65535).
    pub key_size: u16,
    /// Length of the value (never [`TOMBSTONE`]: deleted keys leave the keydir).
    pub value_size: u32,
    /// Write time, copied from the record header.
    pub timestamp: u32,
}

impl KeyDirEntry {
    /// Bytes this record occupies on disk.
    pub fn record_size(&self) -> u64 {
        HEADER_SIZE as u64 + self.key_size as u64 + self.value_size as u64
    }

    /// Absolute offset of the value bytes.
    pub fn value_offset(&self) -> u64 {
        self.offset + HEADER_SIZE as u64 + self.key_size as u64
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Stats {
    pub file_count: usize,
    pub live_keys: usize,
    /// Bytes of live records (`header + key + value`), as tracked in the keydir.
    pub live_bytes: u64,
    /// Total size of the `*.data` files (hint files excluded).
    pub disk_bytes: u64,
    /// `disk_bytes - live_bytes`: overwritten values plus tombstones.
    pub stale_bytes: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MergeStats {
    /// Number of `*.data` files before the merge.
    pub files_before: usize,
    /// Number of `*.data` files after the merge.
    pub files_after: usize,
    /// Live keys rewritten into the merged files.
    pub live_keys: usize,
    /// Total size of the `*.data` files before the merge.
    pub bytes_before: u64,
    /// Total size of the `*.data` files after the merge.
    pub bytes_after: u64,
}

/// Keydir entries produced while loading one data file (or one hint file).
type LoadedEntries = Vec<(Vec<u8>, KeyDirEntry)>;

/// A single-writer, multi-reader-in-one-process Bitcask store.
///
/// Reads take `&mut self` because every reader keeps a file cursor; that is the
/// same serialisation a `Mutex` would impose, so the async wrapper shares one
/// instance behind a lock instead of pretending reads are lock-free.
#[derive(Debug)]
pub struct Bitcask {
    dir: PathBuf,
    options: Options,
    keydir: HashMap<Vec<u8>, KeyDirEntry>,
    /// Lazily opened read handles, one per data file.
    readers: HashMap<u32, File>,
    active: ActiveFile,
    /// Held for the lifetime of the store: `flock`/`LockFileEx` on `LOCK`.
    _lock: File,
}

impl Bitcask {
    /// Open (or create) the database in `dir`.
    ///
    /// Startup needs no log replay: the data file *is* the log. Every data file
    /// is scanned in id order to rebuild the keydir, using its `*.hint` file
    /// when merge has written one.
    pub fn open(dir: impl AsRef<Path>, options: Options) -> Result<Self> {
        let options = options.clamped();
        let dir = dir.as_ref().to_path_buf();
        if dir.exists() && !dir.is_dir() {
            return Err(Error::NotADirectory(dir));
        }
        fs::create_dir_all(&dir).map_err(|error| Error::io_path(&dir, error))?;
        let lock = datafile::lock_writer(&dir)?;
        // Finish (or discard) a merge that a previous process died in the middle
        // of, before scanning the directory.
        datafile::recover_merge_dir(&dir)?;

        let mut keydir = HashMap::new();
        let files = datafile::list_data_files(&dir)?;
        let active = match files.split_last() {
            None => ActiveFile::create(&dir, 0)?,
            Some((last, older)) => {
                for (file_id, path) in older {
                    Self::load_immutable_file(&dir, *file_id, path, &mut keydir)?;
                }
                // The active file is always scanned (not hinted): it is the one
                // that may end in a torn record after a crash.
                Self::scan_file(last.0, &last.1, &mut keydir, true)?;
                ActiveFile::open_existing(&dir, last.0)?
            }
        };

        Ok(Self {
            dir,
            options,
            keydir,
            readers: HashMap::new(),
            active,
            _lock: lock,
        })
    }

    /// Options the store was opened with.
    pub fn options(&self) -> Options {
        self.options
    }

    /// Directory holding the data files.
    pub fn dir(&self) -> &Path {
        &self.dir
    }

    /// Id of the file currently accepting writes.
    pub fn active_file_id(&self) -> u32 {
        self.active.id
    }

    /// Number of live keys (the keydir size).
    pub fn len(&self) -> usize {
        self.keydir.len()
    }

    /// Whether the store has no live keys at all.
    pub fn is_empty(&self) -> bool {
        self.keydir.is_empty()
    }

    /// Store `value` under `key`, overwriting any previous version.
    pub fn put(&mut self, key: &[u8], value: &[u8]) -> Result<()> {
        Self::validate_key(key)?;
        if value.len() > entry::MAX_VALUE_SIZE {
            return Err(Error::ValueTooLarge {
                size: value.len(),
                max: entry::MAX_VALUE_SIZE,
            });
        }
        let location = self.append(key, Some(value))?;
        // The keydir always points at the newest record; the old record stays
        // on disk until merge reclaims it.
        self.keydir.insert(key.to_vec(), location);
        Ok(())
    }

    /// Read `key`, returning `None` when it is absent (or deleted).
    ///
    /// One keydir lookup plus one seek + read: no scan, no read amplification.
    /// With [`Options::verify_reads`] the whole record is read and CRC-checked
    /// first.
    pub fn get(&mut self, key: &[u8]) -> Result<Option<Vec<u8>>> {
        match self.keydir.get(key).copied() {
            Some(location) => Ok(Some(self.read_value(key, &location)?)),
            None => Ok(None),
        }
    }

    /// Delete `key`, appending a tombstone. Returns whether the key was live.
    pub fn delete(&mut self, key: &[u8]) -> Result<bool> {
        Self::validate_key(key)?;
        let existed = self.keydir.contains_key(key);
        // Tombstone first, keydir second: a crash in between leaves a harmless
        // tombstone, never a resurrected key.
        self.append(key, None)?;
        self.keydir.remove(key);
        Ok(existed)
    }

    /// Live keys in lexicographic order (the keydir itself is a hash map, so
    /// iteration order is arbitrary — Bitcask has no ordered index).
    pub fn keys(&self) -> Vec<Vec<u8>> {
        let mut keys: Vec<Vec<u8>> = self.keydir.keys().cloned().collect();
        keys.sort();
        keys
    }

    /// Full scan: every live pair, sorted by key. Reads each value from disk —
    /// the deliberately weak spot of the model.
    pub fn scan(&mut self) -> Result<Vec<(Vec<u8>, Vec<u8>)>> {
        let mut live: Vec<(Vec<u8>, KeyDirEntry)> = self
            .keydir
            .iter()
            .map(|(key, location)| (key.clone(), *location))
            .collect();
        live.sort_by(|(left, _), (right, _)| left.cmp(right));

        let mut entries = Vec::with_capacity(live.len());
        for (key, location) in live {
            let value = self.read_value(&key, &location)?;
            entries.push((key, value));
        }
        Ok(entries)
    }

    /// Keydir and on-disk statistics; also what `merge` reports before/after.
    pub fn stats(&self) -> Result<Stats> {
        let files = datafile::list_data_files(&self.dir)?;
        let mut disk_bytes = 0u64;
        for (_, path) in &files {
            disk_bytes += fs::metadata(path)
                .map_err(|error| Error::io_path(path, error))?
                .len();
        }
        let live_bytes: u64 = self.keydir.values().map(KeyDirEntry::record_size).sum();
        Ok(Stats {
            file_count: files.len(),
            live_keys: self.keydir.len(),
            live_bytes,
            disk_bytes,
            stale_bytes: disk_bytes.saturating_sub(live_bytes),
        })
    }

    /// Merge (compact): drop overwritten values and tombstones, rewrite only
    /// the live records into fresh data files, and write hint files so the next
    /// startup does not have to read a single value.
    ///
    /// Crash behaviour: the merged output is written, synced and marked with
    /// [`datafile::MERGE_MARKER_NAME`] before anything in the database directory
    /// is touched, and the merged files are renamed in *before* the superseded
    /// ones are pruned. An interrupted merge is therefore completed by the next
    /// `open` (which moves marked leftovers in), so no live record — and no
    /// newer version of one — can go missing. The one remaining window is
    /// resurrection: a crash between the rename and prune steps leaves old files
    /// whose records can bring back keys that were deleted before the merge.
    /// A failed rename should be followed by reopening the directory; a failed
    /// prune is reported as [`Error::PruneFailed`] *after* the merge state has
    /// been committed, so the store stays correct and usable.
    pub fn merge(&mut self) -> Result<MergeStats> {
        let before = self.stats()?;
        let merge_dir = datafile::merge_dir_path(&self.dir);
        if merge_dir.exists() {
            fs::remove_dir_all(&merge_dir).map_err(|error| Error::io_path(&merge_dir, error))?;
        }
        fs::create_dir_all(&merge_dir).map_err(|error| Error::io_path(&merge_dir, error))?;

        // Rewrite live records in log order, so a future re-append keeps the
        // "later record wins" invariant.
        let mut live: Vec<(Vec<u8>, KeyDirEntry)> = self
            .keydir
            .iter()
            .map(|(key, location)| (key.clone(), *location))
            .collect();
        live.sort_by_key(|(_, location)| (location.file_id, location.offset));

        let first_new_id = self
            .active
            .id
            .checked_add(1)
            .ok_or_else(|| Error::Internal("file id space exhausted".to_string()))?;
        // Next id to hand out; kept as a running counter so that every id gets
        // the same overflow check.
        let mut next_file_id = first_new_id;
        let mut written: Vec<(u32, u64)> = Vec::new();
        let mut new_keydir: HashMap<Vec<u8>, KeyDirEntry> = HashMap::new();
        let mut current: Option<ActiveFile> = None;

        for (key, location) in &live {
            let value = self.read_value(key, location)?;
            let encoded = entry::encode(location.timestamp, key, Some(value.as_slice()));
            let rotate = match &current {
                Some(file) => {
                    file.size > 0 && file.size + encoded.len() as u64 > self.options.max_file_size
                }
                None => true,
            };
            if rotate {
                if let Some(mut file) = current.take() {
                    file.sync()?;
                    written.push((file.id, file.size));
                }
                let file_id = next_file_id;
                next_file_id = next_file_id
                    .checked_add(1)
                    .ok_or_else(|| Error::Internal("file id space exhausted".to_string()))?;
                current = Some(ActiveFile::create(&merge_dir, file_id)?);
            }
            let file = current
                .as_mut()
                .ok_or_else(|| Error::Internal("merge file handle missing".to_string()))?;
            let offset = file.append(&encoded)?;
            new_keydir.insert(
                key.clone(),
                KeyDirEntry {
                    file_id: file.id,
                    offset,
                    key_size: key.len() as u16,
                    value_size: value.len() as u32,
                    timestamp: location.timestamp,
                },
            );
        }
        if let Some(mut file) = current.take() {
            file.sync()?;
            written.push((file.id, file.size));
        }

        // Hint files for every merged file except the last: the last one
        // becomes the active file and is always scanned.
        if written.len() > 1 {
            for (file_id, _) in &written[..written.len() - 1] {
                Self::write_hint_file(&merge_dir, *file_id, &new_keydir)?;
            }
        }

        // The merged output is now complete and synced. Mark it before touching
        // the database directory: from here on a crash can be repaired by the
        // next open (which moves the leftovers in) instead of throwing away a
        // finished merge.
        datafile::write_merge_marker(&self.dir)?;

        // The pre-merge file list is taken *before* the renames so that the
        // prune step below can never touch the new files (their ids are all
        // higher, but being explicit keeps the two loops independent).
        let old_files = datafile::list_data_files(&self.dir)?;

        // Move the merged files into place first, then remove the old ones.
        // Since new ids are always above every existing id, both generations
        // can coexist: if the process dies in between (or a rename fails),
        // startup loads both and the higher ids win, so no live record is ever
        // missing. Deleting first would open a window where the only copy of
        // the data sits in `<dir>.merge`, which the next open discards.
        for (file_id, _) in &written {
            let source = datafile::data_file_path(&merge_dir, *file_id);
            let destination = datafile::data_file_path(&self.dir, *file_id);
            fs::rename(&source, &destination).map_err(|error| Error::io_path(&source, error))?;
            let hint_source = datafile::hint_file_path(&merge_dir, *file_id);
            if hint_source.exists() {
                let hint_destination = datafile::hint_file_path(&self.dir, *file_id);
                fs::rename(&hint_source, &hint_destination)
                    .map_err(|error| Error::io_path(&hint_source, error))?;
            }
        }

        // Close every handle on the old files before deleting them (Windows
        // cannot unlink an open file). The placeholder lives inside the merge
        // directory, which is removed at the end of this function.
        let placeholder_id = next_file_id;
        let placeholder = ActiveFile::create(&merge_dir, placeholder_id)?;
        drop(std::mem::replace(&mut self.active, placeholder));
        self.readers.clear();

        // Pruning is best effort: a leftover old file is harmless (higher ids
        // win on load) and the next merge retries. The first failure is still
        // reported, after the merge state below has been committed.
        let mut prune_error: Option<(PathBuf, std::io::Error)> = None;
        for (file_id, path) in &old_files {
            if let Err(error) = fs::remove_file(path) {
                prune_error.get_or_insert_with(|| (path.clone(), error));
            }
            let hint = datafile::hint_file_path(&self.dir, *file_id);
            if hint.exists() {
                if let Err(error) = fs::remove_file(&hint) {
                    prune_error.get_or_insert_with(|| (hint.clone(), error));
                }
            }
        }

        // Drops the placeholder handle, then removes the merge directory.
        self.active = match written.last() {
            Some((file_id, _)) => ActiveFile::open_existing(&self.dir, *file_id)?,
            None => ActiveFile::create(&self.dir, first_new_id)?,
        };
        fs::remove_dir_all(&merge_dir).map_err(|error| Error::io_path(&merge_dir, error))?;

        self.keydir = new_keydir;
        let after = self.stats()?;
        if let Some((path, source)) = prune_error {
            return Err(Error::PruneFailed { path, source });
        }
        Ok(MergeStats {
            files_before: before.file_count,
            files_after: after.file_count,
            live_keys: self.keydir.len(),
            bytes_before: before.disk_bytes,
            bytes_after: after.disk_bytes,
        })
    }

    /// Append one record, rotating the active file first when it is full.
    fn append(&mut self, key: &[u8], value: Option<&[u8]>) -> Result<KeyDirEntry> {
        let timestamp = now_timestamp();
        let encoded = entry::encode(timestamp, key, value);
        if self.active.size > 0
            && self.active.size + encoded.len() as u64 > self.options.max_file_size
        {
            self.rotate()?;
        }
        let offset = self.active.append(&encoded)?;
        if self.options.sync_writes {
            self.active.sync()?;
        }
        Ok(KeyDirEntry {
            file_id: self.active.id,
            offset,
            key_size: key.len() as u16,
            value_size: value.map_or(TOMBSTONE, |value| value.len() as u32),
            timestamp,
        })
    }

    /// Close the current active file and start the next file id.
    fn rotate(&mut self) -> Result<()> {
        self.active.sync()?;
        let next_id = self.active.id + 1;
        self.active = ActiveFile::create(&self.dir, next_id)?;
        Ok(())
    }

    /// Read the value of `location`.
    ///
    /// The fast path trusts the keydir and reads only the value bytes; with
    /// [`Options::verify_reads`] the full record is read and decoded instead.
    fn read_value(&mut self, key: &[u8], location: &KeyDirEntry) -> Result<Vec<u8>> {
        if self.options.verify_reads {
            return self.read_value_verified(key, location);
        }
        let offset = location.value_offset();
        let length = location.value_size as usize;
        let path = datafile::data_file_path(&self.dir, location.file_id);
        let file = self.reader(location.file_id)?;
        datafile::read_at(file, offset, length).map_err(|error| error.with_path(&path))
    }

    /// Re-read the whole record, check its CRC32 and confirm that the keydir
    /// entry really points at `key`.
    ///
    /// This is what catches corruption that appears *after* the file was
    /// loaded — a flipped bit inside a value, or a hint file that mapped a key
    /// to the wrong offset. The decode helper does the length, tombstone and
    /// checksum checks; the extra key comparison is what ties the record back
    /// to the lookup.
    fn read_value_verified(&mut self, key: &[u8], location: &KeyDirEntry) -> Result<Vec<u8>> {
        let record_len =
            HEADER_SIZE as u64 + u64::from(location.key_size) + u64::from(location.value_size);
        let path = datafile::data_file_path(&self.dir, location.file_id);
        let file = self.reader(location.file_id)?;
        let bytes = datafile::read_at(file, location.offset, record_len as usize)
            .map_err(|error| error.with_path(&path))?;

        let mut cursor = std::io::Cursor::new(bytes.as_slice());
        let decoded = entry::decode(&mut cursor, location.file_id, location.offset, record_len)
            .map_err(|error| error.with_path(&path))?
            .ok_or_else(|| {
                Error::corrupt(
                    location.file_id,
                    location.offset,
                    "indexed record is missing",
                )
            })?;

        if decoded.record.key != key {
            return Err(Error::corrupt(
                location.file_id,
                location.offset,
                "keydir entry points at a different key",
            ));
        }
        match decoded.record.value {
            Some(value) => Ok(value),
            None => Err(Error::corrupt(
                location.file_id,
                location.offset,
                "keydir entry points at a tombstone",
            )),
        }
    }

    fn reader(&mut self, file_id: u32) -> Result<&mut File> {
        match self.readers.entry(file_id) {
            Entry::Occupied(slot) => Ok(slot.into_mut()),
            // Only the cache miss pays for building the path.
            Entry::Vacant(slot) => {
                let path = datafile::data_file_path(&self.dir, file_id);
                Ok(slot.insert(datafile::open_read(&path)?))
            }
        }
    }

    fn validate_key(key: &[u8]) -> Result<()> {
        if key.is_empty() {
            return Err(Error::EmptyKey);
        }
        if key.len() > entry::MAX_KEY_SIZE {
            return Err(Error::KeyTooLarge {
                size: key.len(),
                max: entry::MAX_KEY_SIZE,
            });
        }
        Ok(())
    }

    /// Load one immutable data file into the keydir, preferring its hint file.
    fn load_immutable_file(
        dir: &Path,
        file_id: u32,
        path: &Path,
        keydir: &mut HashMap<Vec<u8>, KeyDirEntry>,
    ) -> Result<()> {
        let data_len = fs::metadata(path)
            .map_err(|error| Error::io_path(path, error))?
            .len();
        if let Some(entries) = Self::load_hint(dir, file_id, data_len)? {
            for (key, location) in entries {
                keydir.insert(key, location);
            }
            return Ok(());
        }
        Self::scan_file(file_id, path, keydir, false)?;
        Ok(())
    }

    /// Rebuild part of the keydir from `<file_id>.hint`.
    ///
    /// Returns `Ok(None)` whenever the hint file is missing or unusable: a hint
    /// file is only an optimisation, so any doubt falls back to scanning the
    /// data file, which is always authoritative.
    fn load_hint(dir: &Path, file_id: u32, data_len: u64) -> Result<Option<LoadedEntries>> {
        let path = datafile::hint_file_path(dir, file_id);
        // `is_file` (not `exists`): a directory that happens to be named
        // like a hint file must not look like one.
        if !path.is_file() {
            return Ok(None);
        }
        match Self::read_hint_file(file_id, &path, data_len) {
            Ok(entries) => Ok(Some(entries)),
            Err(_) => Ok(None),
        }
    }

    /// Read one hint file into keydir entries, checking that it is complete.
    ///
    /// A hint file is only trusted when its entries tile the whole data file:
    /// in offset order they must start at 0 and each record must end exactly
    /// where the next one starts, with the last entry ending at the data file's
    /// length. Merged files contain live records only, so the layout has no
    /// holes — which is what makes a truncated or partially copied hint file
    /// detectable instead of silently dropping every key it does not mention.
    ///
    /// The corruption errors built here report the owning `file_id` together
    /// with a byte offset inside the *hint* file, and every reason string says
    /// "hint file" so the two cannot be confused. `load_hint` swallows them and
    /// falls back to scanning the data file anyway.
    fn read_hint_file(file_id: u32, path: &Path, data_len: u64) -> Result<LoadedEntries> {
        let hint_len = fs::metadata(path)
            .map_err(|error| Error::io_path(path, error))?
            .len();
        let file = datafile::open_read(path)?;
        let mut reader = BufReader::new(file);
        let mut offset = 0u64;
        let mut entries = Vec::new();
        while let Some(decoded) = entry::decode_hint(&mut reader, file_id, offset, hint_len)? {
            offset += decoded.size;
            let HintRecord {
                timestamp,
                key_size,
                value_size,
                offset: record_offset,
                key,
            } = decoded.record;
            if value_size == TOMBSTONE || key_size as usize != key.len() {
                return Err(Error::corrupt(file_id, offset, "malformed hint record"));
            }
            entries.push((
                key,
                KeyDirEntry {
                    file_id,
                    offset: record_offset,
                    key_size,
                    value_size,
                    timestamp,
                },
            ));
        }

        entries.sort_by_key(|(_, location)| location.offset);
        let mut expected = 0u64;
        for (_, location) in &entries {
            if location.offset != expected {
                return Err(Error::corrupt(
                    file_id,
                    offset,
                    format!(
                        "hint file has a gap at offset {} (expected {expected})",
                        location.offset
                    ),
                ));
            }
            let record_len =
                HEADER_SIZE as u64 + u64::from(location.key_size) + u64::from(location.value_size);
            expected = location
                .offset
                .checked_add(record_len)
                .ok_or_else(|| Error::corrupt(file_id, offset, "hint record offset overflow"))?;
        }
        if expected != data_len {
            return Err(Error::corrupt(
                file_id,
                offset,
                format!("hint file covers {expected} of {data_len} bytes"),
            ));
        }
        Ok(entries)
    }

    /// Scan a data file record by record, applying each record to the keydir.
    ///
    /// With `truncate_tail` (the active file) a torn or corrupt trailing record
    /// is cut off: that is the "crash recovery" path of Bitcask. Without it
    /// (immutable files) corruption is reported, because a rotated file must be
    /// complete.
    fn scan_file(
        file_id: u32,
        path: &Path,
        keydir: &mut HashMap<Vec<u8>, KeyDirEntry>,
        truncate_tail: bool,
    ) -> Result<u64> {
        let file_len = fs::metadata(path)
            .map_err(|error| Error::io_path(path, error))?
            .len();
        let file = datafile::open_read(path)?;
        let mut reader = BufReader::new(file);
        let mut offset = 0u64;
        loop {
            match entry::decode(&mut reader, file_id, offset, file_len) {
                Ok(None) => return Ok(offset),
                Ok(Some(decoded)) => {
                    Self::apply(keydir, &decoded.record, file_id, offset);
                    offset += decoded.size;
                }
                Err(error) => {
                    if !truncate_tail {
                        return Err(error);
                    }
                    let file = fs::OpenOptions::new()
                        .write(true)
                        .open(path)
                        .map_err(|error| Error::io_path(path, error))?;
                    file.set_len(offset)
                        .map_err(|error| Error::io_path(path, error))?;
                    file.sync_all()
                        .map_err(|error| Error::io_path(path, error))?;
                    return Ok(offset);
                }
            }
        }
    }

    fn apply(
        keydir: &mut HashMap<Vec<u8>, KeyDirEntry>,
        record: &entry::LogRecord,
        file_id: u32,
        offset: u64,
    ) {
        match &record.value {
            Some(value) => {
                keydir.insert(
                    record.key.clone(),
                    KeyDirEntry {
                        file_id,
                        offset,
                        key_size: record.key.len() as u16,
                        value_size: value.len() as u32,
                        timestamp: record.timestamp,
                    },
                );
            }
            // A tombstone removes the key from the keydir; the record itself
            // stays on disk until the next merge.
            None => {
                keydir.remove(&record.key);
            }
        }
    }

    /// Write the hint file for one merged file.
    ///
    /// Note: every call filters the whole new keydir, which is fine at this
    /// scale but would become the hot loop of a larger implementation (rosedb
    /// collects the entries while writing the merged file instead).
    fn write_hint_file(
        dir: &Path,
        file_id: u32,
        keydir: &HashMap<Vec<u8>, KeyDirEntry>,
    ) -> Result<()> {
        let path = datafile::hint_file_path(dir, file_id);
        let mut records: Vec<HintRecord> = keydir
            .iter()
            .filter(|(_, location)| location.file_id == file_id)
            .map(|(key, location)| HintRecord {
                timestamp: location.timestamp,
                key_size: location.key_size,
                value_size: location.value_size,
                offset: location.offset,
                key: key.clone(),
            })
            .collect();
        records.sort_by_key(|record| record.offset);

        let mut file = File::create(&path).map_err(|error| Error::io_path(&path, error))?;
        for record in &records {
            file.write_all(&entry::encode_hint(record))
                .map_err(|error| Error::io_path(&path, error))?;
        }
        file.sync_all()
            .map_err(|error| Error::io_path(&path, error))?;
        Ok(())
    }
}

/// Seconds since the Unix epoch, truncated to the 4 bytes the header reserves.
fn now_timestamp() -> u32 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|elapsed| elapsed.as_secs() as u32)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn open(dir: &TempDir) -> Bitcask {
        Bitcask::open(dir.path().join("db"), Options::default()).expect("open")
    }

    #[test]
    fn put_get_delete_roundtrip() {
        let dir = TempDir::new().expect("tempdir");
        let mut db = open(&dir);
        db.put(b"a", b"1").expect("put");
        db.put(b"b", b"2").expect("put");
        assert_eq!(db.get(b"a").expect("get").as_deref(), Some(&b"1"[..]));
        assert_eq!(db.get(b"missing").expect("get"), None);
        assert!(db.delete(b"a").expect("delete"));
        assert!(!db.delete(b"a").expect("delete"));
        assert_eq!(db.get(b"a").expect("get"), None);
        assert_eq!(db.len(), 1);
    }

    #[test]
    fn empty_values_are_supported() {
        let dir = TempDir::new().expect("tempdir");
        let mut db = open(&dir);
        db.put(b"empty", b"").expect("put");
        assert_eq!(db.get(b"empty").expect("get").as_deref(), Some(&b""[..]));
    }

    #[test]
    fn key_and_value_bounds_are_enforced() {
        let dir = TempDir::new().expect("tempdir");
        let mut db = open(&dir);
        assert!(matches!(db.put(b"", b"v"), Err(Error::EmptyKey)));
        let too_long = vec![b'k'; entry::MAX_KEY_SIZE + 1];
        assert!(matches!(
            db.put(&too_long, b"v"),
            Err(Error::KeyTooLarge { .. })
        ));
    }

    #[test]
    fn zero_max_file_size_is_clamped_and_never_loops_forever() {
        let dir = TempDir::new().expect("tempdir");
        let options = Options::default().with_max_file_size(0);
        assert_eq!(options.max_file_size, MIN_FILE_SIZE);

        // A struct literal bypasses the builder, but `open` clamps it as well.
        let literal = Options {
            max_file_size: 0,
            ..Options::default()
        };
        let mut db = Bitcask::open(dir.path().join("db"), literal).expect("open");
        assert_eq!(db.options().max_file_size, MIN_FILE_SIZE);
        // Each record that does not fit an (almost) empty file lands in its own
        // file; the "file is not empty" guard is what keeps this finite.
        for index in 0..5 {
            db.put(format!("k{index}").as_bytes(), b"v").expect("put");
        }
        for index in 0..5 {
            assert!(db
                .get(format!("k{index}").as_bytes())
                .expect("get")
                .is_some());
        }
    }

    #[test]
    fn second_open_is_rejected_by_the_lock() {
        let dir = TempDir::new().expect("tempdir");
        let _db = open(&dir);
        let error = Bitcask::open(dir.path().join("db"), Options::default())
            .expect_err("second open must fail");
        assert!(matches!(error, Error::Locked(_)), "{error}");
    }
}
