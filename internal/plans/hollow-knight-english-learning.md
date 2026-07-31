---
title: 英语学习计划 — Hollow Knight English Reader
created: 2026-07-31
tags: [english, learning, hollow-knight, pronunciation, vocabulary, shadowing]
---

# 英语学习计划 — Hollow Knight English Reader

## Goal

把 **Hollow Knight** 作为长期英语学习主题，在本仓库建立英语学习知识库
（Reading / Vocabulary / Pronunciation / Shadowing / Speaking / Writing），
把游戏兴趣转化为长期的英语能力，最终目标是：**英语不再是一门独立课程，
而成为获取知识和做项目的工具。**

## 背景与关键限制

- 游戏兴趣驱动、世界观完整、文本量适中、词汇反复出现 → 适合长期坚持
- **重要限制**：Hollow Knight 本身几乎没有正常的英语配音 → 适合做英语阅读和
  词汇材料，**不应该作为主要的 Shadowing 材料**
- 发音 / Shadowing 素材使用两层来源：
  - 兴趣驱动：Hollow Knight lore explained / full lore / story explained /
    analysis 等有清晰英语旁白的视频
  - 标准发音：BBC Learning English、VOA Learning English、English with Lucy、
    Rachel's English（避免只模仿一个 YouTuber 的口音）

## 内容位置

知识库放在本仓库 **`docs/notes/research/english/`**（融入现有 MkDocs 站点，
跟随 research 目录的既有约定），预计结构：

```text
docs/notes/research/english/
├── 00-english.md                    # 学习总览 / Dashboard 入口
├── pronunciation.md                 # 发音体系（Ear / Mouth / Rhythm 三阶段）
├── pronunciation-mistakes-log.md    # 易错音长期记录
├── shadowing.md                     # Shadowing 方案与素材清单
├── vocabulary.md                    # Vocabulary 卡片体系说明
├── weekly-review.md                 # 每周复习 / 月度回顾
└── hollow-knight/                   # HK 主题阅读材料
    ├── characters.md
    ├── locations.md
    ├── lore.md
    ├── items.md
    ├── dialogues.md
    └── resources.md
```

## Tasks

### 项目搭建（贴合本仓库）

- [ ] 在 `docs/notes/research/english/` 建立上述目录结构
- [ ] `00-english.md` 遵循 research 命名惯例（`00-*.md`），作为总览 / Dashboard
  入口（Today's Practice / Hollow Knight / Vocabulary / Pronunciation /
  Shadowing / Speaking / Weekly Review 导航）
- [ ] 所有页面补齐 research 约定 frontmatter：`title`、`tags`、`categories`，
  并带 AI 免责声明（参考 `docs/notes/research/docs/jellyfin/00-jellyfin.md`）
- [ ] 在 `docs/notes/research/index.md` 的 **Learning Plans** 分类下注册
  English 学习计划条目
- [ ] 页面间使用相对链接（如 `./hollow-knight/lore.md`），遵循仓库约定

### 内容模板与体系

- [ ] 建立统一内容模板（Original / Vocabulary / Grammar / Pronunciation /
  Shadowing / Summary / Speaking / Personal Notes）
- [ ] 建立 Vocabulary 卡片体系：发音、重音、词性、常见含义、HK 中的含义、
  游戏原句、自己造句
- [ ] 建立 Pronunciation Mistakes Log（Problem / Reason / Practice / Result）
- [ ] 建立 Weekly Review 模板（本周词汇 / 发音错误 / Shadowing 录音 / Summary）

### Pronunciation 发音体系（三阶段）

- [ ] Phase 1 — Ear：训练听辨元音、辅音、长短音、重音；重点混淆对
  `ship/sheep`、`live/leave`、`full/fool`、`rice/lice`、`west/vest`、
  `three/tree`
- [ ] Phase 2 — Mouth：一次重点解决一个音，优先 `th`、`r`、`l`、`v`、`w`
- [ ] Phase 3 — Rhythm：Word Stress、Sentence Stress、Weak Forms、Linking、
  Reduction、Pausing（如 `I want to go.` 不逐词等重）
- [ ] 学习基本 IPA
- [ ] 记录自己的易错音，长期维护 Mistakes Log

### Shadowing 方案

- [ ] 每天 5–10 句、每句 5–10 次、总计 10–20 分钟
- [ ] 流程：Listen → Listen again → Read transcript → Shadow → Record →
  Compare → Repeat
- [ ] 观察点：音是否准确、重音/节奏/停顿是否一致、连读是否自然
- [ ] 素材两层：第一层兴趣驱动（Lore 解说视频），第二层标准发音（BBC / VOA /
  Lucy / Rachel's English），收集进 `hollow-knight/resources.md`

### Reading / Vocabulary

- [ ] 每天阅读一个小主题（Characters / Locations / Lore / Items / Important
  Dialogues），内容整理进 `hollow-knight/` 对应文件
- [ ] 每天积累 5–10 个词（含 HK 语境、游戏原句、自己的造句）
- [ ] AI 辅助：解释句子 / 词汇 / 语法、生成例句、区分近义词、生成复习题

### Speaking / Writing 输出

- [ ] 每个主题用英文回答核心问题（不看原文），如 Who is the Pale King?
- [ ] 每主题写英文总结：阶段一 3–5 句 → 阶段二 100–150 词 → 长期 300–500 词
- [ ] 每周一次 3–5 分钟英文复述
- [ ] 每月一次长篇总结（可记入 weekly-review.md）
- [ ] 记录常见表达错误

### 每日 / 每周习惯

- [ ] 每天 30–45 分钟：10 min Reading / 10 min Vocabulary / 10 min
  Shadowing / 5 min Speaking / 5 min Writing
- [ ] 时间少时保底：10 min Reading + 10 min Shadowing（最重要的是持续）
- [ ] 周一至周四：阅读一个小主题 + 学 5–10 个词 + Shadowing 5–10 句
- [ ] 周五：复习本周词汇、发音错误、Shadowing 录音
- [ ] 周末：一篇英文 Summary + 一次 3–5 分钟 Speaking

### 与仓库工具链的集成改进

- [ ] **draft 机制**：WIP 学习页面先加 `draft: true` frontmatter（本地
  `poe server` 可见，生产构建自动过滤，见 `plugins/draft_filter.py`），
  完成后移除
- [ ] **AI 辅助落地**：学习笔记先以 `*-draft.md` 草稿形式在本地迭代，成熟后
  定稿；利用 pi 对话直接生成/复习内容（词汇卡片、复习题、口语纠错）
- [ ] **格式规范**：笔记保持 mdformat 兼容（`poe fmt` 会格式化 docs/），
  frontmatter 与列表风格与现有 research 笔记一致
- [ ] **Moment 打卡（可选）**：每日练习可用 `poe create-moment` 发一条
  微记录，形成时间轴

### 长期路线

- [ ] Phase 1（0–1 月）：掌握基本 IPA、找出主要发音问题、开始每天 Shadowing、
  建立 Vocabulary 系统
- [ ] Phase 2（1–3 月）：阅读 HK Wiki、每天 5–10 句 Shadowing、每周一次英文
  Summary、每周一次 Speaking
- [ ] Phase 3（3–6 月）：连续阅读英文资料、不依赖中文翻译、能用英语讲 HK
  Lore、建立自己的高频词汇库、发音明显更稳定
- [ ] Phase 4（6–12 月）：逐渐减少专门学习，将英语融入日常技术学习（英文
  技术文档、英文视频、用英语记录项目）

## Notes

- 核心学习模型：

  ```text
  Read → Understand → Collect Vocabulary → Listen → Shadow → Speak → Write
  ```

- 核心原则：

  1. 兴趣优先 — 不为学英语而选不感兴趣的材料
  1. 输入必须转输出 — 看懂不等于会说（Read → Understand → Speak → Write）
  1. 发音必须录音 — 不要只依赖自己的感觉（Listen → Speak → Record → Compare）
  1. 少量长期重复 — 每天 10 句 Shadowing 比偶尔一次练两小时更有效
  1. 不追求完美口音 — 目标是清晰、自然、容易被理解

- 与仓库的结合点：research 目录已有成熟的 frontmatter / disclaimer / 命名
  惯例（见 `docs/notes/research/docs/jellyfin/00-jellyfin.md` 与
  `docs/notes/research/index.md` 的 Learning Plans 分类），英语学习直接复用

- 源文件：`~/Work/tmp/hollow_knight_english_reader_plan.md`（详细设计参考）
