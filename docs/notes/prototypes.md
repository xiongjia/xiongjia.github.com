---
icon: material/flask-outline
hide:
  - tags
  - toc
---

# :material-flask-outline: Prototypes

实验性 mini-project 集散地：快速验证的想法就地保存在仓库根目录
`prototypes/<name>/`，随仓库一起提交，不影响主站的构建、格式化与 lint 流程。
列表事实来源为仓库内 `prototypes/README.md`，本页保持同步；点击链接在新标签页
打开 GitHub 目录。

## Overview

| Prototype                                           | Status          | Created    |
| --------------------------------------------------- | --------------- | ---------- |
| [ali-oss-client](#ali-oss-client)                   | 🟢 Working      | 2026-08-01 |
| [prototype-example](#prototype-example)             | 🟡 Experimental | 2026-08-01 |
| [go-cli-urfave](#go-cli-urfave)                     | 🟡 Experimental | 2026-08-03 |
| [supabase-storage-client](#supabase-storage-client) | 🟢 Working      | 2026-08-04 |

状态：🟡 Experimental（实验性，随时变化）· 🟢 Working（已验证可用）· ⏸️ Shelved（搁置）· ✅ Done（完成）· 🗑️ Abandoned（废弃）

______________________________________________________________________

## TypeScript

### ali-oss-client

TypeScript 原型，用官方 `ali-oss` SDK（pnpm 管理）演示阿里云 OSS 基本用法：
环境变量配置、列 bucket / 对象、上传、下载、生成签名 URL、删除（demo 对象自动清理）。
README 内含基本的阿里云 OSS 配置步骤（RAM 用户 + AccessKey、建 bucket、region/endpoint、`.env.dev.local`）。

- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/ali-oss-client)

### supabase-storage-client

TypeScript 原型，用官方 `@supabase/supabase-js` SDK（pnpm 管理）在**本地**测试 Supabase
Storage 基本用法：自带 `supabase/` 项目配置（`supabase init`，storage 默认开启），anon key
未配置时自动从 `supabase status -o env` 读取，实现零配置本地运行。操作覆盖：列 bucket、建
私有 bucket、列对象、上传（upsert）、下载、签名 URL（GET / PUT 上传）、公开 URL、删除
（demo 对象自动清理；bucket 仅当本次运行创建时才删除，已有 bucket 保留）。

- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/supabase-storage-client)

______________________________________________________________________

## Rust

### prototype-example

最小 Rust hello-world **示例**，用于验证原型机制的完整流程（不是实际功能原型）：
证明非 Python 工具链项目可以干净地放在 `prototypes/` 下，不影响 MkDocs 构建、
ruff / mdformat 格式化与 lint。

- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/prototype-example)

______________________________________________________________________

## Go

### go-cli-urfave

Go CLI 原型，用 `urfave/cli` v2 框架写的简单命令行程序（`greet` 命令，支持
`--name` 参数）。原为研究 [Lux](https://github.com/iawia002/lux) 时在
`research/experiments/` 下的实验代码，已迁移至此；`go.sum` 纳入版本控制以保证
依赖可复现构建。

- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/go-cli-urfave)
