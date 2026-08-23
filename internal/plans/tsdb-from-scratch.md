---
title: TSDB from scratch 学习计划（基于 write-tsdb-from-scratch）
created: 2026-08-23
tags: [tsdb, database, learning, research, golang]
---

# TSDB from scratch 学习计划（基于 write-tsdb-from-scratch）

## Goal

精读 nakabonne 的 **Write a TSDB from scratch** 系列文章（配套开源实现
tstorage），理解 TSDB 的核心设计（数据模型、内存与磁盘存储、压缩、
compaction、retention），并**自己动手实现一个基本的 TSDB**（建议 Go，
与文章一致），把理解落地成代码 + 中文阅读笔记。

阅读笔记（中文）发布到 `docs/notes/research/topics/tsdb/`；实现代码按
Prototype 约定放在 `prototypes/tsdb-from-scratch/`（自带 README 与
`.gitignore`）。

## Tasks

- [ ] **精读文章系列，建立 TSDB 心智模型**

  - 时序数据的基本单元：series（标签集合 + 时间点序列）、point（timestamp +
    value）
  - 时间分区存储：按时间切分 partition / block，查询与 retention 的裁剪依据
  - 内存缓冲 vs 磁盘刷新：写入先进内存（buffer / chunk），到达阈值或周期性
    落盘
  - 压缩策略：逐点差值 / double-delta（类 Gorilla）等，减少存储占用
  - compaction：小块合并为大块、删除 tombstone 处理、旧数据重写
  - retention：按时间淘汰过期分区，无需逐点删除
  - 查询接口：按时间范围 + 标签过滤取回序列

- [ ] **动手实现基本 TSDB（prototypes/tsdb-from-scratch/）**

  - 基础数据模型：series + point 的存储结构（内存 map + 有序时间切片）
  - 写入路径：append point → 内存缓冲 → 到达阈值落盘
  - 读取路径：按 series + 时间范围查询，合并内存与磁盘数据
  - 简单压缩（差值 / delta 编码）与解压
  - retention：按时间分区淘汰过期数据
  - 最小可用 CLI / 测试用例验证：写入一批点 → 查询回读 → 结果一致
  - 每个里程碑提交，README 记录设计取舍与踩坑

- [ ] **对照 tstorage 源码复盘**

  - 自己实现完成后，对照 [tstorage](https://github.com/nakabonne/tstorage)
    源码看差距：分区粒度、压缩细节、并发控制、落盘时机
  - 记录值得借鉴的点，更新笔记

- [ ] **发布笔记并更新索引**

  - 阅读笔记与实现总结发布到 `docs/notes/research/topics/tsdb/`
  - 更新 `docs/notes/research/index.md`（Learning Plans / Libraries 索引）
  - 更新 `prototypes/README.md`（原型登记）

## Notes

- 前置知识：基础 Go、基本数据结构即可；对 LSM / 列式存储有概念更佳
- 文章配套实现 tstorage 是轻量级嵌入式 TSDB，适合作为对照样本
- 实现以「最小可用、逻辑清晰」为准，不追求生产级特性（如 WAL、分布式）

## References

- [Collection: Database → Time-Series](../../docs/notes/collection/database.md)
- [Write a TSDB from scratch](https://nakabonne.dev/posts/write-tsdb-from-scratch/)
- [tstorage](https://github.com/nakabonne/tstorage)
- [TimescaleDB](https://github.com/timescale/timescaledb)（对照：PG 扩展型 TSDB）
- [InfluxDB](https://github.com/influxdata/influxdb)（对照：独立 TSDB）
- [Research 索引](../../docs/notes/research/index.md)
