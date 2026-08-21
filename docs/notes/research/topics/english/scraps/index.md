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

- **上次整理**：2026-08-21

- 按 **ISO 周**归档到 `archive/<YYYY-www>.md`（如 `2026-w33.md`），卡片落进对应
  周文件；只在有归档的周生成。周列表与字段说明见 [archive/](./archive/)；
  周列表在 [英语学习首页](../index.md) 也有一份。

## 常用命令

| 动作 | 命令                                                    |
| ---- | ------------------------------------------------------- |
| 收集 | `poe enu add "内容"` / `/skill:enu-organize add <内容>` |
| 整理 | `/skill:enu-organize arch`                              |
| 回顾 | `/skill:enu-organize quiz [范围]` / `review <tag>`      |
| 导出 | `poe enu export`（Anki，可选）                          |
| 查看 | 站内全文搜索 / [archive/ 周文件](./archive/)            |

## Anki 导出（可选）

复习完全可选：归档周文件才是知识库本体，不导出 Anki 也能正常使用；
导出只是把卡片搬到 Anki 复习。**导入是手工的**（不做 AnkiConnect 自动上传）。

- **生成**：`poe enu export` → 导出所有 `status: new` 的卡片，生成
  `.anki/english-scraps-<日期>.apkg`（目录 git-ignored，不提交）
  - `--format csv`：兜底 CSV（`.anki/<type>.csv`，UTF-8 BOM，每 type 一个文件，
    首字段 = 去重 key）
  - `--type word` / `--tag technical`：按类型 / 标签筛选；`--all`：全部状态；
    `--dry-run`：只生成不改状态
- **导入**：双击 `.apkg` 用 Anki 桌面版导入（File → Import），或传到手机用
  AnkiDroid 打开；登录 AnkiWeb 账号同步即可上手机（AnkiWeb 无直接上传接口）
- **CSV 兜底**：Anki → File → Import 选 CSV，勾选 *Update existing notes when
  first field matches*，按去重 key 更新，重复导入不产生重复卡；
  需导入到首字段为 `key` 的 note type（去重键在第一列）
- **去重三层兜底**：归档按 `type:关键词` 去重 + 导出只选 `status: new` +
  导入按 guid / key 更新
- **状态流转**：导出成功后卡片 `status: new → learning`（幂等：重复导出只更新
  不重复）；`mastered` 手动改；Anki 里删卡/改卡不回写 archive

> 完整流程（分类规则、去重、卡片模板）在 skill 正文：
> `.pi/skills/enu-organize/SKILL.md`，日常疑问回本页查。
