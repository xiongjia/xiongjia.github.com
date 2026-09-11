---
hide:
  - navigation
title: KV 数据库
tags:
  - knowledge
  - database
  - kv
categories:
  - database
---

# :material-database: KV 数据库

KV 存储引擎知识体系 —— 按**存储模型**分类整理 RocksDB / LevelDB / Pebble /
Badger / LMDB / redb / bbolt，以及 Bitcask 模型（rosedb / basho/bitcask）的机制
与选型。

## 存储模型分类

| 模型                       | 代表引擎                            | 核心思路                                                                           |
| -------------------------- | ----------------------------------- | ---------------------------------------------------------------------------------- |
| LSM-Tree                   | RocksDB / LevelDB / Pebble / Badger | 顺序写 + 分层 compaction，写密集首选；key 索引不必全放内存                         |
| B+Tree                     | LMDB / redb / bbolt                 | 原地更新 + mmap，读密集 / 低内存                                                   |
| Bitcask（日志 + 内存索引） | rosedb / basho/bitcask              | append-only 日志 + 全部 key 的 keydir 常驻内存，读最多一次 seek，靠 merge 回收空间 |

## Docs

| Docs                             | Description                                                                              |
| -------------------------------- | ---------------------------------------------------------------------------------------- |
| [KV 数据库对比](./comparison.md) | KV 引擎全面对比（语言、存储结构、性能、生态）                                            |
| [Bitcask 存储模型](./bitcask.md) | 日志结构哈希表：数据结构（entry / keydir / hint file / merge）、读写路径、优劣与实现列表 |
