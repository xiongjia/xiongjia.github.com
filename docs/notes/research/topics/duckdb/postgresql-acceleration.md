---
hide:
  - navigation
title: PostgreSQL 数据用 DuckDB 加速查询
tags:
  - research
  - tech
  - duckdb
  - postgresql
  - database
categories:
  - dev
---

# :material-speedometer: PostgreSQL 数据用 DuckDB 加速查询

> **本页目的：** 原始数据在 PostgreSQL 里，如何用 DuckDB 加速**分析型查询**
> （多表 JOIN + 聚合 + 窗口函数）。两条路径：`postgres_scanner` 直连、
> 导出 Parquet 本地查询。附本机实测基准对比。
>
> 本页是 DuckDB 实战系列第 3 篇，数据源见 [模拟数据](./mock-data.md)。
> 实验环境：MacBook（arm64）+ Docker 内 PostgreSQL 18.4，数据为
> 100 万订单 + 10 万客户（`demo` schema，与 DuckDB 完全一致）。

## 1. 思路：PG 扛 OLTP，DuckDB 扛 OLAP

PostgreSQL 是 **OLTP** 数据库（行存、事务、点查快）；分析型查询要扫全表 +
大 JOIN + 聚合，行存 + 网络往返都很吃亏。DuckDB 是进程内 **OLAP** 引擎
（列存、向量化、零网络开销），适合分析负载。

常见组合：PG 继续提供在线服务，分析/报表查询交给 DuckDB。

## 2. 方案 A：postgres_scanner 直连

不复制数据，DuckDB 直接连 PG（走 PG 的线协议）：

```sql
INSTALL postgres_scanner; LOAD postgres_scanner;

-- 连接串按你的 PG 实例替换（user / password / host / port / dbname）
ATTACH 'dbname=devdb user=dev password=dev host=127.0.0.1 port=5433'
       AS pg (TYPE postgres);

-- 像本地表一样查询
SELECT count(*) FROM pg.demo.orders WHERE order_date >= DATE '2026-06-01';
```

**验证下推**：WHERE 条件会推到 PG 执行，只把过滤后的行拉回来。
`EXPLAIN` 看计划，`POSTGRES_SCAN` 节点里能看到 `Filters`：

```
┌─────────────┴─────────────┐
│       POSTGRES_SCAN       │
│       Table: orders       │
│          Filters:         │
│ order_date>='2026-06-01': │
│           :DATE           │
│       status='paid'       │
└───────────────────────────┘
```

**postgres_scanner 也支持写回**（本机实测可行）：用 DuckDB 生成的数据
`CREATE OR REPLACE TABLE pg.demo.orders AS SELECT * FROM orders;`
一次性把 100 万行写入 PG，保证两库数据一致（本实验就是用这种方式造的数据）。

> **注意：** 直连模式下 JOIN 在 DuckDB 侧做，大表数据还是要经网络传输，
> 提速有限（见基准）。适合**临时/adhoc** 查询，不适合高频分析。

## 3. 方案 B：导出 Parquet（推荐生产路径）

把 PG 表**一次性导出**为 Parquet，之后分析完全本地化：

```sql
LOAD postgres_scanner;
-- 连接串同方案 A（替换为实际 user/password/host/port/dbname）
ATTACH 'dbname=devdb user=dev password=dev host=127.0.0.1 port=5433'
       AS pg (TYPE postgres);

COPY pg.demo.orders TO 'parquet/orders.parquet' (FORMAT PARQUET);
```

本机实测：**100 万行导出耗时约 0.5 秒**，产出 14 MB 的 parquet 文件。

之后查询与 PG 完全解耦，零网络开销：

```sql
SELECT city, count(*) AS n, round(sum(o.amount), 0) AS amt
FROM 'parquet/orders.parquet' o
JOIN 'parquet/customers.parquet' c ON o.customer_id = c.id
WHERE o.order_date >= DATE '2025-08-01'
GROUP BY city ORDER BY amt DESC LIMIT 5;
```

> **同步链路（可选）：** 定时任务（cron / CI）定期把 PG 变更表重新导出
> （增量可用 `WHERE updated_at > last_sync`），DuckDB 侧只读 parquet，
> 即可长期为报表提供高速查询，且不影响 PG 的在线负载。

## 4. 基准对比（本机实测）

同一分析查询（orders JOIN customers，近一年按月/城市聚合 + 排序）：

| 执行方式                           | 耗时    | 相对 PG  |
| ---------------------------------- | ------- | -------- |
| PostgreSQL 直接执行                | 269.7ms | 1.0x     |
| DuckDB 直连 PG（postgres_scanner） | 150ms   | ~1.8x    |
| DuckDB 查本地 Parquet              | 7.6ms   | **~35x** |

结论：

- **直连模式**只快 1.8 倍 —— 瓶颈是网络传输 + PG 侧扫描，DuckDB 的
  向量化/列存优势发挥不出来；
- **Parquet 模式**快 35 倍 —— 数据本地化后，列存 + 向量化 + 无网络
  开销全部生效；
- **结果一致**：PG 与 DuckDB（Parquet）两端核对相同（本实验：78 个分组、
  总额 259,418,325.99）；直连模式数据同源，无差异；

> PG 侧实测没建索引，计划是并行 Seq Scan + 外部排序；对分析查询而言
> 索引本来也帮不上大忙。数据量越大、查询越重，Parquet 路径优势越明显。

## 5. 实践建议

1. **在线服务** → 继续用 PG（事务、点查、写入）；
1. **分析/报表** → 导出 Parquet 后用 DuckDB 查询，或直连模式做临时探索；
1. 数据一致性 → 定时增量导出；只读分析永不写回 PG；
1. 数据量更大时 → parquet 可放对象存储（R2/S3）配合 `httpfs` 扩展。

## 6. 参考链接

| 资源                   | 链接                                                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------ |
| DuckDB Postgres 扩展   | [https://duckdb.org/docs/stable/core_extensions/postgres](https://duckdb.org/docs/stable/core_extensions/postgres) |
| Parquet 扩展           | [https://duckdb.org/docs/stable/core_extensions/parquet](https://duckdb.org/docs/stable/core_extensions/parquet)   |
| httpfs（远程对象存储） | [https://duckdb.org/docs/stable/core_extensions/httpfs](https://duckdb.org/docs/stable/core_extensions/httpfs)     |

→ 返回目录：[DuckDB 实战研究](./index.md)
