---
title: Raft + LevelDB 分布式高可用数据库
created: 2026-08-23
tags: [raft, leveldb, database, distributed, research, prototype]
---

# Raft + LevelDB 分布式高可用数据库

## Goal

用 Raft 共识算法 + LevelDB 存储引擎封装一个**分布式、高可用**的
KV 数据库原型：多节点通过 Raft 达成一致（选主、日志复制、故障转移），
状态机落地到 LevelDB，对外提供简单的 KV API。理解共识协议与单机存储
如何组合成分布式系统，并对照 TiKV（raft-rs + RocksDB）等真实实现复盘。

实现代码按 Prototype 约定放在 `prototypes/raft-db/`（自带 README 与
`.gitignore`），中文笔记发布到 `docs/notes/research/topics/raft-db/`。

## Tasks

- [ ] **设计概览，确定技术选型**

  - 语言与库：Go（[etcd-io/raft](https://github.com/etcd-io/raft) + goleveldb，
    后者为 LevelDB 的纯 Go 重实现）或 Rust（[raft-rs](https://github.com/tikv/raft-rs)
    + leveldb crate）；选型在 README 记录理由
  - 架构：Raft 集群（3 节点起步）→ 日志应用 → 状态机（KV 内存态）→
    LevelDB 持久化；区分 leader 读 / 线性一致性读的取舍
  - API 面：Put / Get / Delete，可选 Watch

- [ ] **搭建单节点存储层**

  - LevelDB 集成：KV 数据持久化、批量写入、快照恢复（Raft Snapshot 语义）
  - 状态机接口（Apply(entry) → 变更内存 + LevelDB），为接入 Raft 预留

- [ ] **接入 Raft 共识层**

  - 基于 etcd-io/raft 或 raft-rs：节点启动、选举、日志复制
  - 客户端请求 → 提案（Propose）→ 日志提交 → Apply 到状态机 → 响应
  - 持久化 raft 自身状态（硬状态、日志）与 Snapshot 触发/恢复
  - 网络层：节点间 RPC 传输（可先用进程内模拟/真实 TCP 二选一）

- [ ] **分布式特性验证**

  - 3 节点集群：正常写入一致、leader 切换后继续服务
  - 故障注入：kill leader / 单节点，验证可用性与一致性（多数派存活）
  - 测试脚本：写一批 key → 切 leader → 读回结果一致

- [ ] **复盘与发布**

  - 对照 TiKV（raft-rs + RocksDB）与 etcd（raft + boltdb）真实架构，
    记录设计取舍（读写路径、WAL、Snapshot、线性一致性）
  - 笔记发布到 `docs/notes/research/topics/raft-db/`
  - 更新 `docs/notes/research/index.md` 与 `prototypes/README.md`

## Notes

- 前置知识：Raft 基本概念（选主、日志复制、多数派）与 LevelDB/LSM 存储模型；
  可先用 etcd raft 官方 example（raftexample）跑通最小闭环再自研
- 存储选型提示：goleveldb 是 LevelDB 的纯 Go 重实现（无官方 Go 绑定）；若选 Rust，
  `leveldb` crate 维护一般，可评估 rocksdb / sled 等替代
- 最小可用优先：先保证「写入一致 + leader 故障转移」，再考虑性能与
  线性一致性读
- 参考：etcd 的 raftexample、TiKV 的 raft-rs

## References

- [Collection: Database → Key-Value / Consensus / Raft](../../docs/notes/collection/database.md)
- [etcd raft](https://github.com/etcd-io/raft) - Go Raft 实现（含 raftexample）
- [raft-rs](https://github.com/tikv/raft-rs) - Rust Raft 实现
- [TiKV](https://github.com/tikv/tikv) - 分布式 KV（raft-rs + RocksDB，对照样本）
- [LevelDB](https://github.com/google/leveldb) - 嵌入式 KV 存储
- [rqlite](https://github.com/rqlite/rqlite) - Raft + SQLite 分布式数据库（同类最小实现）
- [Research 索引](../../docs/notes/research/index.md)
