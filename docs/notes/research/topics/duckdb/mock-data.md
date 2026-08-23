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

> 💡 **补充：外键** —— 上面 4 张表都是 `CREATE TABLE ... AS`（CTAS）建的，**CTAS 不带
> 任何约束**（连主键都没有），所以这套迷你数仓里没有外键，引用一致性靠生成逻辑保证
> （如 `orders.customer_id = 1 + (i % 100000)` 恰好落在 1..100000 区间内）。
>
> DuckDB **支持外键语法**，且本机 1.5.5 实测**强制校验**（插入父行不存在的记录报
> `Constraint Error: Violates foreign key constraint`）。但有几点限制（本机实测）：
>
> - 外键**只能建表时声明**（内联 `REFERENCES` / `FOREIGN KEY (...)`），
>   `ALTER TABLE ... ADD FOREIGN KEY` 不支持（报 `Not implemented`）
> - **不支持** `ON DELETE CASCADE` / `SET NULL` / `SET DEFAULT`，删除被引用的父行
>   默认拒绝（RESTRICT 行为）
> - 被引用列必须是 `PRIMARY KEY` 或 `UNIQUE`
>
> 所以本页生成脚本保持 CTAS 不带约束即可；若要严格外键，需把建表语句改成显式
> `CREATE TABLE` + `REFERENCES` 声明，例如订单表挂到客户表（其余列按需补上，此处只示意思路）：
>
> ```sql
> CREATE TABLE customers (
>     id   INTEGER PRIMARY KEY,
>     name VARCHAR
> );
> CREATE TABLE orders (
>     id          INTEGER PRIMARY KEY,
>     customer_id INTEGER REFERENCES customers(id)  -- 外键：指向 customers.id
> );
>
> -- 多列外键的写法（示意：前提是 orders 有 (id, line_no) 复合主键）：
> CREATE TABLE order_lines (
>     order_id INTEGER,
>     line_no  INTEGER,
>     FOREIGN KEY (order_id, line_no) REFERENCES orders(id, line_no)
> );
> ```

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

**TPC-H 是什么：** 业界标准分析型基准测试，由 TPC（事务处理性能委员会）制定，
定义了一套 8 张表的订单模型 Schema、数据生成器 dbgen 和 22 条标准查询。
数据库厂商都用它横向比性能（DuckDB 官网 benchmark 也用它），所以叫“基准数据”。

DuckDB 把 dbgen **内置成函数**，一条命令就在当前库里直接生成 8 张表
（customer / orders / lineitem / part / partsupp / supplier / nation / region）：

```sql
CALL dbgen(sf=0.1);   -- sf = scale factor，0.1 ≈ 100MB 原始数据量
```

sf 是数据规模档位，各表行数按比例缩放：

| sf   | 原始数据量 | lineitem 行数 |
| ---- | ---------- | ------------- |
| 0.01 | ~10MB      | 6 万          |
| 0.1  | ~100MB     | 60 万         |
| 1    | ~1GB       | 600 万        |

> 原始数据量指未压缩的文本形式，落进 DuckDB 列式存储后体积小很多。
> `sf=0.1` 实测行数：orders 15 万、lineitem 60 万、customer 1.5 万。

**和手搓数据（第 2 节）的区别：** 手搓数据用 `random()` 均匀撒，分布太“平”；
dbgen 按 TPC-H 规范生成，字段分布、键关联更像真实生产数据，性能实验的结果
更可信 —— 手搓数据用来跑通功能，TPC-H 用来测真实性能。

生成后直接用 TPC-H 标准查询验证（本机实测 sf=0.1，60 万行 lineitem，毫秒级）：

```sql
-- 测试 1：TPC-H Q6 收入预测 —— 全表扫描 + 多条件过滤
-- 固定结果 revenue = 11803420.25（sf=0.1，DuckDB 1.5.5），可当数据完整性的回归校验
SELECT sum(l_extendedprice * l_discount) AS revenue
FROM lineitem
WHERE l_shipdate >= DATE '1994-01-01' AND l_shipdate < DATE '1995-01-01'
  AND l_discount BETWEEN 0.06 - 0.01 AND 0.06 + 0.01
  AND l_quantity < 24;

-- 测试 2：TPC-H Q3 运输优先级 —— 三表 JOIN + 聚合 + 排序
SELECT l_orderkey,
       sum(l_extendedprice * (1 - l_discount)) AS revenue,
       o_orderdate, o_shippriority
FROM customer, orders, lineitem
WHERE c_mktsegment = 'BUILDING'
  AND c_custkey = o_custkey
  AND l_orderkey = o_orderkey
  AND o_orderdate < DATE '1995-03-15'
  AND l_shipdate > DATE '1995-03-15'
GROUP BY l_orderkey, o_orderdate, o_shippriority
ORDER BY revenue DESC, o_orderdate
LIMIT 5;
```

想看耗时，把 `.timer on` 放查询前，用 stdin 喂给 CLI（`-c` 里不能用点命令）：

```bash
printf '.timer on\nSELECT ...;\n' | uvx --from duckdb-cli duckdb tpch10.duckdb
```

## 5. 一个注意点：Parquet 的 min/max pruning

机制：Parquet 按 **Row Group** 存储
（DuckDB 写入时每组 122,880 行），每组头部带各列 **min/max 统计**。
查询带过滤条件时，引擎先比对各组的 min/max —— 某组范围与过滤条件完全不
重叠就**整组跳过**、不实际读数据，这就是 pruning（也叫 row group
skipping）。它直接决定按时间过滤这类查询快不快：

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

> ⚠️ **注意：** 本页 `orders` 的日期用 `random()` 均匀撒，每个 Row Group 的
> min/max 都覆盖全区间（实测输出可见）→ 按日期过滤时**每组都可能命中，无法
> pruning**，等于全表扫描（最坏情况）。
>
> **什么时候要紧：** 用这份数据做**性能实验**（尤其按日期过滤，以及
> [PostgreSQL 加速查询](./postgresql-acceleration.md) 的对比实验）时，测出来的
> 是最坏情况数字，不代表真实负载 —— 真实生产数据（订单/日志/流水）是按时间
> 追加写入、天然有序的。**跑通功能 / 验证正确性则无所谓**，random 数据即可。
>
> **需要可剪枝的 Parquet 时**，在导出那一刻按时间排序（Row Group 的 min/max
> 是写入时按数据流顺序算的，表本身的顺序无关）：
>
> ```sql
> COPY (SELECT * FROM orders ORDER BY order_date)
>   TO 'parquet/orders.parquet' (FORMAT PARQUET);
> ```
>
> 实测：50 万行、5 个 Row Group，查最后一个月 —— 随机数据要读 5/5 组，排序后只读 1/5 组。
> 一句话：**数据分布决定 pruning 效果，性能数字只有在数据长得像真实数据时才可信。**

## 6. 参考链接

| 资源                    | 链接                                                                                                                             |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| generate_series 文档    | [https://duckdb.org/docs/stable/sql/functions/utility](https://duckdb.org/docs/stable/sql/functions/utility)                     |
| COPY 语句               | [https://duckdb.org/docs/stable/sql/statements/copy](https://duckdb.org/docs/stable/sql/statements/copy)                         |
| Parquet 元数据函数      | [https://duckdb.org/docs/stable/data/parquet/metadata](https://duckdb.org/docs/stable/data/parquet/metadata)                     |
| TPC-H 数据生成（dbgen） | [https://duckdb.org/docs/stable/guides/performance/benchmarking](https://duckdb.org/docs/stable/guides/performance/benchmarking) |

→ 下一站：[PostgreSQL 加速查询](./postgresql-acceleration.md)
