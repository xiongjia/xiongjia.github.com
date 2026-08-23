---
hide:
  - navigation
title: PostgreSQL
tags:
  - knowledge
  - database
  - postgresql
categories:
  - database
---

# :simple-postgresql: PostgreSQL

PostgreSQL 日常运维与内部机制知识体系 —— 面向「遇到问题能查、能看懂
PG 在干什么」的实战沉淀：会话与性能诊断、WAL / LSN 机制、复制与备份等。
知识点按问题/主题独立成文，长期演进。

## Docs

| Docs                                                     | Description                                                                                                          |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| [活跃会话诊断（Active Sessions）](./active-sessions.md)  | 查看当前活跃 Session、定位 CPU 高占用与慢查询、终止会话                                                              |
| [查看慢查询（Slow Query）](./slow-queries.md)            | 慢查询定位：日志记录（log_min_duration_statement / auto_explain）与实时统计（pg_stat_activity / pg_stat_statements） |
| [磁盘占用查看（Table Size / Datafile）](./disk-usage.md) | 数据库/表/索引/TOAST 空间占用、数据文件位置与膨胀排查                                                                |
| [WAL 与 LSN](./wal-lsn.md)                               | WAL 机制、LSN 概念与常用查询：当前位置、文件、复制进度                                                               |
