---
title: Research Index Status Column
created: 2026-08-17
archived: 2026-08-25
status: completed
tags: [mkdocs, research, index, docs]
---

# Research Index Status Column

## Goal

改进 `docs/notes/research/index.md`（及可能的 topics 索引）：为每个 research
Topic 增加一个「状态」维度，让读者一眼看出该主题是活跃维护中、已完成、
停滞还是待完善，便于决定读哪篇笔记、继续投入哪条路线。

## Tasks

- [x] **确定状态模型**

  - ✅ 状态词汇已定：`polished`（笔记打磨完毕，可用）/ `long-term`（长期滚动积累）/ `draft`（进行中，可删除）
  - ⚠️ 偏离提案：实际词汇按「笔记完善度」而非「活跃度」，为 `polished/long-term/draft`，非提案的 `active/done/stale/draft`
  - ⚠️ 偏离提案：状态记录在**索引页表格**（单一维护点），未采用「Topic frontmatter」方案

- [x] **为现有 Topic 打标**

  - ✅ 索引页已为全部 12 个 topic 标注（polished: Protomaps/DuckDB；long-term: English；其余 draft）
  - ✅ 联动关系可用：lux/trip/shadcn 等改进计划对应 topic 当前均为 draft，改进完成后升 polished

- [x] **更新 research 索引页**

  - ✅ `docs/notes/research/index.md` 表格已加「Status」列 + 图例（表格下方 `> **Status**: ...`）
  - ✅ 索引页当前状态与实现一致

- [x] **维护约定**

  - ✅ `docs/notes/research/index.md` 图例下方已补约定：「新建 Topic 时补一行并填状态（draft → 下方 Drafts 表；polished/long-term → 上方主表）；状态变化时同步更新本表」
  - ✅ 已确认无自动生成部分（macros/hook），索引表为手工维护单一数据源

## Notes

- 实现偏离原提案：状态单一维护点在**索引页表格**（Topic frontmatter 无 status 字段），维护成本低、无自动生成部分
- 与「Improve Lux/Trip/shadcn research」计划联动：对应 topic 当前标为 draft，改进后升 polished
- 全部 4 项任务已完成

## References

- [Research Index](../../docs/notes/research/index.md)
