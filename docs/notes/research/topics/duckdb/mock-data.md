---
hide:
  - navigation
title: DuckDB 模拟数据
tags:
  - research
  - tech
  - duckdb
  - database
categories:
  - dev
---

# :material-database-search: 模拟数据

> **本页目的：** 用纯 SQL 构造**贴近真实分析场景**的模拟数据 —— 不用写 Python 循环，
> 全部在 DuckDB 里生成。产物（表 + Parquet）同时是
> [PostgreSQL 加速查询](./postgresql-acceleration.md) 实验的数据源。
>
> 本页是 DuckDB 实战系列第 2 篇，上一篇见 [环境与基本使用](./basic-usage.md)。

## 1. 内置生成器

`generate_series` 生成序号，`random()` 生成随机数，`md5()` 造假字符串：

```sql
-- 序号（注意：generate_series 返回 BIGINT，DATE 加法只接受 INTEGER，需显式转）
SELECT i, i*i AS square FROM generate_series(1, 5) t(i);
SELECT DATE '2026-01-01' + i::INTEGER AS d FROM generate_series(0, 4) t(i);

-- 随机值与假 hash
SELECT i, md5(random()::varchar) AS fake_hash FROM generate_series(1, 3) t(i);
```

> ⚠️ **坑：** `DATE + i`（i 来自 `generate_series`）报错
> `No function matches ... '+(DATE, BIGINT)'` —— `generate_series` 返回 **BIGINT**，
> 而 DATE 加法只接受 INTEGER，需要 `i::INTEGER`。这是本页生成脚本里最容易踩的错。

## 2. 迷你电商数仓（纯 SQL 生成）

一套 4 张表的订单模型，行数目标：10 万客户 / 100 万订单 / 200 万明细，
订单日期随机分布在最近 2 年：

```sql
-- 客户：id、姓名、城市、注册日期
CREATE TABLE customers AS
SELECT
  i AS id,
  '客户' || i AS name,
  (array['上海','北京','深圳','广州','杭州','成都'])[1 + (i % 6)] AS city,
  DATE '2024-08-11' + CAST(i % 730 AS INTEGER) AS signup_date
FROM generate_series(1, 100000) t(i);

-- 商品：id、名称、分类、价格
CREATE TABLE products AS
SELECT
  i AS id,
  '产品' || i AS name,
  (array['数码','家电','服饰','食品','图书'])[1 + (i % 5)] AS category,
  round(10 + (i % 900) * 0.1, 2) AS price
FROM generate_series(1, 1000) t(i);

-- 订单：id、客户、下单日期（随机 2 年）、金额、状态
CREATE TABLE orders AS
SELECT
  i AS id,
  1 + (i % 100000) AS customer_id,
  DATE '2024-08-11' + CAST(random() * 730 AS INTEGER) AS order_date,
  round(10 + random() * 990, 2) AS amount,
  (array['pending','paid','shipped','done','cancelled'])[1 + (i % 5)] AS status
FROM generate_series(1, 1000000) t(i);

-- 明细：id、订单、商品、数量、单价
CREATE TABLE order_items AS
SELECT
  i AS id,
  1 + (i % 1000000) AS order_id,
  1 + ((i * 7) % 1000) AS product_id,
  1 + (i % 5) AS qty,
  round(10 + ((i * 13) % 500), 2) AS unit_price
FROM generate_series(1, 2000000) t(i);
```

生成结果（本机实测，秒级完成）：

| 表          | 行数      |
| ----------- | --------- |
| customers   | 100,000   |
| products    | 1,000     |
| orders      | 1,000,000 |
| order_items | 2,000,000 |

马上可以跑真实分析查询（JOIN + 聚合 + 排序）：

```sql
SELECT c.city, o.status,
       count(*) AS order_cnt, round(sum(o.amount), 2) AS total_amount
FROM orders o JOIN customers c ON o.customer_id = c.id
WHERE o.order_date >= DATE '2026-02-01'
GROUP BY c.city, o.status
ORDER BY total_amount DESC
LIMIT 8;
```

## 3. 导出 Parquet 复用

生成一次、导出成 Parquet，之后任何进程都能直接查询（这也是 PG 加速实验的载体）：

```sql
COPY customers   TO 'parquet/customers.parquet'   (FORMAT PARQUET);
COPY products    TO 'parquet/products.parquet'    (FORMAT PARQUET);
COPY orders      TO 'parquet/orders.parquet'      (FORMAT PARQUET);
COPY order_items TO 'parquet/order_items.parquet' (FORMAT PARQUET);
```

之后直接查文件，无需建表：

```sql
SELECT city, count(*) AS n, round(sum(o.amount), 0) AS amt
FROM 'parquet/orders.parquet' o
JOIN 'parquet/customers.parquet' c ON o.customer_id = c.id
WHERE o.order_date >= DATE '2026-01-01'
GROUP BY city ORDER BY amt DESC LIMIT 3;
```

本机实测：100 万订单 → 14 MB 的 parquet（列式压缩），查询秒回。

## 4. TPC-H 基准数据（标准分析型数据集）

想要**业界标准**的模拟数据，用内置的 `dbgen`（TPC-H 基准，8 张表：
customer / orders / lineitem / part / partsupp / supplier / nation / region）：

```sql
CALL dbgen(sf=0.1);   -- sf = scale factor，0.1 ≈ 100MB 原始数据量
```

`sf=0.1` 实测行数：`orders` 15 万、`lineitem` 60 万、`customer` 1.5 万。
`sf=1` 时 lineitem 约 600 万行。数据分布、字段命名都比手搓的更像生产环境，
适合做性能实验的对照数据集。

## 5. 列式剪枝的一个注意点

Parquet 按 **Row Group**（DuckDB 写入时每组 122,880 行）存储，每组带
min/max 统计，查询时可跳过不相关的组：

```sql
SELECT row_group_id, path_in_schema, stats_min_value, stats_max_value
FROM parquet_metadata('parquet/orders.parquet')
WHERE path_in_schema = 'order_date' ORDER BY row_group_id LIMIT 3;
```

本实验的实测输出（每组都是 `2024-08-11 ~ 2026-08-11`）：

```
│  0 │ order_date │ 2024-08-11 │ 2026-08-11 │
│  1 │ order_date │ 2024-08-11 │ 2026-08-11 │
│  2 │ order_date │ 2024-08-11 │ 2026-08-11 │
```

> ⚠️ **注意：** 因为日期是用 `random()` 均匀撒的，每个 Row Group 的
> min/max 都覆盖全区间 → 按日期过滤**无法剪枝**。真实时序数据按时间有序写入时，
> 各组区间互不重叠，过滤就能跳过大部分组。构造测试数据时这点要心里有数。

## 6. 参考链接

| 资源                    | 链接                                                                                                                             |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| generate_series 文档    | [https://duckdb.org/docs/stable/sql/functions/utility](https://duckdb.org/docs/stable/sql/functions/utility)                     |
| COPY 语句               | [https://duckdb.org/docs/stable/sql/statements/copy](https://duckdb.org/docs/stable/sql/statements/copy)                         |
| Parquet 元数据函数      | [https://duckdb.org/docs/stable/data/parquet/metadata](https://duckdb.org/docs/stable/data/parquet/metadata)                     |
| TPC-H 数据生成（dbgen） | [https://duckdb.org/docs/stable/guides/performance/benchmarking](https://duckdb.org/docs/stable/guides/performance/benchmarking) |

→ 下一站：[PostgreSQL 加速查询](./postgresql-acceleration.md)
