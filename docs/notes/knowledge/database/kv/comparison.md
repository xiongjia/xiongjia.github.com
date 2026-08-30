---
hide:
  - navigation
title: KV 数据库对比
tags:
  - knowledge
  - database
  - kv
categories:
  - database
---

# KV 数据库对比

KV 存储引擎横向对比：RocksDB / LevelDB / Pebble / Badger / LMDB / redb / bbolt。

> ⭐ 评分为相对经验判断，非基准测试结果。

| 维度       | RocksDB    | LevelDB  | Pebble     | Badger     | LMDB       | redb       | bbolt      |
| ---------- | ---------- | -------- | ---------- | ---------- | ---------- | ---------- | ---------- |
| 语言       | C++        | C++      | Go         | Go         | C          | Rust       | Go         |
| 类型       | LSM        | LSM      | LSM        | LSM        | B+Tree     | B+Tree     | B+Tree     |
| 写性能     | ⭐⭐⭐⭐⭐ | ⭐⭐⭐   | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐   | ⭐⭐⭐⭐   | ⭐⭐⭐⭐   | ⭐⭐⭐     |
| 读性能     | ⭐⭐⭐⭐   | ⭐⭐⭐⭐ | ⭐⭐⭐⭐   | ⭐⭐⭐⭐   | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐   | ⭐⭐⭐⭐   |
| 并发       | ⭐⭐⭐⭐⭐ | ⭐⭐⭐   | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐   | ⭐⭐⭐⭐   | ⭐⭐⭐     | ⭐⭐       |
| 功能丰富度 | ⭐⭐⭐⭐⭐ | ⭐⭐     | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐   | ⭐⭐⭐     | ⭐⭐⭐     | ⭐⭐       |
| 内存占用   | 较高       | 较低     | 较高       | 较高       | 很低       | 低         | 低         |
| 使用复杂度 | 高         | 低       | 中         | 中         | 低         | 低         | 低         |
| Rust 生态  | 一般       | 一般     | —          | —          | —          | ⭐⭐⭐⭐⭐ | —          |
| Go 生态    | 一般       | 一般     | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐     | ⭐⭐⭐     | ⭐⭐⭐⭐⭐ |
| TS/Node    | binding    | binding  | —          | —          | —          | binding    | —          |

以上 7 个引擎均为进程内运行（随应用进程启动、无需独立服务）的 KV 引擎。

## 分布式实现对比

上面的引擎多数都有对应的分布式产品：以「引擎 + 共识复制」拼出分布式 KV。

| 分布式 KV            | 底层存储引擎                         | 共识 / 复制                      | 语言       |
| -------------------- | ------------------------------------ | -------------------------------- | ---------- |
| TiKV                 | RocksDB                              | Raft                             | Rust       |
| YugabyteDB (DocDB)   | RocksDB（每 tablet 一个实例）        | Raft                             | C++        |
| etcd                 | bbolt                                | Raft                             | Go         |
| CockroachDB          | Pebble                               | Raft（etcd/raft 的 fork）        | Go         |
| Dgraph               | Badger                               | Raft（alpha 节点间复制）         | Go         |
| FoundationDB         | Redwood（自研 B+ 树，早期用 SQLite） | Paxos 类事务协议                 | C++        |
| HBase                | HFile（LSM，存 HDFS）                | HDFS 复制 + ZooKeeper 协调       | Java       |
| Cassandra / ScyllaDB | 自研 LSM                             | Gossip + 仲裁复制（Dynamo 风格） | Java / C++ |
| Redis Cluster        | 内存                                 | Gossip + 哈希槽（无共识协议）    | C          |

**对应关系速记**：

- RocksDB → TiKV / YugabyteDB
- bbolt → etcd
- Pebble → CockroachDB（Pebble 本身不含分布式，复制在 CockroachDB 层实现）
- Badger → Dgraph
- LevelDB / LMDB / redb → 无主流分布式形态
- Cassandra 5 / ScyllaDB 5+ 引入 Raft 仅用于元数据管理，数据复制仍是 Gossip 仲裁

## 引擎简介

- **RocksDB**：Facebook 基于 LevelDB 的 C++ 改进版，面向生产环境、高写入吞吐场景（如流式计算、时序存储），功能与调优项极为丰富，但配置复杂度高。
- **LevelDB**：Google 出品的 LSM 树开源鼻祖，简单可靠、占用低；功能相对单一（无前缀扫描优化、无列族等高级特性）。
- **Pebble**：CockroachDB 团队用 Go 从零实现的 LSM 引擎，借鉴 RocksDB/LevelDB 设计，是 Go 生态（尤其 CockroachDB）的事实标准。
- **Badger**：Dgraph 的 Go 实现，针对 SSD 优化，value 存储在 LSM 之外（value log），随机写与 GC 表现好。
- **LMDB**：Symas 的 C 实现，基于 B+ 树 + 内存映射文件（mmap），读性能极快、内存占用极低，常用于高读取、低写入延迟要求的场景（如 DNS、消息队列索引）。
- **redb**：纯 Rust 实现的 B+ 树数据库，API 现代（带类型化键值、事务），是 Rust 生态中轻量又安全的选择（`Rust 生态` 一栏指官方/原生绑定支持）。
- **bbolt**：etcd 的 Go 存储引擎（原 BoltDB 维护分支），B+ 树 + mmap，单写者多读者、快照隔离，读快写慢、API 简单，是 Go 生态 KV 的事实标准。

## 选型速记

- **写密集 / 大数据量 / 要丰富功能** → RocksDB（C++ 栈）或 Pebble / Badger（Go 栈）
- **读密集 / 低内存 / 简单** → LMDB（C）或 redb（Rust）
- **Rust 项目** → redb
- **Go 项目** → Pebble（CockroachDB 系）或 Badger（Dgraph 系）；读密集/简单场景 → bbolt（etcd 系）
