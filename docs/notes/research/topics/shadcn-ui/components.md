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
> 并掌握 v4 / Base UI 的新用法范式。全部基于本机实测（macOS arm64，
> shadcn CLI 4.20.1）。
>
> 上一篇：[环境与初始化](./setup.md)；下一篇：[进阶使用](./advanced.md)。

## 1. add 基本用法

```bash
# 添加一个或多个组件（用环境篇 §2 装的本地固定版 CLI，不用 dlx @latest）
pnpm shadcn add button
pnpm shadcn add card dialog table tabs
```

| 选项                | 作用                                         |
| ------------------- | -------------------------------------------- |
| `-y, --yes`         | 跳过确认提示                                 |
| `-o, --overwrite`   | 覆盖已有文件（默认相同文件跳过）             |
| `--all`             | 添加全部组件                                 |
| `-p, --path <path>` | 指定落盘路径                                 |
| `--dry-run`         | 预览变更不写盘                               |
| `--diff [path]`     | 查看与 registry 的差异（取代旧 `diff` 命令） |

实测输出（shadcn 4.20.1，别名已按环境篇 §3 映射到 `src/`）：

```
- Checking registry.        ✔
- Updating files.
✔ Created 4 files:
  - src/components/ui/card.tsx
  - src/components/ui/table.tsx
  - src/components/ui/tabs.tsx
  - src/components/ui/dialog.tsx
ℹ Skipped 1 file: (files might be identical, use --overwrite to overwrite)
  - src/components/ui/button.tsx
```

> 组件直接写入 `src/components/ui/` —— 前提是已按 [环境与初始化](./setup.md)
> 第 3 节在根 `tsconfig.json` 也配好 `@/*` paths（否则会落到项目根字面 `@/`）。

## 2. 依赖如何自动解析

add 背后两层依赖：

1. **registry 组件依赖**（`registryDependencies`）：加 `field` 会连带装
   `label`、`separator`；加 `dialog` 连带 `button`——实测一次 add 一组，
   依赖组件也被自动创建
1. **npm 依赖**（`dependencies`）：如 `sonner` 组件会安装 `sonner` 包；
   实测主题相关组件还会带进 `next-themes`（深浅色切换）

因此不必手工预装基元依赖——registry item 里声明了什么，CLI 装什么。

## 3. 常用组件清单（实测可用）

| 组件     | 用途                        | 关键依赖/连带                                |
| -------- | --------------------------- | -------------------------------------------- |
| `button` | 按钮（init 自带）           | `@base-ui/react/button` + CVA                |
| `card`   | 卡片容器                    | —                                            |
| `dialog` | 模态对话框                  | `button` + `@base-ui/react/dialog`           |
| `field`  | **表单字段（v4 表单核心）** | `label` + `separator`                        |
| `input`  | 输入框                      | —                                            |
| `label`  | 标签                        | —                                            |
| `tabs`   | 标签页                      | `@base-ui/react/tabs`                        |
| `table`  | 表格                        | —（纯 HTML `<table>` 元素 + cn）             |
| `badge`  | 徽标/标签                   | `merge-props` + `use-render`（Base UI 工具） |
| `sonner` | toast 通知                  | `sonner` npm 包                              |

> v4 registry 中 `form` 项是空 stub（files 为空），真实表单组件是 `field`
> （基于 Base UI Field）——表单请 `add field`。

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

**示例放哪：** 上面的整段代码直接替换 `src/App.tsx` 即可（组件
`import` 自 `@/components/ui/…`），保存后 `pnpm dev` 打开
http://localhost:5173 就能点开对话框看效果。前置：先
`pnpm shadcn add dialog`（自动连带 `button`）把组件装进项目。

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

- `@/lib/utils` 的 `cn()`（4.20 起由 `cn` 包提供 —— utils.ts 仅一行
  `export { cn } from "cn"`；类名合并 + 去重覆盖逻辑封装在包内）
- 组件变体用 `class-variance-authority`（CVA）：`buttonVariants` 导出
  `variant` / `size` 两个维度，改样式 = 改 base/variants 字符串

## 5. 定制入门

| 方式     | 做法                                                                          |
| -------- | ----------------------------------------------------------------------------- |
| 改源码   | 组件就在 `src/components/ui/`，直接编辑（这就是 shadcn 的哲学：代码归你所有） |
| 改变体   | 在 CVA 的 `variants` 里加/改 `variant`、`size`                                |
| 改主题   | 动 `src/index.css` 的 oklch 变量（见 [进阶使用](./advanced.md)）              |
| 组合使用 | `cn(buttonVariants({ variant: "outline" }), "自定义类")`                      |

## 6. 参考链接

| 资源       | 链接                                                  |
| ---------- | ----------------------------------------------------- |
| 组件列表   | <https://ui.shadcn.com/docs/components>               |
| 组件自定义 | <https://ui.shadcn.com/docs/components/customization> |
| Base UI    | <https://base-ui.com/>                                |

→ 下一站：[进阶使用](./advanced.md)
