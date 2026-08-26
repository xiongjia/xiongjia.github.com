---
hide:
  - navigation
title: shadcn/ui 实用研究（从环境到基本使用）
tags:
  - research
  - tech
  - shadcn
  - frontend
categories:
  - dev
---

# :material-layers: shadcn/ui

shadcn/ui 实用研究 —— **v4 新版从环境搭建到基本使用的实操路线**。全部内容
基于本机实测（Node v24.16.0 / pnpm 11.4.0 / Vite 8.2.2 / Tailwind CSS v4 /
TypeScript 7.0.2 / shadcn CLI 4.19.0，Vite react-ts 模板，macOS arm64）。

- 官方文档: [https://ui.shadcn.com/docs](https://ui.shadcn.com/docs)
- 安装指南: [https://ui.shadcn.com/docs/installation](https://ui.shadcn.com/docs/installation)
- 前端收藏页: [Collection Frontend](../../../collection/frontend.md)

> 本主题是**实用研究**：不读 shadcn/ui 源码，而是「装起来、用起来、定制起来」。
> 旧版"源码阅读指南"已清除替换。

## Sub Topics

| 阅读顺序 | 主题                                  | 描述                                                                                                                  |
| -------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1        | [环境与初始化](./setup.md)            | 技术栈定案（pnpm + Vite 8 + Tailwind v4 + TypeScript）、创建项目、接入 Tailwind、`init` 流程与 components.json 逐字段 |
| 2        | [组件添加与基本使用](./components.md) | `add` 用法、依赖自动解析、常用组件清单与最小示例、Base UI 新范式（render prop / Field 组合）                          |
| 3        | [进阶玩法](./advanced.md)             | 组件更新（diff/overwrite）、主题定制（oklch 变量/radius/dark）、表单集成（RHF + zod）、registry 机制与框架差异        |

## 推荐阅读顺序

1. **环境与初始化** → [环境与初始化](./setup.md)：先把项目跑起来——TypeScript 升级、
   Tailwind v4 接入、`init` 成功，得到 components.json 和 button.tsx
1. **组件添加与基本使用** → [组件添加与基本使用](./components.md)：`add` 常用组件、
   理解依赖自动解析，把 button/card/dialog/field 用起来
1. **进阶玩法** → [进阶玩法](./advanced.md)：更新组件、主题定制、表单集成、
   自定义 registry，以及 Vite 脚手架下的实测坑

## 版本快照（2026-08-26 实测）

| 组件         | 版本                 | 备注                                |
| ------------ | -------------------- | ----------------------------------- |
| Node         | v24.16.0             | shadcn CLI 要求 Node >= 20.18.1     |
| pnpm         | 11.4.0               | 包管理器                            |
| Vite         | 8.2.2                | react-ts 模板，rolldown 构建        |
| React        | 19.2.8               |                                     |
| TypeScript   | 7.0.2                | （跟随当前 TypeScript 主版本）      |
| Tailwind CSS | 4.3.3                | v4 CSS-first，无 tailwind.config.js |
| shadcn CLI   | 4.19.0               | v4 架构，style=base-nova            |
| 基元         | @base-ui/react 1.7.0 | **Base UI**（非旧版 Radix UI）      |
| 图标         | lucide-react 1.34.0  | components.json 的 iconLibrary      |
| 动画         | tw-animate-css 1.4.0 | 组件动效（init 写入 index.css）     |

## 实测要点（详细见各篇）

- `init` 前必须先装 Tailwind v4 并配好 `@/*` 别名，否则报
  `No Tailwind CSS configuration found` / `Could not find valid path aliases`
- paths 别名用相对写法（`"./src/*"`）
- v4.19 在 Vite 8 solution-style tsconfig 下，组件会**落盘到项目根的字面
  `@/components/ui/`**，需手动归位到 `src/`（组件代码本身可正常构建）
- v4 的 `form` registry 项是空 stub，真实表单组件是 `field`（Base UI Field）
- Base UI 用 `render={<Button/>}` 替代 Radix 的 `asChild`

## 相关笔记

- [Collection Frontend](../../../collection/frontend.md)：前端/React 资源收藏
- [Research 索引](../../index.md)：研究笔记总目录
