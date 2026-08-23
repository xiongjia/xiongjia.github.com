---
hide:
  - navigation
title: PostgreSQL 磁盘占用查看（Table Size / Datafile）
tags:
  - knowledge
  - database
  - postgresql
  - disk-usage
  - table-sizes
categories:
  - database
---

# PostgreSQL 磁盘占用查看（Table Size / Datafile）

> PG 的空间统计函数都返回**字节数**，配合 `pg_size_pretty()` 转成
> 人类可读格式（KB / MB / GB）。表主体文件直接读文件大小，TOAST /
> 索引部分基于 `pg_class.relpages` 统计估算，`VACUUM` / `ANALYZE` 后
> 数字更接近实际。

## 1. 哪个表最占空间（最常用）

```sql
SELECT schemaname,
       relname,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;
```

> `pg_total_relation_size` = 表主体 + TOAST + **所有索引**，
> 即这个表真正占用的磁盘总量。

## 2. 数据库级别

```sql
-- 当前数据库
SELECT pg_size_pretty(pg_database_size(current_database()));

-- 所有数据库排序
SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size
FROM pg_database
ORDER BY pg_database_size(datname) DESC;
```

## 3. 单表拆解：表 / TOAST / 索引各占多少

> **TOAST 是什么**：TOAST = **The Oversized-Attribute Storage Technique**
> （超大属性存储技术）。PG 的行默认不超过一个页面（8KB），当某个字段值
> 太大时（大 TEXT / BYTEA / 超长 varchar），PG 会先**压缩**，若仍放不下则
> **拆分**到独立的 TOAST 表（`pg_toast_*`），原表只留一个指针。
> 因此大字段数据大多躺在 TOAST 表里，看空间时**必须**把 TOAST 算进去
> （`pg_table_size` / `pg_total_relation_size` 已包含），否则会严重低估。
> 存储策略可调：`ALTER TABLE ... SET STORAGE (EXTENDED / EXTERNAL / MAIN / PLAIN)`，控制「先压缩还是直接外置」。

```sql
SELECT relname,
       pg_size_pretty(pg_relation_size(relid))  AS table_only,   -- 仅表主体
       pg_size_pretty(pg_table_size(relid))     AS with_toast,   -- 表 + TOAST
       pg_size_pretty(pg_indexes_size(relid))   AS indexes,      -- 该表全部索引
       pg_size_pretty(pg_total_relation_size(relid)) AS total
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

某个表最占空间的**单个索引**（表名不在默认 schema 时用
`schema.table` 限定）：

```sql
SELECT c.relname AS index_name,
       pg_size_pretty(pg_relation_size(c.oid)) AS size
FROM pg_class c
JOIN pg_index i ON i.indexrelid = c.oid
WHERE i.indrelid = 'your_table'::regclass
ORDER BY pg_relation_size(c.oid) DESC;
```

## 4. 按 Schema 汇总

```sql
SELECT schemaname,
       pg_size_pretty(sum(pg_total_relation_size(relid))) AS total
FROM pg_stat_user_tables
GROUP BY schemaname
ORDER BY sum(pg_total_relation_size(relid)) DESC;
```

## 5. 数据文件层面（Datafile）

每个表/索引在 `$PGDATA/base/<数据库OID>/` 下对应一个
`<relfilenode>` 文件；**超过 1GB 会自动分段**为 `.1`、`.2`……

```sql
-- 表对应的数据文件路径（相对 $PGDATA）
SELECT pg_relation_filepath('your_table');
-- e.g. base/16384/16407
```

```bash
# 在服务器上直接看（$PGDATA 通常需要 postgres 用户权限）
ls -lh $PGDATA/base/16384/16407*      # 含 .1 .2 分段
du -sh $PGDATA/base/16384/            # 该数据库目录总大小
```

> 数据库 OID：`SELECT oid, datname FROM pg_database;`
> 表的 relfilenode：`SELECT relfilenode FROM pg_class WHERE oid = 'your_table'::regclass;`
> 注意 `VACUUM FULL` / `CLUSTER` / `REINDEX` 会**改变 relfilenode**（旧文件被
> 替换删除），所以文件名不是稳定的。

## 6. 空间大 ≠ 数据多：表膨胀（Bloat）

空间占用异常大的常见原因是**膨胀**：UPDATE/DELETE 留下的死元组没有被
及时回收，表文件里塞满了「已删除但还占着位置」的数据。

- `VACUUM`：回收死元组空间（块内部复用，**文件大小不变**，但后续写入可复用）
- `VACUUM FULL`：重写整表，**实际缩小文件**（会锁表、耗时，建议低峰执行）
- 排查思路：先 `SELECT relname, n_dead_tup FROM pg_stat_user_tables ORDER BY n_dead_tup DESC;` 看死元组数量，再决定是否 FULL

## 一句话总结

| 要看什么                 | 用什么                                                   |
| ------------------------ | -------------------------------------------------------- |
| 哪个表最占空间（含索引） | `pg_stat_user_tables` + `pg_total_relation_size` 排序    |
| 数据库总大小             | `pg_database_size(datname)`                              |
| 表 / TOAST / 索引拆解    | `pg_relation_size` / `pg_table_size` / `pg_indexes_size` |
| 数据文件实际位置 / 大小  | `pg_relation_filepath()` + 服务器 `ls -lh` / `du`        |
| 表很大但可能是膨胀       | `n_dead_tup` 排查 → `VACUUM FULL` 回收                   |
