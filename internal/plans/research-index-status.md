---
title: Research Index Status Column
created: 2026-08-17
tags: [mkdocs, research, index, docs]
---

# Research Index Status Column

## Goal

改进 `docs/notes/research/index.md`（及可能的 topics 索引）：为每个 research
Topic 增加一个「状态」维度，让读者一眼看出该主题是活跃维护中、已完成、
停滞还是待完善，便于决定读哪篇笔记、继续投入哪条路线。

## Tasks

- [ ] **确定状态模型**

  - 定义状态词汇：如 `active`（持续更新）/ `done`（完成）/ `stale`（过时，待更新）/ `draft`（草稿）
  - 确认状态记录位置：Topic 的 `index.md` frontmatter（推荐，单一数据源）

- [ ] **为现有 Topic 打标**

  - 遍历 `docs/notes/research/topics/*/index.md`，按实际内容打上状态
  - 与各 Topic 的 plan（如 lux/trip/shadcn 改进计划）联动，标记待改进项

- [ ] **更新 research 索引页**

  - `docs/notes/research/index.md` 表格增加「状态」列（如用 emoji + 文字）
  - 说明状态含义（表格下方加图例）

- [ ] **维护约定**

  - 在 plan-index 或 research 索引中注明：新 Topic 建立时须带状态字段
  - 检查是否有自动生成部分（macros/hook）需要同步

## Notes

- 保持低维护成本：状态存在 Topic frontmatter 一处，索引页手工同步即可
- 与「Improve Lux/Trip/shadcn research」计划联动，被标记为 stale 的即对应那些计划

## References

- [Research Index](../../docs/notes/research/index.md)
