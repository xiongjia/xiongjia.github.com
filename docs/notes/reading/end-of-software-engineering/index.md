---
title: The End of Software Engineering（整理完成）
tags: [reading, end-of-software-engineering, paper]
categories: [reading]
hide: [navigation]
---

# The End of Software Engineering: How AI Agents Are Fundamentally Restructuring the Software Paradigm

- **类型**: paper（论文）
- **状态**: organized（整理完成）
- **作者**: Zhenfeng Cao（Lingxi Intelligent Investment (Shenzhen) Development Co., Ltd.）
- **出处**: arXiv preprint <https://arxiv.org/html/2606.05608v1>（arXiv:2606.05608v1 [cs.SE]，2026-06-04 投稿 / 06-05 正文标注日期）
- **整理完成日期**: 2026-09-03
- **读完日期**: （由用户读完后再手工补注）

## 全文主线（核心论点）

- **核心主张**：AI agents（LLM 作为主要推理引擎，代码只是按需生成、用后即弃的「临时工具」）
  不是现有范式内的增量改进，而是对软件范式的**根本重构**——其程度堪比从 analog circuits
  到 stored-program computers 的转变。传统软件里代码承载决策逻辑；agentic 系统里代码是
  LLM 推理循环的 ephemeral tooling
- **三大 central claims**：
  1. **First-Principles Necessity** — agentic 范式不是市场偏好，而是复杂度缩放定律下的必然：
     LLM 容量随训练算力增长，把解算能力从固定的人类认知上限中解耦
  1. **Paradigm Shift, Not Optimization** — 从 "AI →Software →Result" 到 "Agent →Result"，
     软件制品不再是必要中间环节；这是软件交付史上继 license→SaaS 之后的**第三次范式转移**
     （终点是作者所称 Agent-as-a-Service / AaaS）
  1. **Emergent Discipline** — Agentic Engineering 正在成为独立学科：实践者不是「更好的
     程序员」，而是 intent architects、agent coordinators、outcome auditors
- **论证路线**：§2 第一性原理（两个形式化定义 + 指数复杂度论证）→ §3 三代交付史与
  AaaS 定位 → §4 Agentic Engineering 学科定义与人的角色重塑 → §5 实证证据与局限
  （SWE-bench Verified / Hermes / LangChain 试点 / EvoClaw 落差）→ §6 四阶段演进路线图 →
  §7 实践者 / 研究者 / 组织建议 → §8 结论
- **总体判断**：今天是「human-in-the-loop、agent-in-the-driver's-seat」的 augmentation
  时代；完全自主的软件工程仍是多年研究挑战——「The old software engineering is ending;
  the new one has already begun.」

## 阅读笔记

- [笔记（跨部分概念 / 重要参考 / 存疑与待查线索）](./notes.md)

## 章节

素材（本地 pdf `2606.05608v1.pdf`）经脚本按页分组预提取为 8 个文件
（source-01…08.txt，拆分点落在正文句子中间，与论文章节不完全对齐），每文件一页：

| 页码      | 论文范围（大致）                       | 摘要                                                  |
| --------- | -------------------------------------- | ----------------------------------------------------- |
| part-0001 | 标题页 + Abstract + §1 前段            | [摘要与引言：范式重构的宣告](./part-0001.md)          |
| part-0002 | §1 后段 + §2 First-Principles Analysis | [第一性原理：两个形式化模型](./part-0002.md)          |
| part-0003 | §3.1–3.2                               | [三代交付史与 AI→Software→Result](./part-0003.md)     |
| part-0004 | §3.3 + §4                              | [Agent→Result 与 Agentic Engineering](./part-0004.md) |
| part-0005 | §5                                     | [实证证据与 EvoClaw 落差](./part-0005.md)             |
| part-0006 | §6（表 3 + 6.1–6.3）                   | [四阶段路线图（前段）](./part-0006.md)                |
| part-0007 | §6.3 后段–§6.4 + §7.1–7.2              | [路线图后段与建议](./part-0007.md)                    |
| part-0008 | §7.3 + §8 + 参考文献                   | [组织建议、结论与文献](./part-0008.md)                |
