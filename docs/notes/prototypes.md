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

| Prototype                               | Status          | Created    |
| --------------------------------------- | --------------- | ---------- |
| [ali-oss-client](#ali-oss-client)       | 🟡 Experimental | 2026-08-01 |
| [prototype-example](#prototype-example) | 🟡 Experimental | 2026-08-01 |

状态：🟡 Experimental（实验性，随时变化）· ⏸️ Shelved（搁置）· ✅ Done（完成）· 🗑️ Abandoned（废弃）

______________________________________________________________________

## TypeScript

### ali-oss-client

TypeScript 原型，用官方 `ali-oss` SDK（pnpm 管理）演示阿里云 OSS 基本用法：
环境变量配置、列 bucket / 对象、上传、下载、生成签名 URL、删除（demo 对象自动清理）。
README 内含基本的阿里云 OSS 配置步骤（RAM 用户 + AccessKey、建 bucket、region/endpoint、`.env`）。

- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/ali-oss-client)

______________________________________________________________________

## Rust

### prototype-example

最小 Rust hello-world **示例**，用于验证原型机制的完整流程（不是实际功能原型）：
证明非 Python 工具链项目可以干净地放在 `prototypes/` 下，不影响 MkDocs 构建、
ruff / mdformat 格式化与 lint。

- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/prototype-example)
