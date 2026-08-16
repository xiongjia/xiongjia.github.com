---
title: MkDocs Media Archive (Books / Movies / Games)
created: 2026-08-17
tags: [mkdocs, plugin, archive, media, research]
---

# MkDocs Media Archive (Books / Movies / Games)

## Goal

为本站寻找一种方法，用 MkDocs 归档「看过的书、影片、玩过的游戏」：
记录时间、评分、短评，并提供按状态（在读/已读、看过、通关等）与分类的浏览方式。
先调研现有方案（插件 / frontmatter + macros / 自研 hook），再决定实现路径。

## Tasks

- [ ] **调研现有方案**

  - MkDocs 插件生态：有没有现成的 reading/collection 类插件（如 rss、tags 扩展）
  - macros (jinja2) + 目录约定（每条目一个 md + frontmatter）的可行性
  - 参照 `docs/notes/collection/` 现有链接页结构与 `mkdocs-moment` 插件写法
  - 输出调研结论到 `internal/` 或 research 笔记

- [ ] **确定数据模型**

  - 每个条目 frontmatter：title、type（book/movie/game）、status、date、rating、tags
  - 目录结构：`docs/notes/media/<type>/<slug>.md`？
  - 状态词汇表（如 planned / in-progress / done）

- [ ] **实现归档页**

  - 用 macros 生成索引页：按 type + status 分组、排序
  - 更新 `docs/notes/` 索引与导航（mkdocs.yml）
  - 可选：自定义 hook 生成统计（总数、年内完成数）

- [ ] **录入首批数据**

  - 从现有阅读记录（`internal/plans/reading-list.md` 等）迁移若干条
  - 验证页面渲染与链接

## Notes

- 关注维护成本：方案应让「随手记一条」足够简单（单个 md + frontmatter）
- 若选自研 hook，参考 `plugins/` 现有插件的测试方式（tests/）

## References

- [Collection: Media](../../docs/notes/collection/media.md)
- [mkdocs.yml](../../mkdocs.yml)
