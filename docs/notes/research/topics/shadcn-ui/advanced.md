---
hide:
  - navigation
title: shadcn/ui 进阶使用
tags:
  - research
  - tech
  - shadcn
  - frontend
categories:
  - dev
---

# :material-rocket-launch-outline: 进阶使用

> **本页目的：** 组件更新（diff/overwrite）、主题定制（oklch 变量）、表单集成
> （react-hook-form + zod + field）、registry 机制与框架差异。全部基于
> 本机实测（macOS arm64）。
>
> 上一篇：[组件添加与基本使用](./components.md)。

## 1. 组件更新与对比

v4 CLI 中旧 `shadcn diff` 命令已弃用，改为 `add --diff`：

```bash
# 查看本地组件与 registry 的差异（不写盘）
pnpm exec shadcn add button --diff

# 强制覆盖本地版本（源码被改过时用 --overwrite 更新）
pnpm exec shadcn add button --overwrite

# 预览改动再落盘
pnpm exec shadcn add dialog --dry-run
```

实测 `add button --diff`：对未生成的组件显示 `(create)` 计划块并打出
完整文件内容；对已存在且一致的组件直接提示 `Skipped (files might be identical)`。更新思路：先 `--diff` 看差异 → 小范围自己改 / 大版本用
`--overwrite` 拉回。

## 2. 主题定制（CSS-first）

Tailwind v4 + shadcn 的主题全部在 `src/index.css`（无 tailwind.config.js）：

- **色板**：`@theme inline` 把语义色映射到 CSS 变量（`--color-primary` →
  `var(--primary)`）；`:root` / `.dark` 下定义 oklch 值，如
  `--primary: oklch(0.205 0 0)`（neutral 基色）
- **圆角**：`--radius: 0.625rem` 派生 `--radius-sm/md/lg/xl/2xl/3xl/4xl`
  （各乘系数），改一个 `--radius` 全局生效
- **dark 模式**：`@custom-variant dark (&:is(.dark *))` —— 给根元素加
  `.dark` 类切换；主题切换组件用 `next-themes`（实测 sonner 场景已安装）
- **字体**：默认 Geist（`@fontsource-variable/geist`），
  换 `--font-sans` / `--font-heading` 即可
- **菜单外观**：components.json 的 `menuColor` / `menuAccent` 控制
  sidebar/菜单配色（base-nova 新增字段）

## 3. 表单集成（react-hook-form + zod）

shadcn v4 表单 = `field` 组件 + react-hook-form + zod：

```bash
pnpm add react-hook-form zod @hookform/resolvers
pnpm exec shadcn add field input label
```

```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"

const schema = z.object({ email: z.string().email() })

// Field 组合子组件承载 RHF 的 register 状态
<form onSubmit={form.handleSubmit((v) => console.log(v))}>
  <Field>
    <FieldLabel htmlFor="email">Email</FieldLabel>
    <FieldContent>
      <Input id="email" type="email" {...form.register("email")} />
    </FieldContent>
    {form.formState.errors.email && (
      <FieldError>{form.formState.errors.email.message}</FieldError>
    )}
  </Field>
  <Button type="submit">Submit</Button>
</form>
```

> 提示：Base UI Field 自带状态管理，但与 RHF 结合时推荐让 RHF 作为唯一
> 状态源（register + formState.errors 显式传入），避免双状态源打架。

## 4. registry 机制

### 4.1 在线 registry 结构（实测抓取）

默认样式 registry URL：`https://ui.shadcn.com/r/styles/base-nova/registry.json`，
顶层结构：

```json
{
  "name": "...",
  "homepage": "...",
  "items": [ ... ]   // 全部可用组件（实测 216 个）
}
```

每个 item 的关键字段（实测 dialog/field/form）：

| 字段                   | 含义                        | 实测例子                          |
| ---------------------- | --------------------------- | --------------------------------- |
| `name`                 | 组件名                      | `field`                           |
| `dependencies`         | npm 依赖                    | （如 sonner 组件的 sonner 包）    |
| `registryDependencies` | 依赖的其他 registry 组件    | `field → label, separator`        |
| `files`                | 组件文件（registry 内路径） | `registry/base-nova/ui/field.tsx` |

> 实测：base-nova registry 中 `form` 的 files 为空数组（stub，已移除）；
> `field` 才是真正表单组件。

### 4.2 组件检索

search/list 默认不配置 registry 时会提示：

```
No registries are configured in components.json.
Provide a registry or namespace to search, e.g. shadcn search @shadcn.
```

显式给命名空间即可（实测）：

```bash
pnpm exec shadcn search @shadcn -q dialog -l 5
# → @shadcn/dialog (ui)、@shadcn/dialog-example (example)、@shadcn/sidebar-13 (block) …
```

registry item 有类型：`ui`（组件）、`example`（示例）、`block`（整块布局，
如 sidebar-13 之类）。

### 4.3 自定义 registry / 私有组件库

- components.json 的 `registries` 字段登记额外 registry（默认 `{}`）
- CLI 自带 `build`（构建 registry）、`registry`（管理）、`preset`、`apply`
  等子命令——可把自写组件发布成私有 registry（本页未实测，保留官方文档指引）

## 5. 框架差异

| 维度                     | Vite（本页实测）                     | Next.js                         | Astro      |
| ------------------------ | ------------------------------------ | ------------------------------- | ---------- |
| 接入                     | @tailwindcss/vite 插件 + CSS @import | 官方有 Next 专用指南（postcss） | 有官方指南 |
| `rsc`（components.json） | `false`                              | `true`（App Router）            | —          |
| 别名                     | tsconfig paths + vite resolve.alias  | `paths` in tsconfig             | 类似       |
| 组件代码                 | 通用 TSX，无框架特异性               | 部分组件有 RSC 特定分支         | 同左       |

实测 Vite 场景：`rsc: false`、`"use client"` directive 仍会出现在组件文件
头部（如 dialog.tsx）——对纯客户端 SPA 无害。

## 6. 参考链接

| 资源            | 链接                                             |
| --------------- | ------------------------------------------------ |
| 组件更新        | <https://ui.shadcn.com/docs/components/updating> |
| 主题定制        | <https://ui.shadcn.com/docs/theming>             |
| 自定义 registry | <https://ui.shadcn.com/docs/registry>            |
| Registry spec   | <https://ui.shadcn.com/docs/registry/spec>       |
| Base UI         | <https://base-ui.com/>                           |
