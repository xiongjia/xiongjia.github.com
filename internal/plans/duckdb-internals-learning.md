---
title: DuckDB Internals 学习计划（Greybeam 系列文章）
created: 2026-08-01
tags: [duckdb, database, learning, research, query-engine]
---

# DuckDB Internals 学习计划（Greybeam 系列文章）

## Goal

精读 Greybeam 的 **DuckDB Internals: Why is DuckDB Fast?** 系列文章
（Part 1 存储与查询计划 / Part 2 向量化执行），建立对 DuckDB 内部机制的
完整心智模型：

- 一条 SQL 从文本到结果的完整执行路径（解析 → 绑定 → 优化 → 物理计划 → 执行）
- 进程内执行与零拷贝如何绕开传统数据库的网络序列化开销
- 列式存储的加速原理：Row Group、Zone Map、Parquet 统计信息剪枝
- 向量化执行为何比 Volcano 逐行模型快：DataChunk/Vector、四种 Vector 格式、
  Selection Vector、解释执行 vs 查询编译

阅读笔记（中文）发布到 `docs/notes/research/topics/duckdb/`。

## Tasks

- [ ] **精读 Part 1：从 SQL 到执行引擎与存储层**

  - 进程内执行（in-process）：无 Server、无序列化开销；replacement scan 与
    pandas/Arrow 的零拷贝路径
  - 查询生命周期：Parsing（Postgres 解析器 fork + AST）→ Binding（catalog
    解析与类型检查）→ Optimizer（33 个 pass，重点：filter pushdown、
    subquery unnesting、dynamic join-filter pushdown、join order / DPhyp）
  - 物理计划：Pipeline 与 Pipeline Breaker（Sink），Sink 的
    sink → combine → finalize 三阶段
  - 存储层：单文件 256KB Block + checksum；列式存储；Row Group（122,880 行）；
    Zone Map（min/max/null count）剪枝；Parquet footer 与远程只读所需字节；
    CSV sniffer
  - 动手验证：`SELECT * FROM duckdb_optimizers()` 查看优化器列表；
    用 `SET disabled_optimizers = '...'` 关闭某 pass 观察计划变化
  - 发布阅读笔记到 `docs/notes/research/topics/duckdb/index.md`

- [ ] **精读 Part 2：向量化执行**

  - 背景：IPC 与 MonetDB/X100；Volcano 模型（open/next/close）逐行开销
  - 批量处理：2048 行 batch 的缓存友好性
  - DataChunk 与 Vector；四种 Vector 类型：Flat / Constant / Dictionary /
    Sequence 及其物理与逻辑表示差异
  - UnifiedVectorFormat（data pointer + selection vector + validity mask）
  - Filter 与 Selection Vector：无拷贝过滤；validity mask 的 NULL 追踪
  - Inner loop 与预编译函数：查询编译（HyPer / Spark whole-stage codegen）
    vs DuckDB 的解释执行（precompiled functions）
  - 动手验证：`SELECT ... FROM duckdb_functions() WHERE internal ...` 查看
    内置函数目录；用 Python 实测 flat vs constant vector 相关查询
  - 发布阅读笔记到 `docs/notes/research/topics/duckdb/`（Part 2 部分）

- [ ] **串联总结：Part 1 + Part 2 心智模型**

  - 用自己的话串联：查询如何被拆分进 Pipeline、向量如何在算子间流动、
    存储统计如何参与剪枝
  - 更新 `docs/notes/research/index.md` 的 Learning Plans / Libraries 索引
  - 若 Part 3（morsel-driven parallelism）已发布，顺手收录

## Notes

- 系列文章共 3 篇：Part 1（存储与计划）、Part 2（向量化执行）、
  Part 3（morsel-driven parallelism，尚未发布/待收录）
- 作者：Kyle Cheung（Greybeam，Snowflake 成本观测工具公司）
- 前置知识建议：了解基本 SQL 与数据库概念即可；对 Volcano 模型或
  columnar 存储有概念更佳
- 文章包含大量可执行验证的 DuckDB SQL（`duckdb_optimizers()`、
  `duckdb_functions()` 等），建议边读边跑

## References

- [Collection: Database → DuckDB](../../docs/notes/collection/database.md)
- [DuckDB Internals: Why is DuckDB Fast? (Part 1)](https://www.greybeam.ai/blog/duckdb-internals-part-1)
- [DuckDB Internals: Why is DuckDB Fast? (Part 2 Vectorized Execution)](https://www.greybeam.ai/blog/duckdb-internals-part-2)
- [Research 索引](../../docs/notes/research/index.md)
