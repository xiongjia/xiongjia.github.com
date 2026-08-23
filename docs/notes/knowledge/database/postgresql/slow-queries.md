---
hide:
  - navigation
title: PostgreSQL 查看慢查询（Slow Query）
tags:
  - knowledge
  - database
  - postgresql
  - slow-queries
  - troubleshooting
categories:
  - database
---

# PostgreSQL 查看慢查询（Slow Query）

> 慢查询有两个观察维度：**日志侧**（事后翻日志，靠 `log_min_duration_statement`
> / `auto_explain` 记录）和**实时侧**（看正在跑/累计跑的 SQL，靠
> `pg_stat_activity` / `pg_stat_statements`）。

## 1. 日志侧：记录慢查询

### `log_min_duration_statement`（最基础）

在 `postgresql.conf` 中设置，超过该毫秒数的语句会连同耗时写入日志：

```ini
log_min_duration_statement = 1000   # 记录执行超过 1s 的语句
log_duration = off                  # 保持 off，避免给每条语句都打日志
```

- 单位毫秒；设 `0` 记录所有语句（日志量会很大，一般不用）
- 改后需 `reload`（`pg_ctl reload` / `SELECT pg_reload_conf();`），无需重启
- 效果：日志里出现
  `duration: 1234.567 ms statement: SELECT ...`，配合
  `log_line_prefix` 里的 `%m %u %d`（时间/用户/库）定位来源

### `auto_explain`（记录慢查询的执行计划）

比裸日志更进一步：自动把慢查询的 `EXPLAIN` 计划也写进日志，方便事后看
计划是否合理：

```ini
shared_preload_libraries = 'auto_explain'
auto_explain.log_min_duration = 1000    # 超过 1s 的语句记录计划
auto_explain.log_analyze = on           # 附带真实执行统计（开销更高）
```

> `shared_preload_libraries` 需要**重启**才生效（与 `log_min_duration_statement`
> 的 reload 不同）。

## 2. 实时侧：正在跑 / 累计的慢查询

### `pg_stat_activity`（当前正在执行的）

```sql
SELECT pid, usename, now() - query_start AS age,
       state, wait_event_type, left(query, 200) AS query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start
LIMIT 20;
```

看到 `age` 很大且 `state = 'active'` 的，就是**当下**的慢查询（详情见
[活跃会话诊断](./active-sessions.md)）。

### `pg_stat_statements`（累计统计，推荐）

记录每条 SQL 的调用次数、总耗时、平均耗时等，是「反复出现的慢 SQL」
的标准工具：

```sql
-- 按累计执行时间排名
SELECT calls,
       round(total_exec_time / 1000) AS total_ms,
       round(mean_exec_time / 1000)  AS mean_ms,
       round(max_exec_time / 1000)   AS max_ms,
       left(query, 200)              AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 或按平均耗时排名（少而慢的查询）
SELECT calls,
       round(mean_exec_time / 1000)  AS mean_ms,
       round(total_exec_time / 1000) AS total_ms,
       left(query, 200)              AS query
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

启用步骤：

1. `postgresql.conf` 加 `shared_preload_libraries = 'pg_stat_statements'`
   → 重启
1. `CREATE EXTENSION pg_stat_statements;`
1. `pg_stat_statements_reset();` 可清空累计值重新观察（PG 14+ 无参形式；
   PG 9.2–13 需 `pg_stat_statements_reset(0,0,0);`）

> 版本差异：PG 13+ 列名为 `total_exec_time` / `mean_exec_time` /
> `max_exec_time`（单位毫秒）；9.x–12 为 `total_time` / `mean_time` /
> `max_time`。PG 15+ 默认 `compute_query_id`，可与 `pg_stat_activity.query_id`
> 对应到同一条查询。

## 3. 定位到具体查询后

- 对嫌疑 SQL 执行 `EXPLAIN (ANALYZE, BUFFERS)`，看扫描方式（Seq Scan vs
  Index Scan）、rows 估算偏差、Buffer 用量
- 结合 `pg_stat_user_indexes` 看是否有该用的索引没用上（`idx_scan = 0`）
- 若慢的是写入/锁等待场景，参考[活跃会话诊断](./active-sessions.md)的
  锁等待排查点

## 一句话总结

| 场景              | 用什么                                                         |
| ----------------- | -------------------------------------------------------------- |
| 事后翻日志        | `log_min_duration_statement`（耗时）→ `auto_explain`（+ 计划） |
| 现在正在跑的      | `pg_stat_activity`                                             |
| 反复出现/累计统计 | `pg_stat_statements`（先装扩展）                               |
