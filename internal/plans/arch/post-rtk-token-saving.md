---
title: Blog Post — RTK 使用与节约 token
created: 2026-08-02
archived: 2026-08-16
status: completed
tags: [blog, post, dev, tools, ai, token]
---

# Blog Post: RTK 使用与节约 token

## Goal

写一篇博客，记录 RTK（Rust Token Killer）的安装、配置与实测 —— 它是如何
在 agent 读取 bash 输出前压缩/过滤内容，从而减少 LLM token 消耗的。

Published under `docs/notes/posts/posts/`（建议 `bits` 分类）。

## Tasks

- [x] **体验并收集素材**

  - 安装 RTK（`brew install rtk` 或官网快速安装脚本）— 本机 v0.45.0（Homebrew）
  - 在本地 dev 环境（MkDocs build、git status/diff、pytest、ruff）实测效果 ✓
  - 记录安装前后 agent 读取的 bash 输出字节数 / token 估算对比 ✓（MkDocs build 93.4%、pytest 97.3%、find 86%……）
  - 确认与当前 shell / agent 的集成方式 ✓（pi extension：`~/.pi/agent/extensions/rtk.ts`，tool_call 事件中调用 `rtk rewrite` 重写命令）

- [x] **写 post 大纲**

  - 背景：LLM 编码 agent 的 token 消耗大头之一是 bash 输出
  - 原理：RTK 在命令输出进入 LLM context 之前压缩（4 种策略：过滤/分组/截断/去重）
  - 安装：Homebrew / 快速安装脚本（单 Rust 二进制、零依赖）
  - 使用效果：本地实测数据（节约百分比与绝对 token 估算的局限性）
  - 注意点：官方说明“削减输出 ≠ 账单减 90%”；小输出命令 RTK 反而更大；token 数只是估算
  - 参考链接：GitHub repo、[rtk-ai.app](https://www.rtk-ai.app/)

- [x] **写 post**

  - 遵循现有 post 格式（frontmatter：title、date、authors、tags、slug、description、categories）
  - Category: `bits` / `dev`
  - 文件名遵循 bits 约定：`docs/notes/posts/posts/bits/20260816-rtk-token-saving.md`
  - 包含实测数据表格与代码片段
  - 中文内容（与现有 bits 一致）

- [x] **Review & publish**

  - 验证 dev server 渲染正常 ✓（dev + 生产 build 均正常，表格/代码块/链接/categories/RSS feed 验证通过）
  - 检查链接、代码块 ✓
  - 去掉 `draft: true` 后发布 ✓（无 draft 标记，生产 build 已包含；git commit/push 留待开发者执行）

## Notes

- RTK 支持 100+ 常用命令，小于 10ms 开销；官方宣称可削减 agent 读取的 bash 输出 60-90%
- “token 节约”与“账单节约”不同：输出只是输入 token 的一部分，输入 token 又只是账单的一部分
- 已在 Collection 中添加：[docs/notes/collection/ai.md](../../../docs/notes/collection/ai.md)（AI CLI 分类）

## References

- [RTK GitHub](https://github.com/rtk-ai/rtk)
- [RTK Website](https://www.rtk-ai.app/)
- [How RTK Savings Work](https://www.rtk-ai.app/guide/resources/savings-explained)
