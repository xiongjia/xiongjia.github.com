---
hide:
  - navigation
title: ETL 工具链研究
tags:
  - research
  - tech
  - etl
categories:
  - dev
---

# :material-warehouse: ETL

数据转换 / 数据管道（ETL/ELT）研究 —— 用本地可验证的方式落地每一类工具：
模拟原始数据、转换过程配置（staging → marts）、目标数据生成与增量（incremental）处理。

- 原型工程: `prototypes/etl-dbt/`（仓库根下的实验原型目录，见 [Prototypes 列表](../../../prototypes.md)）

## Sub Topics

| 主题                                    | 描述                                                                                         |
| --------------------------------------- | -------------------------------------------------------------------------------------------- |
| [dbt-core 本地 ETL 实战](./dbt-core.md) | dbt-core + DuckDB 最小 ETL：模拟原始数据 → staging → marts（维度/事实/日汇总），增量配置演示 |

> 后续扩展方向（按需补充，不限定于 dbt-core）：容器 PostgreSQL 本地源库对比、CDC 增量拉取、
> 其他转换/编排工具（Airflow、Dagster、Spark、SQLMesh 等）、外部表 / parquet 即源、CI 集成。

## 相关笔记

- [Collection Database](../../../collection/database.md)：数据库相关资源收藏
- [Research 索引](../../index.md)：研究笔记总目录
