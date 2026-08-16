---
title: Cloudflare KV Database Research
created: 2026-08-17
tags: [cloudflare, kv, database, research, prototype]
---

# Cloudflare KV Database Research

## Goal

学习 Cloudflare KV (Workers KV)：读写模型、TTL、缓存语义、限制与定价，
并评估 KV vs Cache API vs Durable Objects vs 其他存储（如 R2）的适用场景。
产出形式：research 笔记或 prototype（二选一，先 research 再决定是否孵化 prototype）。

内容落在 `docs/notes/research/topics/cloudflare-kv/`，若做原型则放在 `prototypes/cloudflare-kv/`。

## Tasks

- [ ] **Research: KV 基础概念**

  - Workers KV 是什么、读写模型（eventual consistency，global read-after-write?）
  - Namespace / Key-Value 结构、list/get/put/delete API
  - TTL、metadata、批量写入（write-through vs write-behind）
  - 发布到 `docs/notes/research/topics/cloudflare-kv/`

- [ ] **Research: 缓存语义与一致性**

  - 写入后读取的传播时延、local cache（cacheTtl）行为
  - KV vs Cache API vs Durable Objects vs R2 的取舍
  - 典型用例：配置存储、特性开关、会话、图片元数据、构建产物
  - 发布到 `docs/notes/research/topics/cloudflare-kv/`

- [ ] **Research: 限制与定价**

  - 免费额度、key 数量限制、value 大小上限（25MiB?）、写放大
  - 冷读取（cold read）费用与风险、FAQ 中推荐的替代方案
  - 发布到 `docs/notes/research/topics/cloudflare-kv/`

- [ ] **Prototype（可选）: 动手验证**

  - 用 `wrangler` 建一个 Worker + KV namespace 的最小 demo
  - 验证 read-after-write、TTL 过期、批量写入
  - 原型放在 `prototypes/cloudflare-kv/`（含独立 README + .gitignore）
  - 验证后决定 promotion 或归档

- [ ] **总结**

  - 更新 `docs/notes/research/index.md` 表格（新增 Topic 行）
  - 给出本项目（静态站/自托管）中 KV 是否值得引入的结论

## Notes

- 本项目已有 R2 使用经验（bucket 托管图片），KV 与其在读写模型/一致性上差异明显，值得单独记录
- 先调研官方文档 + 免费额度，再决定是否做 prototype

## References

- [Collection: Database](../../docs/notes/collection/database.md)
- [Cloudflare KV 文档](https://developers.cloudflare.com/kv/)
