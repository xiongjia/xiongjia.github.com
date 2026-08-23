---
hide:
  - navigation
title: PostgreSQL WAL 与 LSN
tags:
  - knowledge
  - database
  - postgresql
  - wal
  - lsn
  - replication
categories:
  - database
---

# PostgreSQL WAL 与 LSN

> 适用：PG 10+（`pg_current_wal_lsn()` / `pg_walfile_name()` 等新命名，
> 9.x 时代为 `pg_current_xlog_location()` / `pg_xlogfile_name()`）。

## WAL 是什么

**WAL（Write-Ahead Log，预写日志）** 是 PG 保证崩溃恢复（redo）与
流式复制（standby 回放）的基础：**任何修改先写 WAL，再落数据文件**。
崩溃后 PG 从最后一个 checkpoint 开始重放 WAL 即可恢复。

WAL 落盘时机由 `wal_level`、`synchronous_commit` 等控制；
归档 / 复制的可靠性底线是「WAL 已写到哪」。

## LSN 是什么

**LSN（Log Sequence Number）** 是 WAL 日志中的位置指针，64 位整数，
显示为 `0/16B3748` 这种形式：

- 前半部分是段内偏移所在段的高位，后半部分是低位；可理解为「在 WAL 流
  中的字节位置」。
- 单调递增；两个 LSN 相减即两个位置之间的 **WAL 字节数**。

## 常用查看命令

### 当前位置

```sql
-- 当前 WAL 写入位置（最常用）
SELECT pg_current_wal_lsn();            -- e.g. 0/16B3748

-- PG 13+ 区分「insert」与「flush」位置
SELECT pg_current_wal_insert_lsn(), pg_current_wal_lsn();

-- 备库：回放位置 + 是否在恢复中
SELECT pg_is_in_recovery(), pg_last_wal_replay_lsn();
```

### 位置差（字节数）

```sql
SELECT pg_wal_lsn_diff('0/16B3748', '0/16B3000');   -- 两个位置间 WAL 字节数
```

### LSN → 文件名

```sql
-- 当前 WAL 段文件名（24 位 hex：8 位时间线 + 16 位段号）
SELECT pg_walfile_name(pg_current_wal_lsn());

-- 列出 pg_wal 目录下的所有 WAL 文件及大小
SELECT * FROM pg_ls_waldir();
```

> 默认每段 16MB（`SHOW wal_segment_size;`，PG 11+）。`pg_ls_waldir()`
> 需要 superuser 或 `pg_monitor` 角色。

### 复制进度（主库视角）

```sql
SELECT application_name,
       client_addr,
       sent_lsn,
       write_lsn,
       flush_lsn,
       replay_lsn,
       write_lag,   -- PG 10+，主备之间的实际延迟
       flush_lag,
       replay_lag
FROM pg_stat_replication;
```

- `sent_lsn`：已发给备库 / 已写入槽位
- `write_lsn` / `flush_lsn`：备库写盘 / flush 位置
- `replay_lsn`：备库实际回放到的位置（落后越多，主备延迟越大）

### 复制槽（slot）水位

```sql
SELECT slot_name, slot_type, restart_lsn,
       confirmed_flush_lsn   -- 逻辑复制槽，PG 10+
FROM pg_replication_slots;
```

- `restart_lsn`：WAL 至少保留到这个位置（防止 WAL 被清理导致备库断流）
- 物理复制槽的 `restart_lsn` 如果长期不推进，pg_wal 会无限膨胀 ——
  这是磁盘爆满的常见原因。

## 常见用途

- **估算主备延迟**：`pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)`，
  或直接看 `*_lag` 列。
- **确认 WAL 归档进度**：配合 `archive_command` / `pg_stat_archiver`
  判断归档是否跟上。
- **备份基线**：`pg_basebackup` / 第三方备份工具都会记录起始 LSN，
  恢复时从该 LSN 起应用 WAL。
- **查 PG 启动后的检查点位置**：`pg_controldata` 输出的
  `Latest checkpoint location`。
