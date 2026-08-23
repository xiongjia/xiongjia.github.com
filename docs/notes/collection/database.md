---
icon: material/database
hide:
  - tags
---

# :material-database: Database

## SQLite

- [SQLite Docs](https://www.sqlite.org/docs.html)
- [SQLite Github mirror](https://github.com/sqlite/sqlite)
- [SQLite 源代码解析](https://huili.github.io/sqlite/sqliteintro.html)
- [rqlite](https://github.com/rqlite/rqlite) - Raft + SQLite 分布式数据库

## PostgreSQL

- [patroni](https://github.com/zalando/patroni) - Python 实现的 PG 高可用方案 (依赖 ETCD)
- [PGSimCity](https://nikolays.github.io/PGSimCity/) - PostgreSQL 工作原理 3D 可视化模拟：把集群映射为一座虚拟城市（缓冲池、WAL、检查点、autovacuum、复制），可调事务频率/读写比例并跑预设场景（检查点风暴、缓存激冷等）
- [PGSimCity Github](https://github.com/NikolayS/PGSimCity) - 源码（TypeScript + three.js，Apache-2.0，早期原型）
- [pglayers](https://github.com/pglayers/pglayers) - 预编译的 PG extension 层（`pgx-*` 镜像），通过 multi-stage COPY 自由组合各类扩展（pg_duckdb、pgvector、pgmq 等），用于构建含 pg_duckdb 的 Docker 镜像，详见 [pg_duckdb + force_execution](../research/topics/duckdb/postgresql-acceleration.md) ([pglayers.github.io](https://pglayers.github.io/))

## DuckDB

- [DuckDB 实战研究](../../notes/research/topics/duckdb/index.md) - 环境与基本使用、模拟数据构造、PostgreSQL 数据加速查询（postgres_scanner 直连 / 导出 Parquet，实测 ~35x）
- [DuckDB Internals: Why is DuckDB Fast? (Part 1)](https://www.greybeam.ai/blog/duckdb-internals-part-1) - 从 SQL 到存储层的执行路径：进程内执行、查询生命周期（解析/绑定/优化/物理计划）、Pipeline 与 Sink、列式存储（Row Group / Zone Map / Parquet / CSV）
- [DuckDB Internals: Why is DuckDB Fast? (Part 2 Vectorized Execution)](https://www.greybeam.ai/blog/duckdb-internals-part-2) - 向量化执行：Volcano 模型 vs 批量处理、DataChunk/Vector、四种 Vector 类型、Selection Vector、解释执行 vs 查询编译

## Key-Value

- [DragonFly DB](https://dragonflydb.io/) - 类 Redis，更快更省内存
- [TiKV](https://github.com/tikv/tikv) - Rust 实现的分布式 KV 存储（Raft 共识，TiDB 底层）
- [LevelDB](https://github.com/google/leveldb) - Google 的嵌入式 KV 存储（LSM 树）

## Time-Series

- [GrepTimeDb](https://github.com/GreptimeTeam/greptimedb) - Rust 实现的 TSDB
- [tstorage](https://github.com/nakabonne/tstorage) - Go 实现的轻量级嵌入式 TSDB
- [Write a TSDB from scratch](https://nakabonne.dev/posts/write-tsdb-from-scratch/) - tstorage 作者系列文章：从零实现 TSDB
- [TimescaleDB](https://github.com/timescale/timescaledb) - PostgreSQL 扩展时序数据库
- [InfluxDB](https://github.com/influxdata/influxdb) - Go 时序数据库（知名开源项目）

## DB Tools

- [dbeaver](https://dbeaver.io) - 跨平台数据库管理工具 (Java, JDBC)
- [tabularis](https://github.com/TabularisDB/tabularis) - Rust + TypeScript 数据库客户端

## Consensus / Raft

- [etcd raft](https://github.com/etcd-io/raft) - Go 实现的 Raft 共识算法库（etcd 核心）
- [raft-rs](https://github.com/tikv/raft-rs) - Rust 实现的 Raft 共识算法库（TiKV 核心）
