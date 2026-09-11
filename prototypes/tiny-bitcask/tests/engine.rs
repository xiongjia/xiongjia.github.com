//! End-to-end tests for the synchronous engine: round trips, crash recovery,
//! corruption handling, rotation and merge.

use std::fs;
use std::io::Write;

use tempfile::TempDir;
use tiny_bitcask::engine::Bitcask;
use tiny_bitcask::entry;
use tiny_bitcask::error::Error;
use tiny_bitcask::{datafile, Options};

/// Open the database that lives at `<tempdir>/db`.
fn open(dir: &TempDir, options: Options) -> Bitcask {
    Bitcask::open(dir.path().join("db"), options).expect("open database")
}

fn db_dir(dir: &TempDir) -> std::path::PathBuf {
    dir.path().join("db")
}

/// Build the database and immediately compact it, so that its data lives in
/// several files that have hint files.
fn build_merged_db(dir: &TempDir, options: Options, keys: usize) {
    let mut db = open(dir, options);
    for index in 0..keys {
        put(&mut db, &format!("key:{index:03}"), &"v".repeat(100));
    }
    let merged = db.merge().expect("merge");
    // More than one file means every file but the last one got a hint file.
    assert!(merged.files_after > 1, "need several files: {merged:?}");
}

/// Id and path of the first (immutable, hinted) file of a merged database.
fn first_immutable(dir: &TempDir) -> (u32, std::path::PathBuf) {
    let files = datafile::list_data_files(&db_dir(dir)).expect("list");
    files.first().cloned().expect("at least one data file")
}

/// Assert every `key:NNN` written by [`merged_db`] is still readable.
fn assert_all_keys(dir: &TempDir, options: Options, keys: usize) {
    let mut db = open(dir, options);
    for index in 0..keys {
        let key = format!("key:{index:03}");
        assert!(
            get(&mut db, &key).is_some(),
            "{key} was lost (hint file trusted when it should not be)"
        );
    }
    assert_eq!(db.len(), keys);
}

fn put(db: &mut Bitcask, key: &str, value: &str) {
    db.put(key.as_bytes(), value.as_bytes()).expect("put");
}

fn get(db: &mut Bitcask, key: &str) -> Option<String> {
    db.get(key.as_bytes())
        .expect("get")
        .map(|value| String::from_utf8(value).expect("utf-8"))
}

#[test]
fn put_overwrite_delete_roundtrip() {
    let dir = TempDir::new().expect("tempdir");
    let mut db = open(&dir, Options::default());

    put(&mut db, "user:1", "alice");
    put(&mut db, "user:2", "bob");
    assert_eq!(get(&mut db, "user:1").as_deref(), Some("alice"));
    assert_eq!(get(&mut db, "missing"), None);

    // Overwriting keeps the newest version and leaves the old one as stale bytes.
    put(&mut db, "user:1", "alicia");
    assert_eq!(get(&mut db, "user:1").as_deref(), Some("alicia"));
    let stats = db.stats().expect("stats");
    assert_eq!(stats.live_keys, 2);
    assert!(stats.stale_bytes > 0, "{stats:?}");

    assert!(db.delete(b"user:2").expect("delete"));
    assert!(!db.delete(b"user:2").expect("delete again"));
    assert_eq!(get(&mut db, "user:2"), None);
    assert_eq!(db.len(), 1);
}

#[test]
fn empty_values_survive_reopen() {
    let dir = TempDir::new().expect("tempdir");
    {
        let mut db = open(&dir, Options::default());
        put(&mut db, "empty", "");
    }
    let mut db = open(&dir, Options::default());
    assert_eq!(get(&mut db, "empty").as_deref(), Some(""));
}

#[test]
fn reopen_rebuilds_the_keydir_from_the_log() {
    let dir = TempDir::new().expect("tempdir");
    {
        let mut db = open(&dir, Options::default());
        put(&mut db, "a", "1");
        put(&mut db, "b", "2");
        put(&mut db, "c", "3");
        db.delete(b"b").expect("delete");
        put(&mut db, "a", "1-updated");
    }

    let mut db = open(&dir, Options::default());
    assert_eq!(get(&mut db, "a").as_deref(), Some("1-updated"));
    assert_eq!(get(&mut db, "b"), None);
    assert_eq!(get(&mut db, "c").as_deref(), Some("3"));
    assert_eq!(db.keys(), vec![b"a".to_vec(), b"c".to_vec()]);
}

#[test]
fn large_values_roundtrip() {
    let dir = TempDir::new().expect("tempdir");
    let value = vec![b'z'; 256 * 1024];
    {
        let mut db = open(&dir, Options::default());
        db.put(b"big", &value).expect("put");
    }
    let mut db = open(&dir, Options::default());
    assert_eq!(db.get(b"big").expect("get").as_deref(), Some(&value[..]));
}

#[test]
fn scan_returns_sorted_live_pairs() {
    let dir = TempDir::new().expect("tempdir");
    let mut db = open(&dir, Options::default());
    put(&mut db, "c", "3");
    put(&mut db, "a", "1");
    put(&mut db, "b", "2");
    db.delete(b"b").expect("delete");

    let pairs: Vec<(String, String)> = db
        .scan()
        .expect("scan")
        .into_iter()
        .map(|(key, value)| {
            (
                String::from_utf8(key).expect("utf-8"),
                String::from_utf8(value).expect("utf-8"),
            )
        })
        .collect();
    assert_eq!(
        pairs,
        vec![
            ("a".to_string(), "1".to_string()),
            ("c".to_string(), "3".to_string())
        ]
    );
}

#[test]
fn rotation_splits_the_log_into_multiple_files() {
    let dir = TempDir::new().expect("tempdir");
    let options = Options::default().with_max_file_size(256);
    {
        let mut db = open(&dir, options);
        for index in 0..20 {
            put(&mut db, &format!("key:{index:03}"), &"v".repeat(64));
        }
        let stats = db.stats().expect("stats");
        assert!(stats.file_count > 1, "expected rotation: {stats:?}");
    }

    // Every record is still reachable after a full reload.
    let mut db = open(&dir, options);
    for index in 0..20 {
        assert_eq!(
            get(&mut db, &format!("key:{index:03}")).as_deref(),
            Some(&*"v".repeat(64))
        );
    }
    assert!(db.stats().expect("stats").file_count > 1);
}

#[test]
fn torn_tail_is_truncated_on_open() {
    let dir = TempDir::new().expect("tempdir");
    {
        let mut db = open(&dir, Options::default());
        put(&mut db, "keep", "value");
    }

    // Simulate a crash in the middle of an append: a partial record header.
    let files = datafile::list_data_files(&db_dir(&dir)).expect("list");
    let (_, active) = files.last().expect("one data file");
    let valid_len = fs::metadata(active).expect("metadata").len();
    let mut file = fs::OpenOptions::new()
        .append(true)
        .open(active)
        .expect("append");
    file.write_all(&[0x01, 0x02, 0x03]).expect("write garbage");
    drop(file);

    let mut db = open(&dir, Options::default());
    assert_eq!(get(&mut db, "keep").as_deref(), Some("value"));
    // The torn tail was cut off, so the file is back to its last valid record.
    assert_eq!(fs::metadata(active).expect("metadata").len(), valid_len);

    // ... and the recovered store still accepts writes.
    put(&mut db, "after-recovery", "ok");
    assert_eq!(get(&mut db, "after-recovery").as_deref(), Some("ok"));
}

#[test]
fn crc_mismatch_in_the_tail_is_dropped() {
    let dir = TempDir::new().expect("tempdir");
    {
        let mut db = open(&dir, Options::default());
        put(&mut db, "keep", "value");
    }

    let files = datafile::list_data_files(&db_dir(&dir)).expect("list");
    let (_, active) = files.last().expect("one data file");
    // A structurally valid record with a broken checksum: a half-written page.
    let mut broken = entry::encode(1, b"torn", Some(b"payload"));
    let last = broken.len() - 1;
    broken[last] ^= 0xff;
    let mut file = fs::OpenOptions::new()
        .append(true)
        .open(active)
        .expect("append");
    file.write_all(&broken).expect("write broken record");
    drop(file);

    let mut db = open(&dir, Options::default());
    assert_eq!(get(&mut db, "keep").as_deref(), Some("value"));
    assert_eq!(get(&mut db, "torn"), None);
}

#[test]
fn corruption_in_an_immutable_file_is_reported() {
    let dir = TempDir::new().expect("tempdir");
    let options = Options::default().with_max_file_size(256);
    {
        let mut db = open(&dir, options);
        for index in 0..20 {
            put(&mut db, &format!("key:{index:03}"), &"v".repeat(64));
        }
    }

    // Damage a byte inside the first (immutable) file's last record value.
    let files = datafile::list_data_files(&db_dir(&dir)).expect("list");
    assert!(files.len() > 1, "rotation expected");
    let (first_id, first_path) = files.first().expect("first file");
    let mut bytes = fs::read(first_path).expect("read");
    let length = bytes.len();
    bytes[length - 1] ^= 0xff;
    fs::write(first_path, &bytes).expect("write");

    let error = Bitcask::open(db_dir(&dir), options).expect_err("corruption must surface");
    assert!(
        matches!(error, Error::Corrupt { file_id, .. } if file_id == *first_id),
        "{error}"
    );
}

#[test]
fn merge_reclaims_space_and_keeps_live_data() {
    let dir = TempDir::new().expect("tempdir");
    let options = Options::default().with_max_file_size(1024);
    let mut db = open(&dir, options);

    // Lots of overwrites (stale versions) plus a few keys that get deleted.
    for round in 0..50 {
        put(&mut db, "hot", &format!("round-{round}"));
        put(&mut db, "warm", &"w".repeat(120));
    }
    put(&mut db, "cold", &"c".repeat(120));
    db.delete(b"cold").expect("delete");

    let before = db.stats().expect("stats");
    assert!(before.stale_bytes > 0);

    let merged = db.merge().expect("merge");
    let after = db.stats().expect("stats");
    assert_eq!(after.stale_bytes, 0, "{after:?}");
    assert!(
        after.disk_bytes < before.disk_bytes,
        "{before:?} -> {after:?}"
    );
    assert_eq!(merged.live_keys, 2);
    assert_eq!(get(&mut db, "hot").as_deref(), Some("round-49"));
    assert_eq!(get(&mut db, "warm").as_deref(), Some(&*"w".repeat(120)));
    assert_eq!(get(&mut db, "cold"), None);

    // Writes keep working after the merge, then a reload exercises the hint files.
    put(&mut db, "post-merge", "yes");
    drop(db);

    let mut db = open(&dir, options);
    assert_eq!(get(&mut db, "hot").as_deref(), Some("round-49"));
    assert_eq!(get(&mut db, "post-merge").as_deref(), Some("yes"));
    assert_eq!(get(&mut db, "cold"), None);
}

#[test]
fn merge_writes_hint_files_for_immutable_files() {
    let dir = TempDir::new().expect("tempdir");
    let options = Options::default().with_max_file_size(512);
    let mut db = open(&dir, options);
    for index in 0..40 {
        put(&mut db, &format!("key:{index:03}"), &"v".repeat(64));
    }
    let merged = db.merge().expect("merge");
    assert!(merged.files_after > 1, "{merged:?}");

    let files = datafile::list_data_files(db.dir()).expect("list");
    let immutable = &files[..files.len() - 1];
    for (file_id, _) in immutable {
        let hint = datafile::hint_file_path(db.dir(), *file_id);
        assert!(hint.exists(), "missing {}", hint.display());
    }
    // The active file deliberately has no hint: it is scanned on startup anyway.
    let (active_id, _) = files.last().expect("active file");
    assert!(!datafile::hint_file_path(db.dir(), *active_id).exists());

    for index in 0..40 {
        assert!(
            get(&mut db, &format!("key:{index:03}")).is_some(),
            "key:{index:03} lost after merge"
        );
    }
}

#[test]
fn merge_with_no_live_keys_recreates_an_empty_active_file() {
    let dir = TempDir::new().expect("tempdir");
    let mut db = open(&dir, Options::default());
    put(&mut db, "gone", "value");
    db.delete(b"gone").expect("delete");

    let merged = db.merge().expect("merge");
    assert_eq!(merged.live_keys, 0);
    assert_eq!(db.stats().expect("stats").file_count, 1);
    assert_eq!(db.len(), 0);

    put(&mut db, "fresh", "value");
    assert_eq!(get(&mut db, "fresh").as_deref(), Some("value"));
    drop(db);

    let mut db = open(&dir, Options::default());
    assert_eq!(get(&mut db, "fresh").as_deref(), Some("value"));
    assert_eq!(get(&mut db, "gone"), None);
}

#[test]
fn only_one_process_can_hold_the_writer_lock() {
    let dir = TempDir::new().expect("tempdir");
    let _first = open(&dir, Options::default());
    let error = Bitcask::open(db_dir(&dir), Options::default()).expect_err("second open");
    assert!(matches!(error, Error::Locked(_)), "{error}");
}

#[test]
fn key_limits_are_enforced() {
    let dir = TempDir::new().expect("tempdir");
    let mut db = open(&dir, Options::default());
    assert!(matches!(db.put(b"", b"v"), Err(Error::EmptyKey)));
    let too_long = vec![b'k'; entry::MAX_KEY_SIZE + 1];
    assert!(matches!(
        db.put(&too_long, b"v"),
        Err(Error::KeyTooLarge { .. })
    ));
}

#[test]
fn leftover_merge_directory_is_discarded_on_open() {
    let dir = TempDir::new().expect("tempdir");
    {
        let mut db = open(&dir, Options::default());
        put(&mut db, "a", "1");
    }

    // Simulate an interrupted merge: a merge directory that never got swapped in.
    let merge_dir = datafile::merge_dir_path(&db_dir(&dir));
    fs::create_dir_all(&merge_dir).expect("create");
    fs::write(merge_dir.join("000999.data"), b"garbage").expect("write");

    let mut db = open(&dir, Options::default());
    assert_eq!(get(&mut db, "a").as_deref(), Some("1"));
    assert!(!merge_dir.exists(), "merge directory should be removed");
}

#[test]
fn interrupted_merge_output_is_recovered_on_open() {
    let options = Options::default();
    let dir = TempDir::new().expect("tempdir");
    {
        let mut db = open(&dir, options);
        put(&mut db, "keep", "old");
    }
    let (last_id, _) = datafile::list_data_files(&db_dir(&dir))
        .expect("list")
        .last()
        .cloned()
        .expect("one data file");

    // Simulate a merge that had written, synced and marked its output but died
    // before renaming it into place: the leftovers must be adopted, with the
    // higher file id winning, not dropped with the merge directory.
    let merge_dir = datafile::merge_dir_path(&db_dir(&dir));
    fs::create_dir_all(&merge_dir).expect("create merge dir");
    let recovered_id = last_id + 1;
    let mut bytes = entry::encode(1, b"keep", Some(b"new"));
    bytes.extend_from_slice(&entry::encode(1, b"extra", Some(b"value")));
    fs::write(datafile::data_file_path(&merge_dir, recovered_id), &bytes).expect("write");
    datafile::write_merge_marker(&db_dir(&dir)).expect("marker");

    let mut db = open(&dir, options);
    assert_eq!(get(&mut db, "keep").as_deref(), Some("new"));
    assert_eq!(get(&mut db, "extra").as_deref(), Some("value"));
    assert!(!merge_dir.exists(), "merge directory should be gone");
    assert_eq!(db.active_file_id(), recovered_id);
}

#[test]
fn directory_masquerading_as_a_data_file_is_ignored() {
    let dir = TempDir::new().expect("tempdir");
    {
        let mut db = open(&dir, Options::default());
        put(&mut db, "keep", "value");
    }

    // A directory whose name matches the data-file pattern must not be listed
    // (and must not blow up `open` with a confusing I/O error).
    fs::create_dir(datafile::data_file_path(&db_dir(&dir), 999)).expect("create decoy");

    let mut db = open(&dir, Options::default());
    assert_eq!(get(&mut db, "keep").as_deref(), Some("value"));
    assert_eq!(db.stats().expect("stats").file_count, 1);
}

#[test]
fn verify_reads_detects_a_corrupted_value() {
    let dir = TempDir::new().expect("tempdir");
    let options = Options::default().with_verify_reads(true);
    let mut db = open(&dir, options);
    put(&mut db, "key", "value");

    // Flip a bit inside the value bytes of the record that was just written:
    // the file is structurally unchanged, only the checksum now disagrees.
    let (_, active) = datafile::list_data_files(db.dir())
        .expect("list")
        .last()
        .cloned()
        .expect("active file");
    let mut bytes = fs::read(&active).expect("read");
    let last = bytes.len() - 1;
    bytes[last] ^= 0xff;
    fs::write(&active, &bytes).expect("write");

    let error = db.get(b"key").expect_err("verification must fail");
    assert!(matches!(error, Error::Corrupt { .. }), "{error}");
}

#[test]
fn fast_reads_return_stored_bytes_without_checking_the_crc() {
    let dir = TempDir::new().expect("tempdir");
    let mut db = open(&dir, Options::default());
    put(&mut db, "key", "value");

    let (_, active) = datafile::list_data_files(db.dir())
        .expect("list")
        .last()
        .cloned()
        .expect("active file");
    let mut bytes = fs::read(&active).expect("read");
    let last = bytes.len() - 1;
    // Flip one bit so the stored value stays valid UTF-8 for the assertion.
    bytes[last] ^= 0x01;
    fs::write(&active, &bytes).expect("write");

    // Documents the trade-off: without `verify_reads` the keydir is trusted and
    // the (now damaged) bytes are returned as-is.
    let value = get(&mut db, "key").expect("the fast path does not verify");
    assert_ne!(value, "value");
}

#[cfg(unix)]
#[test]
fn symlinked_data_file_is_still_read() {
    let dir = TempDir::new().expect("tempdir");
    let options = Options::default().with_max_file_size(128);
    {
        let mut db = open(&dir, options);
        for index in 0..3 {
            put(&mut db, &format!("key:{index}"), &"v".repeat(40));
        }
        assert!(db.stats().expect("stats").file_count > 1, "need rotation");
    }

    // Move the first segment aside and link it back: following the link is the
    // only difference between "missing data" and a correctly loaded store.
    let (first_id, first_path) = first_immutable(&dir);
    let moved = dir.path().join("moved.data");
    fs::rename(&first_path, &moved).expect("move aside");
    std::os::unix::fs::symlink(&moved, &first_path).expect("symlink");

    let mut db = open(&dir, options);
    for index in 0..3 {
        assert!(
            get(&mut db, &format!("key:{index}")).is_some(),
            "key:{index} lost behind file {first_id}"
        );
    }
}

#[test]
fn truncated_hint_file_falls_back_to_scanning() {
    let options = Options::default().with_max_file_size(512);
    let dir = TempDir::new().expect("tempdir");
    build_merged_db(&dir, options, 20);

    // A hint that only mentions its first record must not be trusted: the
    // loader has to notice the missing coverage and scan the data file.
    let (first_id, _) = first_immutable(&dir);
    let hint = datafile::hint_file_path(&db_dir(&dir), first_id);
    let bytes = fs::read(&hint).expect("read hint");
    assert!(bytes.len() > 23);
    fs::write(&hint, &bytes[..23]).expect("truncate hint");

    assert_all_keys(&dir, options, 20);
}

#[test]
fn corrupt_hint_file_falls_back_to_scanning() {
    let options = Options::default().with_max_file_size(512);
    let dir = TempDir::new().expect("tempdir");
    build_merged_db(&dir, options, 20);

    let (first_id, _) = first_immutable(&dir);
    let hint = datafile::hint_file_path(&db_dir(&dir), first_id);
    fs::write(&hint, [0xff; 30]).expect("corrupt hint");

    assert_all_keys(&dir, options, 20);
}

#[test]
fn merge_preserves_empty_values() {
    let options = Options::default().with_max_file_size(256);
    let dir = TempDir::new().expect("tempdir");
    let mut db = open(&dir, options);
    put(&mut db, "empty", "");
    for index in 0..10 {
        put(&mut db, &format!("filler:{index:03}"), &"v".repeat(60));
    }

    db.merge().expect("merge");
    assert_eq!(get(&mut db, "empty").as_deref(), Some(""));
    drop(db);

    // The reload also exercises a hint file whose first record has value_size 0.
    let mut db = open(&dir, options);
    assert_eq!(get(&mut db, "empty").as_deref(), Some(""));
    assert_eq!(db.len(), 11);
}

#[test]
fn merge_reports_superseded_files_it_cannot_remove() {
    let options = Options::default().with_max_file_size(512);
    let dir = TempDir::new().expect("tempdir");
    build_merged_db(&dir, options, 20);

    // Replace an old hint file with a directory: `remove_file` cannot delete it,
    // so pruning must fail — without losing data and without leaving the engine
    // in a broken state.
    let (first_id, _) = first_immutable(&dir);
    let hint = datafile::hint_file_path(&db_dir(&dir), first_id);
    fs::remove_file(&hint).expect("remove hint");
    fs::create_dir(&hint).expect("put a directory in its place");

    let mut db = open(&dir, options);
    let error = db.merge().expect_err("pruning must fail");
    assert!(matches!(error, Error::PruneFailed { .. }), "{error}");

    // The merge is committed even though the leftover file remains: all data is
    // readable and survives a reload.
    for index in 0..20 {
        let key = format!("key:{index:03}");
        assert!(get(&mut db, &key).is_some(), "{key} lost");
    }
    drop(db);
    assert_all_keys(&dir, options, 20);
}
