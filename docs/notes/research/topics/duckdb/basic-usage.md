---
hide:
  - navigation
title: DuckDB 环境与基本使用
tags:
  - research
  - tech
  - duckdb
  - database
categories:
  - dev
---

# :material-rocket-launch: 环境与基本使用

> **本页目的：** 把 DuckDB 装起来并跑通基本用法 —— CLI、Python API、常用 SQL、CSV 导出、
> 扩展机制。全部基于本机实测（DuckDB v1.5.5 Variegata，macOS arm64）。
>
> 本页是 DuckDB 实战系列第 1 篇，下一篇见 [模拟数据](./mock-data.md)。

## 1. 安装

DuckDB 有两个形态：**CLI 二进制** 与 **Python 包**。本机用 `uv` 管理，无需全局安装：

```bash
# Python API（临时环境，不污染项目依赖）
uv run --with duckdb python -c "import duckdb; print(duckdb.__version__)"   # 1.5.5

# CLI（新版 duckdb 包不再自带 CLI，需用 duckdb-cli 包）
uvx --from duckdb-cli duckdb --version   # v1.5.5 (Variegata)
```

> ⚠️ **坑：** `uvx duckdb` 会报 `Package "duckdb" does not provide any executables` ——
> 新版 `duckdb` Python 包不再附带 CLI，要用 `uvx --from duckdb-cli duckdb`。

> 💡 **uvx 装在哪：** `uvx` 是**临时执行**，不装到当前目录，全部落在 uv 的全局缓存里
> （`uv cache dir` 查看；默认 `$UV_CACHE_DIR` > `$XDG_CACHE_HOME/uv` > `~/.cache/uv`）。
> 结构大致是：`wheels-v6/` 存下载的 wheel，`archive-v0/<hash>/` 存解压后的包
> （duckdb 的 `bin/duckdb` 就在这里），`environments-v2/<hash>/` 是临时 venv，
> 用符号链接指回 archive-v0。跑完后临时 venv 清理，但包会留在缓存里复用，
> 所以第二次执行会快很多。想**持久安装**（可卸载、入口进 `~/.local/bin`）用
> `uv tool install duckdb-cli`，那是装到 `~/.local/share/uv/tools/`。

## 2. CLI 基本操作

CLI 支持 **内存库**（不指定文件）与 **文件库**（单文件持久化，就是普通文件，
可拷走/备份）：

```bash
uvx --from duckdb-cli duckdb                    # 内存库
uvx --from duckdb-cli duckdb test.duckdb        # 文件库（不存在则创建）
uvx --from duckdb-cli duckdb test.duckdb -c "SQL"   # 非交互执行
```

交互模式常用元命令：

| 命令                            | 作用         |
| ------------------------------- | ------------ |
| `.tables`                       | 列出表       |
| `.schema t`                     | 查看建表语句 |
| `.mode list` / `.mode markdown` | 切换输出格式 |

示例：

```sql
-- 文件库：建表 + 写入 + 查询
CREATE TABLE users (id INTEGER, name VARCHAR, created DATE);
INSERT INTO users VALUES (1, 'Alice', '2026-01-01'), (2, 'Bob', '2026-02-14');
SELECT id, name, strftime(created, '%Y-%m') AS ym FROM users ORDER BY id;
```

## 3. Python API

```python
import duckdb

# 1) 连接：内存库 vs 文件库
con_mem = duckdb.connect()  # 内存库
con_file = duckdb.connect("app.duckdb")  # 文件库

# 2) 默认连接：不显式 connect 也能直接查
duckdb.sql("SELECT 40 + 2").fetchone()  # (42,)

# 3) con.sql()（推荐，返回 relation）vs con.execute()（返回 cursor）
con_file.sql("SELECT 'a'").fetchone()  # ('a',)
con_file.execute("SELECT 'b'").fetchone()  # ('b',)

# 4) pandas / Arrow 互操作：直接查 DataFrame（零拷贝）
import pandas as pd

df = pd.DataFrame({"city": ["上海", "北京"], "pop": [2487, 2189]})
duckdb.sql("SELECT city FROM df WHERE pop > 2000").df()  # 结果取回 DataFrame
duckdb.sql("SELECT count(*) FROM df").arrow()  # 取回 Arrow RecordBatch

# 5) 结果展示
con_file.sql("SELECT ...").show()  # CLI 风格的表格输出
```

> **要点：** DuckDB 是进程内嵌入式数据库，**没有 server、没有端口、没有序列化开销**。
> 查询 pandas DataFrame、Arrow 表时直接读内存数据，不用导入导出。

## 4. 常用 SQL 特性

```sql
-- CTAS：建表并写入
CREATE TABLE sales AS
  SELECT * FROM (VALUES (1,'2026-01',100),(2,'2026-01',50)) t(id, ym, amt);

-- 窗口函数
SELECT id, ym, amt, sum(amt) OVER (PARTITION BY ym) AS ym_total FROM sales;

-- DESCRIBE 查看表结构
DESCRIBE sales;

-- COPY：与文件互导（CSV / Parquet）
COPY sales TO 'sales.parquet' (FORMAT PARQUET);
COPY sales FROM 'sales.csv'   (FORMAT CSV, HEADER);

-- EXPLAIN ANALYZE 查看执行计划与耗时
EXPLAIN ANALYZE SELECT ym, sum(amt) FROM sales GROUP BY ym;
```

## 5. 导出表到 CSV

最常用的是 `COPY ... TO`，支持分隔符、表头、压缩等选项：

```sql
-- 基本导出
COPY sales TO 'sales.csv' (FORMAT CSV, HEADER);

-- 不带表头
COPY sales TO 'sales-nohead.csv' (FORMAT CSV, HEADER false);

-- 自定义分隔符（TSV）
COPY sales TO 'sales.tsv' (FORMAT CSV, DELIMITER E'\t', HEADER);

-- 导出为 gzip 压缩的 CSV
COPY sales TO 'sales.csv.gz' (FORMAT CSV, HEADER, COMPRESSION GZIP);

-- 只导出查询结果（子查询）
COPY (SELECT id, amt FROM sales WHERE amt > 50) TO 'big.csv' (FORMAT CSV, HEADER);
```

> **实测：** 1.5.5 里 COPY CSV 的 `HEADER` **默认为 true**（不写也会带表头），
> 需要无表头时显式写 `HEADER false`。分隔符用 `DELIMITER`，制表符转义写法 `E'\t'`。

CLI 交互模式也可以用 `.mode` / `.output` 把查询结果写进文件：

```
.mode csv
.output sales.csv
SELECT * FROM sales;
.output stdout
```

导出结束后用 `.output stdout` 恢复终端输出（注意：`.output` 命令不支持行内注释）。

Python API 里 relation 自带 `to_csv()`：

```python
duckdb.sql("SELECT * FROM sales").to_csv("sales.csv", header=True)
```

反向导入（CSV → 表）见第 4 节 `COPY sales FROM ...`。

## 6. 扩展机制

DuckDB 通过扩展提供更多功能，分两类：

| 扩展               | 安装方式                                           | 用途                     |
| ------------------ | -------------------------------------------------- | ------------------------ |
| `parquet` / `json` | **核心扩展**，开箱即用                             | Parquet / JSON 读写      |
| `httpfs`           | `INSTALL httpfs; LOAD httpfs;`                     | 读取远程 HTTP(S)/S3 文件 |
| `postgres_scanner` | `INSTALL postgres_scanner; LOAD postgres_scanner;` | 连接 PostgreSQL          |

```sql
INSTALL postgres_scanner; LOAD postgres_scanner;   -- 需要网络下载扩展
LOAD parquet; LOAD json;                            -- 核心扩展直接 LOAD

-- 查看扩展状态
SELECT extension_name, installed, loaded
FROM duckdb_extensions()
WHERE extension_name IN ('parquet','json','httpfs','postgres_scanner');
```

> **坑：** 1.5.5 里 `LOAD httpfs` 会报 `Extension not found. Install it first` ——
> 非核心扩展必须先 `INSTALL`（联网下载）再 `LOAD`；`INSTALL` 后扩展文件缓存在
> `~/.duckdb/extensions/`。

## 7. 参考链接

| 资源        | 链接                                                                                                             |
| ----------- | ---------------------------------------------------------------------------------------------------------------- |
| DuckDB 文档 | [https://duckdb.org/docs/](https://duckdb.org/docs/)                                                             |
| Python API  | [https://duckdb.org/docs/stable/clients/python/overview](https://duckdb.org/docs/stable/clients/python/overview) |
| 扩展列表    | [https://duckdb.org/docs/stable/extensions/overview](https://duckdb.org/docs/stable/extensions/overview)         |

→ 下一站：[模拟数据](./mock-data.md)
