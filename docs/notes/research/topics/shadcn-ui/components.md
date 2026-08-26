---
hide:
  - navigation
title: shadcn/ui 组件添加与基本使用
tags:
  - research
  - tech
  - shadcn
  - frontend
categories:
  - dev
---

# :material-plus-box: 组件添加与基本使用

> **本页目的：** 用 `shadcn add` 把常用组件装进来，理解依赖如何自动解析，
> 并掌握 v4 / Base UI 的新用法范式。全部基于 external/shadcn-demo 实测。
>
> 上一篇：[环境与初始化](./setup.md)；下一篇：[进阶玩法](./advanced.md)。

## 1. add 基本用法

```bash
# 添加一个或多个组件（用 pnpm dlx / pnpm exec，项目内已含 shadcn 包时用 exec）
pnpm dlx shadcn@latest add button
pnpm dlx shadcn@latest add card dialog table
```

| 选项                | 作用                                         |
| ------------------- | -------------------------------------------- |
| `-y, --yes`         | 跳过确认提示                                 |
| `-o, --overwrite`   | 覆盖已有文件（默认相同文件跳过）             |
| `--all`             | 添加全部组件                                 |
| `-p, --path <path>` | 指定落盘路径                                 |
| `--dry-run`         | 预览变更不写盘                               |
| `--diff [path]`     | 查看与 registry 的差异（取代旧 `diff` 命令） |

实测输出（一次加 7 个组件）：

```
- Checking registry.        ✔
- Installing dependencies.  ✔
- Updating files.
✔ Created 9 files:
  - @/components/ui/card.tsx
  - @/components/ui/table.tsx
  - @/components/ui/tabs.tsx
  - @/components/ui/badge.tsx
  - @/components/ui/sonner.tsx
  - @/components/ui/label.tsx
  - @/components/ui/separator.tsx
  - @/components/ui/dialog.tsx
  - @/components/ui/field.tsx
ℹ Skipped 1 file: (files might be identical, use --overwrite to overwrite)
  - @/components/ui/button.tsx
```

> ⚠️ 与 init 相同，v4.19 在 Vite 8（solution-style tsconfig）下把组件写到
> **项目根的字面 `@/components/ui/`** 目录。手动归位：
>
> ```bash
> mkdir -p src/components/ui src/lib
> mv @/components/ui/*.tsx src/components/ui/
> mv @/lib/utils.ts src/lib/utils.ts
> ```
>
> 组件代码本身可用（`tsc -b` + `vite build` 均通过），仅落盘位置问题。

## 2. 依赖如何自动解析

add 背后两层依赖：

1. **registry 组件依赖**（`registryDependencies`）：加 `field` 会连带装
   `label`、`separator`；加 `dialog` 连带 `button`——实测一次 add 一组，
   依赖组件也被自动创建
1. **npm 依赖**（`dependencies`）：如 `sonner` 组件会安装 `sonner` 包；
   实测主题相关组件还会带进 `next-themes`（深浅色切换）

因此不必手工预装基元依赖——registry item 里声明了什么，CLI 装什么。

## 3. 常用组件清单（实测可用）

| 组件     | 用途                              | 关键依赖/连带                                |
| -------- | --------------------------------- | -------------------------------------------- |
| `button` | 按钮（init 自带）                 | `@base-ui/react/button` + CVA                |
| `card`   | 卡片容器                          | —                                            |
| `dialog` | 模态对话框                        | `button` + `@base-ui/react/dialog`           |
| `field`  | **表单字段（v4 表单核心，见坑）** | `label` + `separator`                        |
| `input`  | 输入框                            | —                                            |
| `label`  | 标签                              | —                                            |
| `tabs`   | 标签页                            | `@base-ui/react/tabs`                        |
| `table`  | 表格                              | —（纯 HTML `<table>` 元素 + cn）             |
| `badge`  | 徽标/标签                         | `merge-props` + `use-render`（Base UI 工具） |
| `sonner` | toast 通知                        | `sonner` npm 包                              |

> ⚠️ **坑：v4 的 `form` 组件是空 stub。** `add form` 实测静默无产出——
> base-nova registry 中 `form` 项的 `files` 为空（已移除，由 `field` 取代）。
> 表单请用 `field`（基于 Base UI Field）。

## 4. v4 / Base UI 新用法范式

v4（style=base-nova）组件基于 **Base UI**，写法与旧版 Radix 有两大不同：

### 4.1 render prop 取代 asChild

旧版 Radix：`<DialogTrigger asChild><Button/></DialogTrigger>`。
**Base UI 没有 asChild**，用 `render` prop 注入元素（实测 `dialog.tsx` 内部
`Dialog.Close render={<Button variant="outline" />}`）：

```tsx
<Dialog>
  <DialogTrigger render={<Button variant="secondary" />}>
    Open dialog
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>标题</DialogTitle>
      <DialogDescription>描述</DialogDescription>
    </DialogHeader>
  </DialogContent>
</Dialog>
```

（实测：直接传 `asChild` 会类型报错，Base UI 没有这个 prop。）

### 4.2 Field 组合子组件，而非标签/错误 prop

Base UI 的 Field 是一组子组件（`field.tsx` 导出
`Field / FieldLabel / FieldContent / FieldError / FieldDescription ...`），
不是 `<Field label="..." error="...">` 那种 props 式 API：

```tsx
<Field>
  <FieldLabel htmlFor="email">Email</FieldLabel>
  <FieldContent>
    <Input id="email" type="email" />
  </FieldContent>
  <FieldError>邮箱格式不正确</FieldError>
</Field>
```

### 4.3 cn() 与 CVA

- `@/lib/utils` 的 `cn()` = `clsx` + `tailwind-merge`（后者负责类名去重覆盖）
- 组件变体用 `class-variance-authority`（CVA）：`buttonVariants` 导出
  `variant` / `size` 两个维度，改样式 = 改 base/variants 字符串

## 5. 定制入门

| 方式     | 做法                                                                          |
| -------- | ----------------------------------------------------------------------------- |
| 改源码   | 组件就在 `src/components/ui/`，直接编辑（这就是 shadcn 的哲学：代码归你所有） |
| 改变体   | 在 CVA 的 `variants` 里加/改 `variant`、`size`                                |
| 改主题   | 动 `src/index.css` 的 oklch 变量（见 [进阶玩法](./advanced.md)）              |
| 组合使用 | `cn(buttonVariants({ variant: "outline" }), "自定义类")`                      |

## 6. 参考链接

| 资源       | 链接                                                  |
| ---------- | ----------------------------------------------------- |
| 组件列表   | <https://ui.shadcn.com/docs/components>               |
| 组件自定义 | <https://ui.shadcn.com/docs/components/customization> |
| Base UI    | <https://base-ui.com/>                                |

→ 下一站：[进阶玩法](./advanced.md)
