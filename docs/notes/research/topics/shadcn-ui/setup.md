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
> Tailwind v4 + TypeScript）、创建项目、接入 Tailwind、`init` 完整流程、
> components.json 逐字段解读与启动验证。全部基于本机实测（macOS arm64）。
>
> 本页是 shadcn/ui 实用系列第 1 篇，下一篇见 [组件添加与基本使用](./components.md)。

## 1. 技术栈定案

| 层            | 技术                  | 版本     | 说明                                                               |
| ------------- | --------------------- | -------- | ------------------------------------------------------------------ |
| 运行时        | Node                  | v24.16.0 | shadcn CLI 要求 **Node >= 20.18.1**（engines 实测）                |
| 包管理器      | pnpm                  | 11.25.0  |                                                                    |
| 构建          | Vite（react-ts 模板） | 8.2.2    | rolldown 内核                                                      |
| UI            | React                 | 19.2.8   |                                                                    |
| 语言          | TypeScript            | 7.0.2    | 创建后随首次安装升到 ^7.0.2（模板自带 ~6.0.2）                     |
| 样式          | Tailwind CSS v4       | 4.3.3    | CSS-first，**无 tailwind.config.js**                               |
| Tailwind 插件 | @tailwindcss/vite     | 4.3.3    | vite 侧接入                                                        |
| 动画          | tw-animate-css        | 1.4.0    | 组件动效（init 自动写入 index.css）                                |
| shadcn CLI    | shadcn                | 4.20.1   | 固定版本 `-D` 装入项目，本地 CLI 跑 init/add（不用 `dlx @latest`） |
| 基元          | @base-ui/react        | 1.7.0    | **Base UI**（v4 默认 style=base-nova，取代旧版 Radix UI）          |
| 工具          | cn                    | 0.2.4    | cn() 类合并（init 自动安装，4.20 起取代 clsx + tailwind-merge）    |

## 2. 创建项目

创建 + 一次装齐依赖（**唯一一次安装**；shadcn CLI 用固定版本，不用 latest）：

```bash
pnpm create vite shadcn-demo --template react-ts --no-interactive
cd shadcn-demo

# 一次装齐：shadcn CLI（固定 4.20.1）+ Tailwind v4 + TypeScript（模板自带 ~6.0.2 一并升到 ^7.0.2）
pnpm add -D shadcn@4.20.1 typescript@^7.0.2 tailwindcss @tailwindcss/vite tw-animate-css
pnpm exec tsc --version                                # → Version 7.0.2
```

- 单条 `pnpm add` 即完成唯一一次安装（无需先单独 `pnpm install`、也无需分多次
  add），实测装出 TS 7.0.2 / Vite 8.2.2 / Tailwind 4.3.3 / tw-animate-css 1.4.0。
- shadcn CLI 以固定版本装入 devDependencies（实测 4.20.1），第 4 节 `init` 直接用
  本地 CLI 运行；`dlx shadcn@latest` 存在版本漂移，不保证与本文行为一致。

> 说明：create 命令为何带 `--no-interactive`？create-vite 已改为交互式向导
> （实测 create-vite **9.2.0**，生成的是 Vite 8.2.2 —— create-vite 自身的
> 版本号与 Vite 主版本号独立演进，9.2.0 是脚手架工具的版本，**≠ Vite 9**）：
> 即使指定了 `--template react-ts`（免掉 framework/variant 两步），在交互
> 终端里 React 模板还会**额外追问两个问题**：
>
> 1. **Which linter to use?** —— Oxlint（默认）/ ESLint
> 1. **Install with pnpm and start now?** —— 是否自动装依赖并启动 dev server
>
> 全部选项都可用 CLI flag 显式指定（非 TTY / CI 脚本环境会自动免交互）：
>
> | flag                                 | 作用                                | 默认              |
> | ------------------------------------ | ----------------------------------- | ----------------- |
> | `-t, --template react-ts`            | framework / variant                 | —                 |
> | `--eslint` / `--no-eslint`           | 选 ESLint / Oxlint（仅 React 模板） | Oxlint            |
> | `-i, --immediate` / `--no-immediate` | 自动装依赖并起 dev server           | 不装              |
> | `--overwrite`                        | 目标目录非空时直接覆盖              | 报错退出          |
> | `--no-interactive`                   | 整体免交互，未指定项全部取默认      | 非 TTY 自动非交互 |
>
> 实测：默认 linter 为 **Oxlint**（`pnpm lint` → `oxlint`，零 ESLint 依赖）；
> 加 `--eslint` 则生成 `eslint.config.js` + eslint 10 + typescript-eslint，
> `pnpm lint` → `eslint .`。其余脚手架（Vite 8.2.2 / React 19.2.8 /
> TS ~6.0.2）两种选择完全一致。

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

**`tsconfig.app.json`** —— compilerOptions 加 paths（供 tsc 构建解析 `@/*`）：

```json
"moduleResolution": "bundler",
"paths": { "@/*": ["./src/*"] },
```

**`tsconfig.json`（根，solution-style）** —— 也要加同样的 paths（供 shadcn
CLI 解析别名、决定组件落盘位置；只配 tsconfig.app.json 的话，init 会把组件
写到项目根 `./@/` 而不是 `src/`）：

```json
"compilerOptions": {
  "baseUrl": ".",
  "paths": { "@/*": ["./src/*"] }
}
```

**`src/index.css`** —— 至少先有：

```css
@import "tailwindcss";
@import "tw-animate-css";
```

✅ 完成本节三步后（Tailwind 已装、别名两处配好），`init` 的 preflight
（Tailwind / alias 校验）直接通过，组件按别名写进 `src/`（见第 4 节）。

## 4. `init` 初始化

```bash
pnpm shadcn init -d    # 本地 CLI（第 2 节已 -D 装好 4.20.1）；-d = --defaults，免交互
```

实测流程输出（shadcn 4.20.1，别名已按第 3 节映射到 `src/`）：

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
  - src/components/ui/button.tsx
  - src/lib/utils.ts
- Updating src/index.css
✔ Updating src/index.css

Project initialization completed.
```

自动安装（进 dependencies）：`@base-ui/react`（基元）、`cn`（cn() 类合并，
4.20 起取代 clsx + tailwind-merge）、`class-variance-authority`（CVA）、
`lucide-react`（图标）、`@fontsource-variable/geist`（字体）；另生成根目录
`.oxlintrc.json`。CLI 已由第 2 节 `-D` 装好，init 不会重复把它加进依赖。

组件直接落在 `src/lib/utils.ts`、`src/components/ui/button.tsx`，无需任何搬移；
收尾验证构建：

```bash
pnpm build
```

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

init 完成后（别名已映射到 `src/`）的最终布局：

```
src/
├── components/ui/          # 复制的组件源码（init 直接生成）
│   ├── button.tsx          # init 自带的基础组件
│   └── …                   # 之后 add 的组件
├── lib/
│   └── utils.ts            # cn() 再导出（见下）
└── index.css               # init 重写，增补：
    @import "tailwindcss";
    @import "tw-animate-css";
    @import "shadcn/tailwind.css";        # shadcn 主题样式的入口
    @import "@fontsource-variable/geist"; # Geist 字体（默认主题字体）
    @custom-variant dark (&:is(.dark *)); # dark 变体
    @theme inline { … }                   # 语义色映射（--color-* → --* 变量）
    :root { … }                           # oklch 色板 + --radius 组合（sm…4xl）
    .dark { … }                           # dark 模式色板
（另：根目录 .oxlintrc.json 由 init 生成）
```

`src/lib/utils.ts`（init 生成；4.20 起直接再导出 `cn` 包，不再手写
clsx + tailwind-merge）：

```ts
export { cn } from "cn"
```

## 7. 启动验证

```bash
pnpm dev    # → http://localhost:5173
```

打开 http://localhost:5173 —— 默认仍是 Vite 欢迎页（init 只把组件源码放进
`src/`，不改 `App.tsx`）。展示/使用 Button 与后续 `add` 组件，见
[组件添加与基本使用](./components.md)。生产构建：

```bash
pnpm build && pnpm preview    # 预览 → http://localhost:4173
```

## 8. 参考链接

| 资源          | 链接                                                                                         |
| ------------- | -------------------------------------------------------------------------------------------- |
| shadcn 文档   | [https://ui.shadcn.com/docs](https://ui.shadcn.com/docs)                                     |
| Vite 安装指南 | [https://ui.shadcn.com/docs/installation/vite](https://ui.shadcn.com/docs/installation/vite) |
| Base UI       | [https://base-ui.com/](https://base-ui.com/)                                                 |
| Tailwind v4   | [https://tailwindcss.com/docs](https://tailwindcss.com/docs)                                 |

→ 下一站：[组件添加与基本使用](./components.md)
