---
hide:
  - navigation
title: English Scraps 使用指南
tags:
  - research
  - tech
  - english
  - scraps
categories:
  - dev
---

# English Scraps — 使用指南

日常英语碎片（生词 / 语法 / 难句 / 搭配）的收集、整理与回顾，
动作都在 **enu-organize skill** 下（动作用英文：`add` / `arch` / `quiz` / `review`）。

## 三步流程

1. **📥 收集** — `uv run poe enu add "内容"`，或 pi 里 `/skill:enu-organize add <内容>`
1. **🧹 整理** — 攒够一批（inbox ≥ 15 条 / ≥ 2 周 / 主动）→ `/skill:enu-organize arch`
1. **👀 回顾** — `/skill:enu-organize quiz [范围]` / `review <tag>`

## 归档

- **上次整理**：2026-08-12

- 按 **ISO 周**归档到 `archive/<YYYY-www>.md`（如 `2026-w33.md`），卡片落进对应
  周文件；只在有归档的周生成。周列表与字段说明见 [archive/](./archive/)；
  周列表在 [英语学习首页](../index.md) 也有一份。

## 常用命令

| 动作 | 命令                                                    |
| ---- | ------------------------------------------------------- |
| 收集 | `poe enu add "内容"` / `/skill:enu-organize add <内容>` |
| 整理 | `/skill:enu-organize arch`                              |
| 回顾 | `/skill:enu-organize quiz [范围]` / `review <tag>`      |
| 查看 | 站内全文搜索 / [archive/ 周文件](./archive/)            |

> 完整流程（分类规则、去重、卡片模板）在 skill 正文：
> `.pi/skills/enu-organize/SKILL.md`，日常疑问回本页查。
