---
hide:
  - navigation
title: DuckDB 实战研究
tags:
  - research
  - tech
  - duckdb
  - database
  - postgresql
categories:
  - dev
---

# :material-database: DuckDB

DuckDB 实战研究 —— 环境与基本使用、模拟数据构造、以及原始数据在
PostgreSQL 时如何用 DuckDB 加速分析查询。

- 官方文档: [https://duckdb.org/docs/](https://duckdb.org/docs/)
- 核心扩展参考: [https://duckdb.org/docs/stable/core_extensions/postgres](https://duckdb.org/docs/stable/core_extensions/postgres)

## Sub Topics

| 阅读顺序 | 主题                                                | 描述                                                                                  |
| -------- | --------------------------------------------------- | ------------------------------------------------------------------------------------- |
| 1        | [环境与基本使用](./basic-usage.md)                  | CLI / Python API 安装与上手、常用 SQL、扩展机制（parquet / json / httpfs / postgres） |
| 2        | [模拟数据](./mock-data.md)                          | 内置生成器、迷你电商数仓（10 万客户 / 100 万订单）、TPC-H dbgen、导出 Parquet         |
| 3        | [PostgreSQL 加速查询](./postgresql-acceleration.md) | pg_duckdb + force_execution、postgres_scanner、Parquet 导出、基准对比                 |

## 推荐阅读顺序

1. **环境与基本使用** → [环境与基本使用](./basic-usage.md)：装好 CLI 与 Python API，
   跑通第一个查询，了解扩展机制
1. **构造模拟数据** → [模拟数据](./mock-data.md)：用 SQL 生成贴近真实的分析数据集，
   导出 Parquet（后续 PG 加速实验的载体）
1. **PG 加速实战** → [PostgreSQL 加速查询](./postgresql-acceleration.md)：数据在 PG 时，
   pg_duckdb + force_execution、postgres_scanner、Parquet 导出、基准对比

> DuckDB 内部原理（向量化执行、列式存储等「为什么快」的进阶内容）
> 暂未收录，后续按需补充。

## 相关笔记

- [Collection Database](../../../collection/database.md)：数据库相关资源收藏
- [Research 索引](../../index.md)：研究笔记总目录
