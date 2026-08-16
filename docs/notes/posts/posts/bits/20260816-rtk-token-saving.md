---
title: RTK 使用与节约 token
date:
  created: 2026-08-16
  updated: 2026-08-16
authors: [xiongjia]
tags:
  - ai
  - tools
  - dev
slug: rtk-token-saving
description: >
  记录 RTK（Rust Token Killer）的安装、配置与实测 —— 它是如何在 agent 读取 bash 输出前压缩/过滤内容，从而减少 LLM token 消耗的
categories:
  - bits
  - dev
---

RTK [:simple-github:](https://github.com/rtk-ai/rtk){:target="\_blank"} (Rust Token Killer) 是一个高性能 CLI 代理，在命令输出进入 LLM context 之前压缩/过滤内容，官方宣称可削减 agent 读取的 bash 输出 60-90%。单 Rust 二进制、零依赖、小于 10ms 开销，支持 100+ 常用命令。

<!-- more -->

## 为什么需要 RTK

LLM 编码 agent（Claude Code、pi 等）的一大 token 消耗大头是 **bash 输出**。一条 `git diff`、一次完整 build 的输出动辄几十 KB，其中大部分是 LLM 不需要的噪音：`ls` 每行一个条目、`grep` 的原始行、测试的通过项、build 的 INFO 日志…… 这些内容全部原样进入 context，按 token 计费。

RTK 的思路很直接：**在输出到达 agent 之前，先按命令类型做压缩**。

## 原理

RTK 对每条命令应用 4 种策略（可组合）：

1. **过滤** - 去掉噪音（注释、空白、样板输出）
1. **分组** - 聚合相似项（文件按目录折叠、错误按类型聚合）
1. **截断** - 保留相关上下文，砍掉冗余
1. **去重** - 重复日志行折叠成计数

拿最简单的 `ls -la scripts/` 举例（本机真实输出，1315 → 477 bytes，-64%）：

```text
# raw: 每行 9 列（权限/链接数/属主/属组/大小/月/日/时间/文件名），全量展示（agent 根本用不上）
$ ls -la scripts/
total 480
drwxr-xr-x@ 20 user       staff    640 Aug 16 12:29 __pycache__
drwxr-xr-x  20 user       staff    640 Aug 16 12:49 .
drwxr-xr-x  39 user       staff   1248 Aug 16 13:49 ..
-rw-r--r--@  1 user       staff   5206 Aug  2 11:47 add_weight_week.py
-rw-r--r--@  1 user       staff  17019 Aug 16 00:57 bucket_check.py
...（共 21 行）

# rtk: 权限简化为八进制，属主/属组/时间戳全部丢弃，只留名字 + 人类可读大小
$ rtk ls -la scripts/
755  __pycache__/
755  md2wechat/
644  add_weight_week.py  5.1K
644  bucket_check.py  16.6K
644  api_server.py  1.1K
...（共 18 行）
```

每一行留下的只有 agent 真正关心的：**文件名 + 大小**，而把权限、属主、属组、时间戳这些对代码任务几乎无用的列全部砍掉。

按命令类型的典型效果：

| 命令                    | RTK 做什么                   |
| ----------------------- | ---------------------------- |
| `ls` / `tree`           | 折叠成树状 + 文件计数        |
| `cat` / `read`          | 智能读取：签名和结构代替全文 |
| `grep` / `rg`           | 截断长行，按文件分组         |
| `git status`            | 紧凑 stat，按状态分组        |
| `git diff`              | 精简上下文，去 header        |
| `git log`               | 只留 hash / author / subject |
| `pytest` / `cargo test` | 只留失败项，通过项折叠成计数 |
| `ruff check`            | 按规则和文件分组             |

## 安装

Homebrew（本机 v0.45.0）：

```bash
brew install rtk
```

或官网快速安装脚本：

```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
```

## 与 agent 集成

RTK 提供了 `rtk init -g`（hook 方式）以及面向各 agent 的初始化命令。它支持 16 种 AI 编码工具，包括 Claude Code、Cursor、Gemini CLI、Codex 以及 **pi**：

```bash
rtk init -g --agent pi    # 全局安装 pi extension
```

以 pi 为例，生成的是 `~/.pi/agent/extensions/rtk.ts`：一个 typeScript extension，监听 `tool_call` 事件中的 bash 命令，调用 `rtk rewrite <cmd>` 重写为 RTK 等价命令（返回 0/3 表示有重写，1 表示透传）。所有重写逻辑都在 RTK 的 Rust registry（`src/discover/registry.rs`）里，extension 只是薄薄的委托层。

关键行为：

- 失败时 **fail-open**：RTK 出错只是透传原命令，绝不阻塞执行
- `RTK_DISABLED=1` 可随时禁用
- 版本 < 0.23.0（引入 `rtk rewrite`）自动禁用
- 重写只作用于 **bash 工具调用**；agent 内置的 Read/Grep/Glob 等不走 hook，需显式用 `rtk read` / `rtk grep` / `rtk find` 或 shell 命令

## 本地实测

在本文档仓库（MkDocs + uv + pytest 项目）实测，对比 raw 命令与 `rtk` 前缀命令的输出字节数：

| 命令                          | raw (bytes) | rtk (bytes) | 节省      |
| ----------------------------- | ----------- | ----------- | --------- |
| `uv run mkdocs build --clean` | 54,538      | 3,578       | **93.4%** |
| `uv run pytest`（全绿）       | 3,430       | 91          | **97.3%** |
| `uv run pytest`（1 失败）     | 1,048       | 461         | 56%       |
| `find docs -type f`           | 5,818       | 813         | **86%**   |
| `ls -la`（仓库根）            | 2,380       | 623         | **74%**   |
| `git status`（clean）         | 58          | 40          | 31%       |
| `git diff`（小改动）          | 241         | 131         | 46%       |

输出越大的命令收益越明显：build 和全绿 pytest 都削减了 90%+。失败场景下 RTK 保留失败项的关键 traceback，砍掉冗余上下文。

`rtk gain` 给出全局统计（本机历史累积）：

```
Total commands:    16608
Input tokens:      43.9M
Output tokens:     13.4M
Tokens saved:      30.5M (69.5%)
Total exec time:   104m17s (avg 376ms)
```

主要节省来源：`rtk grep` 3089 次省 19.6M tokens、`rtk read` 1471 次省 3.5M、`rtk git diff HEAD` 273 次省 335K。

## 注意点

- **削减输出 ≠ 账单减 90%**。官方明确说明：削减的是 agent 读取的 bash 输出，不是账单。输出只是输入 token 的一部分，输入 token 又只是账单的一部分。RTK 报告的 token 数是 `bytes / 4` 的**估算**，实际按 tokenizer 计费会有偏差。
- **小输出命令反而更大**。比如 `git log --oneline -15`（raw 1,156 → rtk 4,114）和 clean 状态的 `ruff check`（19 → 89），因为加了标题/分组结构后开销超过压缩收益。RTK 只在大输出上划算。（注：rtk 的 `git log` 输出含相对时间戳，数字为实测快照）
- `rtk pytest` 直接调用在本机报 "Failed to spawn process"（找不到 pytest），需要带环境运行：`rtk uv run pytest`。
- RTK 会把完整输出 tee 到日志（如 `~/Library/Application Support/rtk/tee/*.log`），压缩掉了但随时可回看全文。

## 参考

- [RTK GitHub](https://github.com/rtk-ai/rtk)
- [RTK Website](https://www.rtk-ai.app/)
- [How RTK Savings Work](https://www.rtk-ai.app/guide/resources/savings-explained)
