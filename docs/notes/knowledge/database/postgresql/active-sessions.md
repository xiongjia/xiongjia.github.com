---
hide:
  - navigation
title: PostgreSQL 活跃会话诊断（Active Sessions）
tags:
  - knowledge
  - database
  - postgresql
  - active-sessions
  - troubleshooting
categories:
  - database
---

# PostgreSQL 活跃会话诊断（Active Sessions）

> 适用：PG 9.6+（`pg_stat_activity` 的 `wait_event_type` / `wait_event`
> 列自 9.6 起，`query_id` 列自 14 起，`backend_type` 列自 14 起）。

「PG 卡了 / CPU 高」时第一步永远是看**当前会话在干什么**。核心工具是
`pg_stat_activity` 视图。

## 查看当前活跃 Session

```sql
SELECT pid,
       usename,
       application_name,
       client_addr,
       state,
       wait_event_type,
       wait_event,
       now() - query_start AS query_age,
       left(query, 200)    AS query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start;
```

### 关键列含义

| 列                | 含义                                                                                                                  |
| ----------------- | --------------------------------------------------------------------------------------------------------------------- |
| `pid`             | 后端进程 ID，可配合 `pg_terminate_backend(pid)` 终止                                                                  |
| `state`           | `active` 正在执行 / `idle` 空闲 / `idle in transaction` 事务内空闲 / `idle in transaction (aborted)` 事务已失败未回滚 |
| `wait_event_type` | 等待类别：`Lock` 锁等待、`LWLock` 轻量锁、`IO` 磁盘 IO、`CPU` 正在 CPU 上执行、`Client` 等客户端                      |
| `wait_event`      | 具体等待点（如 `tuple`、`relation`、`WALWrite` 等）                                                                   |
| `query_age`       | 当前查询已执行时长，从 `query_start` 计算                                                                             |
| `query_id`        | PG 14+ 的查询指纹，可与 `pg_stat_statements` 关联（PG 15+ 默认开启计算）                                              |
| `backend_type`    | PG 14+ 的后端类型（`client backend` / `autovacuum worker` 等）                                                        |

> `state = 'idle in transaction'` 是常见的「卡住」元凶：事务开着没提交，
> 占着连接和锁；`idle in transaction (aborted)` 说明事务已报错但没回滚，
> 同样要处理。

## CPU 高占用定位流程

1. **先看有没有进程在 CPU 上跑**（PG 13+ 才有 `wait_event_type = 'CPU'`）：

   ```sql
   SELECT pid, now() - query_start AS age, left(query, 150) AS query
   FROM pg_stat_activity
   WHERE state = 'active'
     AND wait_event_type = 'CPU'
   ORDER BY query_start;
   ```

1. **看谁的查询跑了最久**：

   ```sql
   SELECT pid, usename, now() - query_start AS age,
          wait_event_type, wait_event, left(query, 200) AS query
   FROM pg_stat_activity
   WHERE state = 'active' AND pid <> pg_backend_pid()
   ORDER BY query_start
   LIMIT 20;
   ```

1. **如果是反复出现的同一条 SQL**，用 `pg_stat_statements` 按累计 CPU /
   执行时间排名（需先 `CREATE EXTENSION pg_stat_statements`，PG 13+ 才有
   `total_exec_time` / `mean_exec_time`，9.x–12 为 `total_time` / `mean_time`）：

   ```sql
   SELECT calls,
          round(total_exec_time / 1000) AS total_ms,
          round(mean_exec_time / 1000)  AS mean_ms,
          left(query, 200)              AS query
   FROM pg_stat_statements
   ORDER BY total_exec_time DESC
   LIMIT 10;
   ```

1. **对嫌疑 SQL 做 `EXPLAIN (ANALYZE, BUFFERS)`**，看计划是否合理、是否
   触发大量 Buffer/排序/嵌套循环。

## 终止 / 取消会话

```sql
-- 取消当前正在执行的查询（进程保留，适合误跑的大查询）
SELECT pg_cancel_backend(pid);

-- 强制终止整个后端进程（会断开连接，事务回滚；慎用）
SELECT pg_terminate_backend(pid);
```

## 相关排查点

- **锁等待**：`wait_event_type = 'Lock'` + `pg_locks` / `pg_blocking_pids(pid)`
  查是谁堵住了谁。
- **autovacuum / 后台进程占资源**：过滤 `backend_type`（PG 14+）或
  `backend_start` 很久的 `autovacuum worker`。
- **连接数打满**：`SELECT count(*) FROM pg_stat_activity` vs `SHOW max_connections;`，
  配合 `pg_stat_activity` 看是否大量 `idle` 连接占坑。
