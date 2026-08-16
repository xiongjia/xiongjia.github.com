---
title: Improve shadcn/ui Research
created: 2026-08-17
tags: [shadcn, research, improve, frontend]
---

# Improve shadcn/ui Research

## Goal

改进现有的 shadcn/ui research 笔记（`docs/notes/research/topics/shadcn-ui/index.md`）：
基于 shadcn/ui 仓库 `main` 分支，核对 CLI 与 Registry 分发系统的最新实现，
补全组件生成流程、样式/主题机制，修正过时内容。

## Tasks

- [ ] **核对上游版本**

  - 确认笔记依据的 commit 与最新 `main` 的差距
  - diff CLI 相关代码变更（registry、init、add 命令行为）

- [ ] **补全/修正内容**

  - Registry 分发系统：组件注册表结构、依赖解析、版本管理
  - CLI 工作流：`init` → `add` 的完整流程（配置、样式、别名）
  - 主题/样式机制（CSS variables、Tailwind 配置、dark mode）
  - 修正过时的命令示例与代码片段

- [ ] **补充实操示例**

  - 本地跑一次 `npx shadcn@latest init/add` 观察产物与文件结构
  - 记录 Registry 拉取的 URL 结构与组件依赖树

- [ ] **维护索引**

  - 确保 `docs/notes/research/index.md` 中 shadcn/ui 的描述与实际一致

## Notes

- 现有笔记 7.6K，重点核对 CLI 与 Registry 是否变化（shadcn 近期迭代较快）
- 与前端相关 collection 页（frontend.md）保持交叉引用一致

## References

- [shadcn/ui Topic](../../docs/notes/research/topics/shadcn-ui/)
- [shadcn/ui 仓库](https://github.com/shadcn-ui/ui)
