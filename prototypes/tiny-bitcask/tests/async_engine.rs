//! Tests for the async wrapper: concurrent access, merge and the async backup.

use tempfile::TempDir;
use tiny_bitcask::async_engine::AsyncBitcask;
use tiny_bitcask::engine::Bitcask;
use tiny_bitcask::{datafile, Options};

async fn open(dir: &TempDir) -> AsyncBitcask {
    AsyncBitcask::open(dir.path().join("db"), Options::default())
        .await
        .expect("open")
}

#[tokio::test]
async fn concurrent_puts_and_gets_share_one_engine() {
    let dir = TempDir::new().expect("tempdir");
    let db = open(&dir).await;

    let mut tasks = Vec::new();
    for task in 0..4u32 {
        let db = db.clone();
        tasks.push(tokio::spawn(async move {
            for index in 0..50u32 {
                let key = format!("task:{task}:{index:03}").into_bytes();
                let value = format!("value-{index}").into_bytes();
                db.put(key, value).await.expect("put");
            }
        }));
    }
    for task in tasks {
        task.await.expect("join");
    }

    assert_eq!(db.len().await.expect("len"), 200);
    for task in 0..4u32 {
        for index in 0..50u32 {
            let key = format!("task:{task}:{index:03}").into_bytes();
            let value = db.get(key).await.expect("get");
            assert_eq!(value, Some(format!("value-{index}").into_bytes()));
        }
    }

    let deleted = db.delete(b"task:0:000".to_vec()).await.expect("delete");
    assert!(deleted);
    assert_eq!(db.get(b"task:0:000".to_vec()).await.expect("get"), None);
    assert_eq!(db.len().await.expect("len"), 199);
}

#[tokio::test]
async fn merge_and_backup_are_usable_from_the_copied_directory() {
    let dir = TempDir::new().expect("tempdir");
    let db = AsyncBitcask::open(
        dir.path().join("db"),
        Options::default().with_max_file_size(1024),
    )
    .await
    .expect("open");

    // 12 live records of 200 bytes: enough that the merge output needs several
    // files (and therefore hint files), plus plenty of stale versions.
    for index in 0..12u32 {
        db.put(format!("stable:{index:02}").into_bytes(), vec![b'v'; 200])
            .await
            .expect("put");
    }
    for round in 0..40u32 {
        db.put(b"hot".to_vec(), format!("round-{round}").into_bytes())
            .await
            .expect("put");
    }
    db.delete(b"stable:11".to_vec()).await.expect("delete");

    let before = db.stats().await.expect("stats");
    assert!(before.stale_bytes > 0);

    let merged = db.merge().await.expect("merge");
    let after = db.stats().await.expect("stats");
    assert_eq!(after.stale_bytes, 0);
    assert!(after.disk_bytes < before.disk_bytes);
    assert_eq!(merged.live_keys, 12);
    assert!(merged.files_after > 1, "{merged:?}");
    assert_eq!(
        db.get(b"hot".to_vec()).await.expect("get"),
        Some(b"round-39".to_vec())
    );

    // tokio::fs copy of every data and hint file.
    let backup = dir.path().join("backup");
    let copied = db.backup_to(&backup).await.expect("backup");
    assert!(copied > 0);
    assert_eq!(
        datafile::list_data_files(&backup).expect("list").len(),
        after.file_count as usize
    );
    let hints = std::fs::read_dir(&backup)
        .expect("read_dir")
        .filter(|entry| {
            entry
                .as_ref()
                .is_ok_and(|entry| entry.path().extension().is_some_and(|ext| ext == "hint"))
        })
        .count();
    assert!(hints >= 1, "hint files should be copied too");
    // The staging directory used to place files atomically is cleaned up, and
    // the completion marker was written as the last step.
    assert!(
        !backup.with_file_name(".backup.partial").exists(),
        "staging directory should be removed"
    );
    let marker = std::fs::read_to_string(datafile::backup_marker_path(&backup))
        .expect("completion marker should exist");
    assert!(
        marker.contains("bytes=") && marker.starts_with("files="),
        "unexpected marker contents: {marker:?}"
    );

    // The copy is a real database: open it with the synchronous engine.
    let mut restored = Bitcask::open(&backup, Options::default()).expect("open backup");
    assert_eq!(
        restored.get(b"hot").expect("get").as_deref(),
        Some(&b"round-39"[..])
    );
    assert_eq!(
        restored.get(b"stable:00").expect("get").as_deref(),
        Some(&vec![b'v'; 200][..])
    );
    assert_eq!(restored.get(b"stable:11").expect("get"), None);
}

#[tokio::test]
async fn sequential_and_concurrent_writes_do_not_lose_keys() {
    let dir = TempDir::new().expect("tempdir");
    let db = open(&dir).await;

    for index in 0..200u32 {
        db.put(format!("seq:{index:04}").into_bytes(), b"seq".to_vec())
            .await
            .expect("put");
    }

    let mut tasks = Vec::new();
    for task in 0..8u32 {
        let db = db.clone();
        tasks.push(tokio::spawn(async move {
            for index in 0..100u32 {
                db.put(
                    format!("par:{task}:{index:04}").into_bytes(),
                    b"par".to_vec(),
                )
                .await
                .expect("put");
            }
        }));
    }
    for task in tasks {
        task.await.expect("join");
    }

    assert_eq!(db.len().await.expect("len"), 1000);
    assert_eq!(db.keys().await.expect("keys").len(), 1000);
}
