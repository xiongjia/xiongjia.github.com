---
title: 用 Restic + R2 + just 构建日常备份方案
date:
  created: 2026-07-30
  updated: 2026-07-30
authors: [xiongjia]
tags:
  - dev
  - tools
slug: restic-backup-guide
description: >
  记录我如何使用 Restic、S3/R2 和 just 构建一套可自动化、可验证、可恢复的个人备份方案
categories:
  - bits
  - dev
---

restic 日常用法，和我自己封装的简化工具。

<!-- more -->

## 为什么用 restic

我把备份 repository 放在 Cloudflare R2，而不是只依赖本地磁盘。这样即使电脑损坏，备份仍然存在于独立的远程存储中。

选择 [restic](https://restic.net) 的理由：

- **加密** — 所有数据在客户端加密后传输，R2 只能看到密文
- **增量去重** — 自动分块去重，只上传变化的部分。我的项目代码每天备份，绝大部分数据块复用，传输量很小
- **S3 原生支持** — 直接对接 R2，无需中间层
- **简单** — 一个二进制搞定，没有复杂的配置文件

## Restic 的核心概念

在进入命令前，先理解三个概念：

### Repository

Restic 的所有备份数据存储在 **repository** 中。Repository 可以位于本地目录、SFTP 服务器或 S3 兼容存储上。Repository 是加密的，访问需要密码。

### Snapshot

每次执行 `restic backup` 创建一个 **snapshot**，类似文件系统在某一个时间点的快照。多个 snapshot 可以共享相同的数据块——如果文件没变，restic 不会重复存储。

### 工作流程

```
源文件 → restic backup → snapshot（加密） → repository（R2/S3/本地）
```

## 安装

```bash
# macOS
brew install restic

# Ubuntu / Debian
apt install restic
```

## 第一次备份

### 初始化 Repository

```bash
# 仅用于演示，自动化环境见下方说明
export RESTIC_PASSWORD="your-strong-password-here"
restic init --repo /path/to/backup-repo
```

!!! warning "Repository 密码"
丢失密码将无法恢复数据。建议用密码管理器生成并保存高强度密码。更换访问密码可以使用 `restic key` 管理 key，不需要重新初始化 repository。

````
自动化脚本中不建议直接 export 密码，推荐使用：
```bash
export RESTIC_PASSWORD_FILE=/path/to/restic-password
# 或
export RESTIC_PASSWORD_COMMAND="pass show restic-repo"
```
````

### 创建 Snapshot

```bash
# 备份单个目录
restic backup --repo /path/to/backup-repo /home/user/documents

# 使用 exclude file 统一管理排除规则
restic backup --repo /path/to/backup-repo \
    --exclude-file=/path/to/.restic_exclude \
    /home/user/projects
```

对于长期备份，建议使用 `--exclude-file` 而不是在命令行中不断增加 `--exclude` 参数。

### 查看 Snapshot

```bash
restic snapshots --repo /path/to/backup-repo

# 查看 snapshot 中的具体文件
restic ls <snapshot-id>

# 在仓库中查找指定文件
restic find important.pdf
```

### 恢复文件

备份最终的价值在于恢复。不要把"backup 成功"当成"备份可靠"，至少应该定期做一次实际 restore 测试。

```bash
# 恢复整个 snapshot 到指定目录
restic restore <snapshot-id> --target /tmp/restore

# 恢复单个文件或目录
restic restore <snapshot-id> \
    --target /tmp/restore \
    --include /path/to/important.pdf

# 恢复最新 snapshot
restic restore latest --target /tmp/restore
```

### 验证 Repository 完整性

验证分三级，日常用 subset 检查即可，重要备份可以定期执行完整检查：

```bash
# 一级：检查 repository metadata（快速）
restic check

# 二级：随机读取并验证部分数据（推荐日常使用）
restic check --read-data-subset=5%

# 三级：读取并验证所有数据（耗时较长）
restic check --read-data
```

## Tag 与 Retention

### 为什么用 Tag

同一台机器上可能备份多个项目，如果不做区分，一个项目的保留策略会影响到另一个。Tag 可以让不同备份任务拥有独立的 retention policy。

```
repository
├── tag:project:blog
│   ├── snapshot A (host:my-mac)
│   └── snapshot B (host:server)
├── tag:project:photos
└── tag:project:documents
```

### Tag 命名设计

我使用三层的 tag 命名：

```bash
--tag "project:blog"     # 项目标识，作为 forget 的过滤条件
--tag "host:my-mac"      # 机器标识，区分不同机器
--tag "path:projects"    # 路径标识，一个项目下可能备份多个路径
```

### forget 与 prune

`forget` 和 `prune` 是两个不同的操作：

```
forget → 删除不再需要的 snapshot 引用
prune  → 清理已经没有任何 snapshot 引用的数据块
```

日常使用通常组合执行：先 forget 删除过期 snapshot，再 prune 回收空间。

### 我的保留策略

```bash
restic forget \
    --keep-daily 7 \
    --keep-weekly 4 \
    --keep-monthly 6 \
    --prune \
    --tag "project:blog"
```

| 策略 | 保留数量    | 说明                       |
| ---- | ----------- | -------------------------- |
| 每日 | 最近 7 天   | 粒度细，方便回退到最近几天 |
| 每周 | 最近 4 周   | 覆盖近期的重要节点         |
| 每月 | 最近 6 个月 | 半年内的长期归档           |

完整的策略选项参考（注意注释写在命令上方，避免 shell 解析问题）：

```bash
# 保留最近 N 个快照
# 保留最近 24 小时
# 保留最近 7 天
# 保留最近 4 周
# 保留最近 6 个月
# 保留最近 2 年
restic forget \
    --keep-last 10 \
    --keep-hourly 24 \
    --keep-daily 7 \
    --keep-weekly 4 \
    --keep-monthly 6 \
    --keep-yearly 2 \
    --keep-tag important \
    --keep-within 2w
```

## 远程存储

我把备份 repository 放在远程存储，而不是只依赖本地磁盘。Restic 原生支持 S3 协议，兼容所有 S3 兼容存储。

### Cloudflare R2

Cloudflare R2 提供 S3-compatible API，且**不收取 Internet egress 费用**，因此对于偶尔需要恢复大量数据的异地备份场景比较有吸引力。存储和操作等费用仍需根据实际使用量计算。

```bash
export AWS_ACCESS_KEY_ID="<r2-access-key>"
export AWS_SECRET_ACCESS_KEY="<r2-secret-key>"

restic init --repo s3:https://<ACCOUNT_ID>.r2.cloudflarestorage.com/my-bucket/restic

restic backup --repo s3:https://<ACCOUNT_ID>.r2.cloudflarestorage.com/my-bucket/restic \
    --tag "project:blog" \
    --tag "host:my-mac" \
    /home/user/projects/blog
```

### AWS S3

```bash
export AWS_ACCESS_KEY_ID="<aws-access-key>"
export AWS_SECRET_ACCESS_KEY="<aws-secret-key>"

restic init --repo s3:https://s3.ap-northeast-1.amazonaws.com/my-bucket/restic

restic backup --repo s3:https://s3.ap-northeast-1.amazonaws.com/my-bucket/restic \
    --tag "project:blog" \
    --tag "host:my-mac" \
    /home/user/projects/blog
```

## 备份 ≠ 可靠备份

这是整篇文章最想传达的一点。一个真正可靠的备份方案至少需要：

```
        Backup（创建 snapshot）
           │
           ▼
      Remote Storage（异地存储）
           │
           ▼
         Verify（验证完整性）
           │
           ▼
         Restore（实际恢复测试）
```

### 1. 至少两个独立存储位置

我的方案：本地（电脑磁盘做临时缓存）+ R2（异地存储）。即使电脑损坏，数据仍然存在。

### 2. 定期 check

```bash
restic check --read-data-subset=5%
```

### 3. 定期 restore 测试

Repository check 和实际恢复测试解决的是不同问题。我每季度做一次完整的 restore 测试，把一个 snapshot 恢复到临时目录，确认文件能正常打开。

### 4. 密码独立保存

Repository 密码和 backup 数据分开保存。我用密码管理器保存，不把密码放在备份脚本或 repository 所在的机器上。

### 5. 测试失败通知

我故意让 backup job 失败一次，确认 Telegram 能正常收到失败通知——否则通知配置了却没有真正生效。

## 我的 Backup Module

命令太长记不住，我在 [playground](https://github.com/xiongjia/playground) 项目中封装了 backup module，用 `just` 任务编排器统一管理。

### 项目结构

```
playground/
├── justfile                   # 入口：加载各模块
├── config/
│   ├── .env.example           # 配置模板（git tracked）
│   ├── .env                   # 实际配置（gitignored）
│   └── .env.dev.local         # 本机覆盖（gitignored）
└── modules/
    └── backup/
        ├── README.md          # 模块文档
        ├── justfile           # backup 任务定义
        ├── .restic_exclude    # 排除规则
        └── scripts/
            └── run-backup.sh  # 备份主脚本
```

加载顺序：`.env` → `.env.dev.local`（后者覆盖前者）。

### 快速开始

```bash
# 1. 安装依赖
brew install restic just

# 2. 配置
cp config/.env.example config/.env
# 编辑 config/.env 设置 RESTIC_PASSWORD、RESTIC_REPOSITORY、BACKUP_SOURCE_DIR、BACKUP_TAG、HOSTNAME

# 3. 初始化仓库（只需一次）
just backup::init

# 4. 日常备份
just backup::run
```

### 可用命令

| 命令                              | 说明                             |
| --------------------------------- | -------------------------------- |
| `just backup::run`                | 备份 → forget → prune → 手机通知 |
| `just backup::run-only`           | 仅备份，不做清理                 |
| `just backup::list`               | 列出所有快照                     |
| `just backup::status`             | 查看最新快照统计                 |
| `just backup::restore ./out [id]` | 恢复快照到指定目录               |
| `just backup::forget`             | 手动执行保留清理                 |
| `just backup::forget-dry-run`     | 预览会被清理的快照               |
| `just backup::prune`              | 手动回收数据块                   |
| `just backup::check`              | 验证仓库完整性                   |

### 封装特色

#### 1. 自动 Tag 标识

每次备份自动打上三个 tag，精确区分项目、机器和数据来源：

| Tag              | 来源                              | 示例            |
| ---------------- | --------------------------------- | --------------- |
| `$BACKUP_TAG`    | `config/.env`                     | `my-backup`     |
| `host:$HOSTNAME` | `config/.env`                     | `host:my-mac`   |
| `path:$basename` | 从 `BACKUP_SOURCE_DIR` 首路径提取 | `path:projects` |

#### 2. 内置保留策略

`just backup::run` 在备份后自动执行：

```bash
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune --tag "$BACKUP_TAG"
```

#### 3. 排除规则

`.restic_exclude` 预置了常见排除项，直接用 `--exclude-file`：

```
node_modules/
target/
.DS_Store
*.tmp
__pycache__/
.vscode/
.idea/
```

#### 4. 多目录备份

`BACKUP_SOURCE_DIR` 支持空格分隔多个路径：

```bash
BACKUP_SOURCE_DIR="/home/user/data /home/user/projects /etc/nginx"
```

!!! warning "路径空格限制"
当前使用空格分隔路径，因此路径本身不应含有空格。如果你的路径包含空格，可以每个目录单独配置一个 job，或改进解析方式。

#### 5. 相对路径（BACKUP_PARENT）

这是我觉得比较有价值的设计——控制 repository 中的路径形式。

假设要备份 `/home/user/projects/blog`：

```bash
# 不设置 BACKUP_PARENT，repository 中存储绝对路径
/home/user/projects/blog/foo.txt

# 设置 BACKUP_PARENT=/home/user，repository 中存储相对路径
projects/blog/foo.txt
```

避免将机器的绝对目录结构写入 repository，恢复时也更加灵活。

#### 6. 通知

`backup::run` 备份结束后通过 playground 的 notify module 发送执行结果到手机：

```
✅ backup::run succeeded (took: 2m15s)
❌ backup::run failed (took: 0m45s, exit code: 2)
```

通知具体配置（Telegram Bot Token / Chat ID）属于 notify module 的范围，不在这里展开。详见 [notify module 文档](https://github.com/xiongjia/playground/tree/main/modules/notify)。

## 自动化

### 定时执行

`just backup::run` 准备好之后，通过系统定时任务驱动：

```bash
# macOS: 每天 10:00 执行
# 创建 ~/Library/LaunchAgents/com.user.restic-backup.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.restic-backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>just</string>
        <string>backup::run</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/path/to/playground</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.user.restic-backup.plist
```

Linux 下用 systemd timer，思路相同。

## 我的备份方案总结

```
                ┌───────────────┐
                │   My Computer │
                │               │
                │   just        │
                │ backup::run   │
                └───────┬───────┘
                        │
                   restic backup
                   （加密 + tag）
                        │
                        ▼
                ┌───────────────┐
                │ restic repo   │
                │   encrypted   │
                └───────┬───────┘
                        │
                   S3-compatible
                        │
                        ▼
                ┌───────────────┐
                │ Cloudflare R2 │
                └───────────────┘
```

每日备份流程：

```
backup → tag → forget → prune → notify（推送到手机）
```

核心约定：

| 维度     | 我的选择                                                    |
| -------- | ----------------------------------------------------------- |
| 备份内容 | 项目代码、配置文件                                          |
| 存储位置 | Cloudflare R2（异地）                                       |
| 保留策略 | 7 天每日 + 4 周每周 + 6 月每月                              |
| 验证方式 | 每周 `check --read-data-subset=5%`，每季度实际 restore 测试 |
| 通知方式 | Telegram Bot → 手机                                         |
| 密码管理 | 密码管理器，不放在备份脚本中                                |
| 自动化   | launchd（macOS）定时驱动                                    |
