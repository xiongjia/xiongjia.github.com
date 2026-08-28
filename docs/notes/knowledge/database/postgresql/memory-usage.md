---
hide:
  - navigation
title: PostgreSQL 内存占用查看（Memory / Buffers / Connections）
tags:
  - knowledge
  - database
  - postgresql
  - memory
  - shared-buffers
  - connections
categories:
  - database
---

# PostgreSQL 内存占用查看（Memory / Buffers / Connections）

> PG 的内存分两个层次：**共享内存**（所有后端进程共用，主要是
> `shared_buffers` 里缓存的数据页）与**进程私有内存**（每个连接自己的
> `work_mem` 排序/哈希、临时表用的 `temp_buffers`、各类会话缓存）。
> 排查时先分清「共享」与「私有」，再看对应层的数据。本文覆盖：内存参数、
> 配置修改与持久化、共享内存实际占用、缓存命中率、临时表/临时文件
> （内存溢写的信号）、连接数。

## 1. 相关内存参数一览（先看配置）

```sql
SHOW shared_buffers;              -- 共享内存：数据页缓存
SHOW work_mem;                    -- 私有内存：单次排序/哈希
SHOW maintenance_work_mem;        -- 私有内存：VACUUM / CREATE INDEX 等
SHOW temp_buffers;                -- 会话私有：临时表缓存
SHOW max_connections;             -- 连接上限
SHOW superuser_reserved_connections; -- 预留给超级用户的连接数
```

或一次性从 `pg_settings` 查（`SHOW x` 只是它的语法糖）：

```sql
SELECT name, setting, unit, short_desc
FROM pg_settings
WHERE name IN ('shared_buffers', 'work_mem', 'maintenance_work_mem',
               'temp_buffers', 'max_connections', 'effective_cache_size');
```

参数含义：

| 参数                             | 属于             | 含义                                                                 |
| -------------------------------- | ---------------- | -------------------------------------------------------------------- |
| `shared_buffers`                 | 共享内存         | 数据页缓存大小（默认 128MB）。PG 专用机常见建议为物理内存的 ~25%     |
| `work_mem`                       | 私有（每操作）   | 单个排序/哈希操作可用内存上限（默认 4MB）                            |
| `maintenance_work_mem`           | 私有（维护进程） | VACUUM / CREATE INDEX / REINDEX 等维护操作内存（默认 64MB）          |
| `temp_buffers`                   | 私有（每会话）   | 本会话临时表（`pg_temp_*`）的缓存（默认 8MB）                        |
| `effective_cache_size`           | 仅规划器参考     | 告诉规划器操作系统缓存大概多大，用来选执行计划，**并不实际分配内存** |
| `max_connections`                | 连接上限         | 同时最大后端连接数                                                   |
| `superuser_reserved_connections` | 连接预留         | 普通用户占满连接后，给超级用户留的槽位（默认 3）                     |

> 上表默认值为 **PG 9.4+ 的默认**；9.3 及更早版本默认更小（如
> work_mem 1MB、maintenance_work_mem 16MB、shared_buffers 32MB）。
>
> ⚠️ `work_mem` 是**每个操作**的限额：一个查询里多个排序/哈希各自单独
> 计算，再乘以并发连接数，实际峰值可能远超「work_mem × 连接数」的直觉。
> 调它要谨慎，通常先看下面第 6 节有没有溢写再动手。

## 2. 修改内存配置

改法分三层，从轻到重：

```sql
-- ① 会话级：只影响当前会话，立即生效（适合试参数、临时调整）
SET work_mem = '128MB';
SET LOCAL work_mem = '128MB';   -- 事务结束自动恢复

-- ② 实例级：ALTER SYSTEM 写入 postgresql.auto.conf（需超级用户；优先级高于 postgresql.conf）
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM RESET work_mem;    -- 恢复默认
```

> ⚠️ `SET` 只对**当前会话**生效：连接断开/服务重启即失效，不会写入任何
> 配置文件，也不影响其他连接与今后新开的会话。要**持久生效**，用
> `ALTER SYSTEM`（或改 `postgresql.conf`）后 reload / 重启。
>
> ✅ 与之相反，`ALTER SYSTEM` 写入的 `postgresql.auto.conf` 在服务**每次
> 启动和 reload 时都会被读取**，因此**重启后依然生效**；同一参数若在
> `postgresql.conf` 里也配置了，以 auto.conf 为准（`pg_settings.source = 'override'` 即表示来自 auto.conf）。生效时机仍看 `context`：user 参数
> reload 即对新连接生效，postmaster 参数要重启才真正用上。
> `ALTER SYSTEM RESET` 只删除 auto.conf 中的该项，不碰 postgresql.conf。

三种方式小结：

| 修改方式               | 作用范围            | 重启后是否保留      | 生效时机                                     |
| ---------------------- | ------------------- | ------------------- | -------------------------------------------- |
| `SET`（会话级）        | 当前会话            | ❌ 否（断开即失效） | 立即，仅本会话                               |
| `ALTER SYSTEM`         | 实例级（auto.conf） | ✅ 是               | 按 context：user → reload；postmaster → 重启 |
| 编辑 `postgresql.conf` | 实例级              | ✅ 是               | 按 context：reload / 重启                    |

③ 直接编辑主配置文件 `postgresql.conf`（路径用 `SHOW config_file;` 查）。
云/托管实例一般通过控制台参数组或 `ALTER SYSTEM` 改。

生效方式：多数参数 `SELECT pg_reload_conf();` 即可热加载；但
`postmaster` 级参数必须重启服务。

### 哪些参数需要重启

```sql
SELECT name, setting, unit, context, pending_restart
FROM pg_settings
WHERE name IN ('shared_buffers', 'max_connections',
               'superuser_reserved_connections', 'work_mem',
               'maintenance_work_mem', 'temp_buffers', 'effective_cache_size');
```

`context` 与生效方式对照：

| `context`            | 生效方式                                         |
| -------------------- | ------------------------------------------------ |
| `postmaster`         | 必须重启服务                                     |
| `sighup`             | reload 即生效（当前进程重新读配置）              |
| `backend`            | reload 后仅**新连接**生效                        |
| `superuser` / `user` | 会话级可 `SET`；`ALTER SYSTEM` + reload 同样生效 |

本文涉及的参数归类：

| 参数                             | context    | 修改后如何生效      |
| -------------------------------- | ---------- | ------------------- |
| `shared_buffers`                 | postmaster | 重启                |
| `max_connections`                | postmaster | 重启                |
| `superuser_reserved_connections` | postmaster | 重启                |
| `work_mem`                       | user       | reload / 会话 `SET` |
| `maintenance_work_mem`           | user       | reload / 会话 `SET` |
| `temp_buffers`                   | user       | reload / 会话 `SET` |
| `effective_cache_size`           | user       | reload / 会话 `SET` |

### 完整修改流程

```sql
-- 例 1：work_mem 这类可热加载的参数
ALTER SYSTEM SET work_mem = '64MB';
SELECT pg_reload_conf();   -- 返回 true 表示已发出 reload 信号

-- 例 2：shared_buffers / max_connections 这类需要重启的
ALTER SYSTEM SET shared_buffers = '6GB';
ALTER SYSTEM SET max_connections = '300';
SELECT name, setting FROM pg_settings WHERE pending_restart;  -- 列出待重启才生效的参数（PG 9.5+）

-- 然后重启（方式因部署而异）
pg_ctl restart -D $PGDATA          -- 或 systemctl restart postgresql / 平台控制台
```

验证是否生效：

```sql
SHOW shared_buffers;
-- 或看来源：boot_val 默认值 / setting 当前值 / source 值从哪来
SELECT name, boot_val, setting, source, pending_restart
FROM pg_settings WHERE name IN ('shared_buffers', 'work_mem');
```

### 注意事项与常见建议

- **用数据说话再改**：先看第 4 节缓存命中率、第 6 节 `temp_files`，
  确定瓶颈是缓存偏小、溢写多还是连接打满，再决定改哪个参数。
- `work_mem` 是**每操作**限额，别随手设 1GB：实际峰值 ≈ 每查询排序数
  × 并发连接 × 每个 `work_mem`。从默认 4MB 逐步试，观察 `temp_files`
  是否下降。
- `max_connections` 增大**同时**会增大共享内存（锁、进程/连接数组按
  `max_connections` 预分配），与 `shared_buffers` 一起加时要算总账
  （可用第 3 节 `pg_shmem_allocations` 核实）。
- `superuser_reserved_connections` 必须小于 `max_connections`，预留
  槽位要一起规划。
- `maintenance_work_mem`：会话内临时调大对**本次** `VACUUM` /
  `CREATE INDEX` 有效；要影响 autovacuum worker（独立进程）必须改配置并
  reload。
- `effective_cache_size` 只影响执行计划估算、不实际分配内存，可约等于
  「OS 文件缓存 + shared_buffers」的估计值。
- 起步参考（非标准）：PG 专用机 `shared_buffers` ≈ 物理内存 25%；
  `work_mem` 常见 16–64MB；`maintenance_work_mem` 64MB 起、大维护临时调大。

## 3. 共享内存实际占用（pg_shmem_allocations）

`shared_buffers` 只是最大配置值，实际占用的共享内存看视图
`pg_shmem_allocations`（PG 13+，列：name / off / size / allocated_size）：

```sql
-- 按大小排序看每个共享内存模块
SELECT name, size, allocated_size
FROM pg_shmem_allocations
ORDER BY size DESC;

-- 共享内存总大小（所有行 size 之和，含 named / anonymous / 未用内存）
SELECT pg_size_pretty(sum(size)) AS total_shared
FROM pg_shmem_allocations;
```

> 共享内存由 `shared_buffers`（最大的一块）+ WAL 缓冲 + `max_connections`
> 相关的锁/进程信息等多块组成，所以实际映射的总量略大于
> `shared_buffers` 本身。

操作系统层侧面印证（Linux）：

```bash
df -h /dev/shm                # shared_memory_type=mmap（默认）时共享内存在 /dev/shm
ipcs -m                       # shared_memory_type=sysv 时看 System V 共享内存段
ps -eo pid,rss,cmd -C postgres --sort=-rss   # 各进程 RSS 排序
```

## 4. 缓存命中率（shared_buffers 是否够用）

按数据库看数据页缓存命中率：

```sql
SELECT datname,
       round(sum(blks_hit) * 100.0 / nullif(sum(blks_hit + blks_read), 0), 2) AS hit_rate_pct
FROM pg_stat_database
GROUP BY datname
ORDER BY hit_rate_pct;
```

长期低于 95–99% 说明缓存偏小或存在大量扫表（大表全表扫描会读入
大量页、把 shared_buffers 里的其他热点数据冲掉，导致整体命中率下降；
顺序扫描本身对缓存命中不敏感）。
此时先找大表并确认是否经常被全表扫描，判断该扩 `shared_buffers` 还是改
查询，而不是盲目加内存：

```sql
-- 被全表扫描最多的表（seq_scan 高 = 频繁扫全表）
SELECT schemaname, relname, seq_scan, seq_tup_read
FROM pg_stat_user_tables
ORDER BY seq_scan DESC
LIMIT 10;
```

> 找「哪些表最占空间」见 [磁盘占用查看](./disk-usage.md)。

## 5. 每个对象占多少 Buffer（pg_buffercache）

想精确知道「共享缓存里现在躺着哪些表/索引的数据」用扩展
`pg_buffercache`（PG 9.0+，需超级用户，一次性安装即可）：

```sql
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

-- 哪个表/索引占用了最多的缓存页
SELECT c.relname,
       count(*)             AS buffers,
       pg_size_pretty(count(*) * current_setting('block_size')::int) AS approx
FROM pg_buffercache b
JOIN pg_class c ON c.relfilenode = b.relfilenode
GROUP BY c.relname
ORDER BY buffers DESC
LIMIT 20;
```

> 它反映的是**当前缓存状态**，不是对象总大小；TOAST 表（`pg_toast_*`）
> 也会各自出现。`isdirty`、`pinning` 列自 9.5 起提供，可用于统计脏页
> （未落盘）：

```sql
SELECT count(*) AS dirty_buffers FROM pg_buffercache WHERE isdirty;
```

## 6. 临时表 / 临时文件（内存溢写信号）

**`temp_files > 0` 是「内存不够用了」最直接的信号**：排序/哈希所需内存
超过 `work_mem` 时，PG 会把中间结果溢写到磁盘临时文件：

```sql
SELECT datname,
       temp_files,
       pg_size_pretty(temp_bytes) AS temp_bytes
FROM pg_stat_database
ORDER BY temp_bytes DESC;
```

`temp_files` 持续增长 → 有查询在大排序/大哈希，且 `work_mem` 偏小，
调大 `work_mem` 的方法见第 2 节。
每次溢写还会被记录（`log_temp_files` 默认 -1 即关闭，0 表示记录所有，
正值 = KB 阈值）：

```sql
SHOW log_temp_files;
-- 建议设 0：ALTER SYSTEM SET log_temp_files = 0; 之后日志里搜 "temporary file"
```

临时表本身的占用（会话级 `temp_buffers`），汇总 `pg_temp%` schema：

```sql
SELECT n.nspname,
       pg_size_pretty(sum(pg_total_relation_size(c.oid))) AS total
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname LIKE 'pg_temp%'
GROUP BY n.nspname;
```

> `pg_temp_N` 是会话的临时 schema，会话退出即清空，所以只有在会话
> 存活期间能查到内容。

## 7. 连接数（Connection）

```sql
-- 当前连接数 vs 上限
SELECT count(*) AS current_conns FROM pg_stat_activity;
SHOW max_connections;

-- 按数据库 + 状态聚合，快速定位谁在占坑
SELECT datname, state, count(*)
FROM pg_stat_activity
GROUP BY datname, state
ORDER BY 1, 2;

-- 仅客户端连接（不含 autovacuum / background worker 等；PG 14+）
SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend';
```

`max_connections` 里有一小部分预留给超级用户
（`superuser_reserved_connections`，默认 3）：普通用户把连接占满后会报
`FATAL: sorry, too many clients already`，靠这 3 个槽位还能用超级用户
连进去处理。连接打满时的标准排查：

1. 按 `application_name` / `client_addr` / `state` 分组找谁在占连接
   （常见：连接池没释放、大量 `idle` / `idle in transaction`、监控或
   备份脚本）。
1. 定位「卡住」的连接与锁等待 → 见
   [活跃会话诊断（Active Sessions）](./active-sessions.md)。

## 8. 进程级 RSS（私有内存实况）

后端进程实际占用的物理内存（RSS）在操作系统层看：

```bash
ps -eo pid,rss,cmd --sort=-rss | grep 'postgres:' | head -20
```

进程私有内存大头通常是 `work_mem` 排序/哈希 + 会话缓存 + 扩展加载。
注意：**每个进程的 RSS 里都含一份共享内存的映射**，所以「各进程
RSS 之和」≠「shared_buffers + 私有内存之和」，别用 RSS 求和去反推
`shared_buffers`。

## 一句话总结

| 要看什么                  | 用什么                                                                            |
| ------------------------- | --------------------------------------------------------------------------------- |
| 参数配置                  | `SHOW shared_buffers / work_mem / temp_buffers / max_connections`                 |
| 修改配置 / 生效方式       | `ALTER SYSTEM` + `pg_reload_conf()` / 重启；用 `context` / `pending_restart` 判断 |
| 共享内存实际占用          | `pg_shmem_allocations`（PG 13+；总量用 `sum(size)`）                              |
| 缓存命中率                | `pg_stat_database` 的 `blks_hit` / `blks_read`                                    |
| 哪些对象在缓存里          | `pg_buffercache` 扩展                                                             |
| 排序/哈希溢写（内存不够） | `pg_stat_database` 的 `temp_files` / `temp_bytes` + `log_temp_files`              |
| 临时表占用                | `pg_temp%` schema 汇总                                                            |
| 连接数 / 上限 / 预留      | `pg_stat_activity` + `max_connections` / `superuser_reserved_connections`         |
| 进程实际 RSS              | 操作系统 `ps -o rss` 排序                                                         |
