---
hide:
  - navigation
title: shadcn/ui 环境与初始化
tags:
  - research
  - tech
  - shadcn
  - frontend
categories:
  - dev
---

# :material-rocket-launch: 环境与初始化

> **本页目的：** 把 shadcn/ui v4 跑起来 —— 技术栈定案（pnpm + Vite 8 +
> Tailwind v4 + TypeScript）、创建项目、接入 Tailwind、`init` 完整流程与
> components.json 逐字段解读。全部基于本机实测（macOS arm64）。
>
> 本页是 shadcn/ui 实用系列第 1 篇，下一篇见 [组件添加与基本使用](./components.md)。

## 1. 技术栈定案

| 层            | 技术                  | 版本     | 说明                                                      |
| ------------- | --------------------- | -------- | --------------------------------------------------------- |
| 运行时        | Node                  | v24.16.0 | shadcn CLI 要求 **Node >= 20.18.1**（engines 实测）       |
| 包管理器      | pnpm                  | 11.4.0   |                                                           |
| 构建          | Vite（react-ts 模板） | 8.2.2    | rolldown 内核                                             |
| UI            | React                 | 19.2.8   |                                                           |
| 语言          | TypeScript            | 7.0.2    |                                                           |
| 样式          | Tailwind CSS v4       | 4.3.3    | CSS-first，**无 tailwind.config.js**                      |
| Tailwind 插件 | @tailwindcss/vite     | 4.3.3    | vite 侧接入                                               |
| 动画          | tw-animate-css        | 1.4.0    | 组件动效（init 自动写入 index.css）                       |
| shadcn CLI    | shadcn                | 4.19.0   | v4 架构：`init 时把 shadcn 包本身装入项目依赖`            |
| 基元          | @base-ui/react        | 1.7.0    | **Base UI**（v4 默认 style=base-nova，取代旧版 Radix UI） |

## 2. 创建项目

```bash
pnpm create vite shadcn-demo --template react-ts
cd shadcn-demo
pnpm install
```

升级模板自带的 TypeScript（~6.0.2 已过时，跟随当前主版本 ^7.0.2），并安装 Tailwind v4 相关依赖：

```bash
# 手动改 package.json: "typescript": "~6.0.2" → "^7.0.2"，然后：
pnpm install
pnpm add tailwindcss @tailwindcss/vite tw-animate-css
pnpm exec tsc --version   # → Version 7.0.2
```

## 3. 接入 Tailwind v4（CSS-first）

v4 不生成 `tailwind.config.js`，配置在 CSS 与 vite 插件里完成：

**`vite.config.ts`** —— 加 `@tailwindcss/vite` 插件 + `@` 路径别名：

```ts
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
})
```

**`tsconfig.app.json`** —— compilerOptions 加 paths（相对路径写法）：

```json
"moduleResolution": "bundler",
"paths": { "@/*": ["./src/*"] },
```

**`src/index.css`** —— 至少先有：

```css
@import "tailwindcss";
@import "tw-animate-css";
```

> ⚠️ **坑 1：`init` 不自动装 Tailwind。** 全新项目直接 `init` 会失败：
> 报 `No Tailwind CSS configuration found …`（Tailwind 未装）与
> `Could not find valid path aliases …`（别名未配）。必须先完成本节三步。

## 4. `init` 初始化

```bash
pnpm dlx shadcn@latest init -d    # -d = --defaults，免交互
```

实测流程输出：

```
- Preflight checks.            ✔
- Verifying framework.         ✔ Found Vite.
- Validating Tailwind CSS.     ✔ Found v4.
- Validating import alias.     ✔
- Writing components.json.     ✔
- Checking registry.           ✔
- Installing dependencies.     ✔
- Updating files.
✔ Created 2 files:
  - @/components/ui/button.tsx
  - @/lib/utils.ts
```

`init -d` **会额外把 shadcn 包本身加进项目 dependencies**（实测 v4.19.0），
并自动安装：`@base-ui/react`（基元）、`clsx` + `tailwind-merge`（cn()）、
`class-variance-authority`（CVA）、`lucide-react`（图标）、
`@fontsource-variable/geist`（字体）。

## 5. components.json 逐字段

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "base-nova",          // 样式族：v4 默认，基于 Base UI
  "rsc": false,                  // React Server Components（Next.js 项目为 true）
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/index.css",
    "baseColor": "neutral",      // 基础色板
    "cssVariables": true,        // 全部走 CSS 变量（oklch）
    "prefix": ""
  },
  "iconLibrary": "lucide",       // 图标库
  "rtl": false,
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "menuColor": "default",        // 菜单/侧边栏外观
  "menuAccent": "subtle",
  "registries": {}               // 自定义/extra registry（默认空=用内置 @shadcn）
}
```

## 6. 生成的文件结构

```
src/
├── components/ui/          # 复制的组件源码（每个组件一个 .tsx）
│   ├── button.tsx          # init 自带的基础组件
│   └── …                   # 之后 add 的组件
├── lib/
│   └── utils.ts            # cn() = clsx + tailwind-merge（合并 Tailwind 类）
├── index.css               # init 会增补以下内容：
│   @import "tailwindcss";
│   @import "tw-animate-css";
│   @import "shadcn/tailwind.css";        # shadcn 主题样式的入口
│   @import "@fontsource-variable/geist"; # Geist 字体（默认主题字体）
│   @custom-variant dark (&:is(.dark *)); # dark 变体
│   @theme inline { … }                   # 语义色映射（--color-* → --* 变量）
│   :root { … }                           # oklch 色板 + --radius 组合（sm…4xl）
│   .dark { … }                           # dark 模式色板
```

`@/lib/utils.ts`（init 生成）：

```ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

## 7. 常见坑（实测）

| 坑                         | 现象                                                                                                  | 处理                                                                   |
| -------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Tailwind/别名未配就 init   | `No Tailwind CSS configuration found` / `Could not find valid path aliases`                           | 按第 3 节先配好                                                        |
| 组件落盘到项目根 `@/` 目录 | v4.19 在 Vite 8 solution-style tsconfig 下写出 `./@/components/ui/`（别名未正确解析，未跟随后续修复） | 手动 `mv` 到 `src/components/ui/`（组件代码可正常构建）；跟踪 CLI 修复 |
| `add form` 静默无产出      | v4 的 `form` registry 项 files 为空（stub），实际表单组件是 `field`                                   | 用 `add field`（见下一篇）                                             |

## 8. 参考链接

| 资源          | 链接                                                                                         |
| ------------- | -------------------------------------------------------------------------------------------- |
| shadcn 文档   | [https://ui.shadcn.com/docs](https://ui.shadcn.com/docs)                                     |
| Vite 安装指南 | [https://ui.shadcn.com/docs/installation/vite](https://ui.shadcn.com/docs/installation/vite) |
| Base UI       | [https://base-ui.com/](https://base-ui.com/)                                                 |
| Tailwind v4   | [https://tailwindcss.com/docs](https://tailwindcss.com/docs)                                 |

→ 下一站：[组件添加与基本使用](./components.md)
