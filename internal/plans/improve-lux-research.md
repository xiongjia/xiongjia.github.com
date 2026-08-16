---
title: Improve Lux Research
created: 2026-08-17
tags: [lux, research, go, improve]
---

# Improve Lux Research

## Goal

改进现有的 Lux research 笔记（`docs/notes/research/topics/lux/index.md`）：
该笔记基于旧 branch `master`（`dd00f6d`），需要核对上游更新、补全缺失部分、
修正过时内容，并补充实操示例。

## Tasks

- [ ] **核对上游版本**

  - 检查 lux 仓库最新 release / master 是否已超出当前记录 commit
  - 若有更新：标注新的依据 commit，diff 关键变更（新增下载器、行为变化）
  - 更新笔记头部 "依据 lux 仓库" 信息

- [ ] **补全/修正内容**

  - 通读现有笔记，列出过时或错误结论（API 变化、已废弃特性）
  - 核对现有代码片段是否仍能编译/运行
  - 补充缺失主题：多网站下载器结构、插件式扩展、登录/cookie 处理
  - 保持中文写作 + 每节带代码片段

- [ ] **补充实操示例**

  - 本地 clone + 编译运行的最小示例
  - 常见用法（下载单视频/列表、输出格式、代理配置）命令记录

- [ ] **维护索引**

  - 确保 `docs/notes/research/index.md` 中 Lux 的描述与实际一致

## Notes

- 现有笔记 16.8K，先 diff 上游再动手，避免大改破坏已有结构
- 保持原有风格：资料整理 + 源码阅读指南

## References

- [Lux Topic](../../docs/notes/research/topics/lux/)
- [Lux 仓库](https://github.com/iawia002/lux)
