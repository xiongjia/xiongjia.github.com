---
title: shadcn/ui 源码阅读指南
tags:
  - research
  - tech
categories:
  - dev
---

> **⚠️ 免责声明**: 本文档由 AI 自动生成，仅供参考学习使用。
> - 依据 shadcn/ui 仓库: branch `main`

> **学习前先克隆项目:**
> ```bash
> cd docs/research/external
> git clone --depth 1 https://github.com/shadcn-ui/ui.git shadcn-ui
> ```

---

## 项目概述

shadcn/ui 不是传统的 npm 组件库，而是一个 **CLI 工具**，它将组件源码直接复制到你的项目中，让你完全拥有和自定义组件代码。

- GitHub: https://github.com/shadcn-ui/ui
- 官网: https://ui.shadcn.com
- 本地路径: `docs/research/external/shadcn-ui`
- 核心依赖: Radix UI (无样式行为基元) + Tailwind CSS (样式)

## 核心理念

```
传统的 npm 包                    shadcn/ui
─────────────                    ─────────
npm install @acme/ui             npx shadcn add button
    ↓                               ↓
node_modules 黑盒               components/ui/button.tsx (你的代码)
    ↓                               ↓
import { Button } from ...      import { Button } from "@/components/ui/button"
    ↓                               ↓
无法修改源码                     完全可控，直接改
```

## 项目结构

```
shadcn-ui/
├── packages/
│   ├── shadcn/                      # CLI 工具 (核心)
│   │   └── src/
│   │       ├── index.ts            # CLI 入口
│   │       ├── commands/           # CLI 命令 (init, add, build, diff)
│   │       ├── registry/           # 组件注册表系统
│   │       ├── schema/             # components.json 配置 schema
│   │       ├── utils/              # 工具函数
│   │       ├── mcp/                # MCP 协议支持
│   │       └── migrations/         # 配置迁移
│   └── tests/                      # 测试
├── apps/v4/                        # 文档网站 (Next.js)
│   ├── registry/                   # 组件注册表 (JSON)
│   ├── registry.json               # 默认注册表配置
│   ├── components/                 # 文档站用的组件
│   └── content/                    # MDX 文档
├── templates/                      # 模板项目
│   ├── next-app/ next-monorepo/
│   ├── vite-app/ vite-monorepo/
│   ├── astro-app/ astro-monorepo/
│   └── start-app/ start-monorepo/
└── skills/                         # AI 辅助技能
```

## 学习阶段

### 阶段 1: 体验使用

1. **初始化一个项目**
   ```bash
   npx shadcn@latest init
   ```

2. **添加组件**
   ```bash
   npx shadcn@latest add button
   npx shadcn@latest add dialog
   ```

3. **理解生成的文件**
   - `components.json` — 项目配置 (tailwind config, aliases, registry url)
   - `components/ui/` — 复制的组件源码
   - `lib/utils.ts` — `cn()` 工具函数 (tailwind-merge + clsx)

### 阶段 2: 理解 CLI 架构

> 核心代码: `packages/shadcn/src/`

4. **CLI 入口**
   - 阅读 `packages/shadcn/src/index.ts` — 了解 commander 如何注册命令
   - 工作原理: 用 `@commander-js/extra-typings` 构建 CLI
   - TypeScript 编译为 ESM (`"type": "module"`)

5. **核心命令**
   | 文件 | 命令 | 用途 |
   |------|------|------|
   | `commands/init.ts` | `shadcn init` | 初始化项目配置 |
   | `commands/add.ts` | `shadcn add` | 添加组件 |
   | `commands/build.ts` | `shadcn build` | 构建 registry |
   | `commands/diff.ts` | `shadcn diff` | 对比组件差异 |
   | `commands/migrate.ts` | `shadcn migrate` | 迁移配置 |
   | `commands/search.ts` | `shadcn search` | 搜索组件 |

### 阶段 3: 理解 Registry 系统

> 核心代码: `packages/shadcn/src/registry/`

6. **Registry 是什么**
   - 一个 JSON 配置文件，定义所有可用的组件、依赖、文件列表
   - 默认 registry: `https://ui.shadcn.com/r/styles/default/registry.json`
   - 本地 registry: `apps/v4/registry.json`

7. **关键模块**
   | 文件 | 用途 |
   |------|------|
   | `registry/api.ts` | 从 URL 或本地加载 registry |
   | `registry/loader.ts` | 加载组件文件 |
   | `registry/resolver.ts` | 解析组件依赖树 |
   | `registry/parser.ts` | 解析 TypeScript/JSX 源码 |
   | `registry/builder.ts` | 构建最终输出 |
   | `registry/schema.ts` | Zod schema 定义 |

8. **Registry 工作流程**
   ```
   shadcn add button
       ↓
   加载 registry.json → 解析 button 的定义
       ↓
   递归解析依赖 (button → @radix-ui/react-slot)
       ↓
   从 registry 获取每个文件的源码
       ↓
   转换为目标格式 (TypeScript/JavaScript)
       ↓
   写入 components/ui/button.tsx
       ↓
   安装 npm 依赖 (如 react-aria, class-variance-authority)
   ```

### 阶段 4: 理解组件设计

9. **组件架构**
   - 基元层: Radix UI / React Aria (无样式、可访问的行为)
   - 样式层: Tailwind CSS + `class-variance-authority` (变体)
   - 组合层: `cn()` = `clsx` + `tailwind-merge`

10. **阅读示例组件**
    - `apps/v4/components/ui/button.tsx` — 简单组件
    - `apps/v4/components/ui/dialog.tsx` — 复合组件
    - `apps/v4/components/ui/form.tsx` — 结合 react-hook-form

### 阶段 5: 理解模板系统

11. **模板项目** (`templates/`)
    - `next-app` → Next.js App Router
    - `vite-app` → Vite + React SPA
    - `astro-app` → Astro
    - `start-app` → TanStack Start
    - Monorepo 变体: `*-monorepo/`

12. **模板如何工作**
    - 每个模板定义框架特定的配置
    - `shadcn init` 使用对应模板初始化项目
    - 模板包含惯例文件: `components.json`, `tailwind.config`, `lib/utils.ts`

### 阶段 6: 进阶了解

13. **diff 命令实现**
    - `commands/diff.ts` — 对比本地组件和上游 registry 的差异
    - 类似 `git diff`，帮助你追踪上游更新

14. **build 命令**
    - `commands/build.ts` — 构建自定义 registry
    - 用于部署私有组件库

15. **MCP 协议**
    - `mcp/` — Model Context Protocol 集成
    - 让 AI 助手通过 MCP 服务器管理 shadcn/ui 组件

## 关键概念

| 概念 | 说明 |
|------|------|
| **Registry** | 组件的 JSON 清单，列出所有可用组件 |
| **components.json** | 项目级配置，记录别名、样式、registry 地址 |
| **cn()** | `clsx` + `tailwind-merge` 的组合函数 |
| **Class Variance Authority** | 类型安全的组件变体 API |
| **Radix UI** | 无样式可访问 UI 基元库 |
| **Tailwind CSS** | 原子化 CSS 框架 |

## 技术栈

| 技术 | 用途 |
|------|------|
| **TypeScript** | 语言 |
| **Commander.js** | CLI 框架 |
| **Zod** | Schema 验证 |
| **tsup** | TypeScript 构建 |
| **Vitest** | 测试 |
| **Next.js** | 文档网站 |
| **Turbo** | Monorepo 管理 |
| **Radix UI / React Aria** | 组件基元 |
| **Tailwind CSS** | 样式 |
