---
title: 英语学习计划 — Hollow Knight English Reader
created: 2026-07-31
tags: [english, learning, hollow-knight]
---

# 英语学习计划 — Hollow Knight English Reader

> **2026-08-11 结构调整**：发音（pronunciation / mistakes-log）、shadowing、
> vocabulary、weekly-review 等「每日/每周模型」页面已移除（用户无法维持固定
> 节奏）；词汇积累统一走 English Scraps（见 `english-scraps.md` 计划）。
> 本计划只保留 **HK 主题阅读**：`hollow-knight/` 阅读材料 + 素材清单。
> 通用工具链约定（draft 机制 / AI 草稿迭代 / 格式规范）任务已取消——
> 由 `english-scraps.md` 的「工具链与约定」覆盖。

## Goal

把 **Hollow Knight** 作为英语阅读主题（游戏兴趣驱动、文本量适中、词汇反复
出现），阅读与素材沉淀在 `hollow-knight/`；阅读中遇到的生词 / 难句 / 搭配
随手丢进 English Scraps（`poe enu add` / 「enu 记」），由 AI 统一归档复习。

## 背景与关键限制

- 游戏兴趣驱动、世界观完整、文本量适中、词汇反复出现 → 适合做长期阅读材料
- **重要限制**：Hollow Knight 几乎没有正常的英语配音 → 适合英语阅读，
  **不适合作为 Shadowing 材料**（Shadowing 体系已随每日模型移除）

## 内容位置

知识库放在本仓库 **`docs/notes/research/topics/english/`**（融入现有 MkDocs
站点，跟随 research 目录的既有约定），结构：

```text
docs/notes/research/topics/english/
├── index.md                        # 英语学习入口：scraps 主路径 + 特殊主题列表
└── hollow-knight/                   # HK 主题阅读材料
    ├── index.md                     # 主题落地页
    ├── characters.md
    ├── locations.md
    ├── lore.md
    ├── items.md
    ├── dialogues.md
    └── resources.md
```

## Tasks

### 项目搭建（已完成的历史记录）

- [x] 在 `docs/notes/research/topics/english/` 建立目录结构
- [x] 所有页面补齐 research 约定 frontmatter：`title`、`tags`、`categories`
- [x] 在 `docs/notes/research/index.md` 的 **Learning Plans** 分类下注册
  English 条目（链接 `./topics/english/index.md`）
- [x] 页面间使用相对链接，遵循仓库约定

### 内容模板与体系（已完成）

- [x] 建立统一内容模板（Original / Vocabulary / Grammar / Pronunciation /
  Shadowing / Summary / Speaking / Personal Notes）—— `hollow-knight/*.md`
  内模板

### HK 主题阅读（保留，以后再做）

- [ ] 阅读一个小主题（Characters / Locations / Lore / Items / Dialogues），
  内容整理进 `hollow-knight/` 对应文件
- [ ] AI 辅助：解释句子 / 词汇 / 语法、生成例句、区分近义词
- [ ] 每个主题用英文回答核心问题（不看原文），如 Who is the Pale King?
- [ ] 每主题写英文总结：3–5 句 → 100–150 词 → 长期 300–500 词
- [ ] 记录常见表达错误

## Notes

- 核心原则（通用部分，与 English Scraps 共用）：

  1. 兴趣优先 — 不为学英语而选不感兴趣的材料
  1. 输入必须转输出 — 看懂不等于会说（Read → Understand → Speak → Write）
  1. 不追求完美口音 — 目标是清晰、自然、容易被理解

- 与仓库的结合点：research 目录已有成熟的 frontmatter / disclaimer / 命名
  惯例，英语学习直接复用

- 源文件：`~/Work/tmp/hollow_knight_english_reader_plan.md`（详细设计参考）
