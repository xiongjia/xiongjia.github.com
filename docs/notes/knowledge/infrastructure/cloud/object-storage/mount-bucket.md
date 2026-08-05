---
hide:
  - navigation
title: 挂载 Bucket 为本地文件系统（FUSE Mount）
tags:
  - knowledge
  - cloud
  - object-storage
  - mount
  - fuse
categories:
  - infrastructure
---

# 挂载 Bucket 为本地文件系统（FUSE Mount）

> 用 FUSE 把对象存储 bucket 挂载成 Linux 本地目录，就能用 `ls` / `cp` / `cat`
> 等普通文件命令直接操作云端对象。本文以阿里云 OSS 的 **OSSFS2** 为主讲透
> 安装、挂载与 **Security Key 处理**，并覆盖 AWS S3（mountpoint-s3 / s3fs-fuse）、
> S3 兼容端点（R2 / MinIO / Supabase）、以及通用方案 rclone。
> 通用用法见 [基本用法](./basic-usage.md)，供应商差异见
> [供应商对比](./vendors-comparison.md)。

## 概述

FUSE（Filesystem in Userspace）让一个用户态进程把对象存储的 API 翻译成
POSIX 文件操作：挂载后 `ls /mnt/bucket` 实际发出的是 ListObjects 请求，
`cat /mnt/bucket/a.txt` 是 GetObject。

**适合的场景**

- 数据搬移：桶间 / 云间迁移、下载到本地、批量归档
- 大数据 / AI 训练：把云端数据当本地路径读（顺序读友好）
- 用现有本地工具（find、tar、diff……）直接处理云端文件，不改代码

**限制（务必先了解）**

- **不是完整 POSIX**：OSSFS2 针对顺序 / 随机读 + 追加写优化；mountpoint-s3 基本是
  读 + 追加写；随机写、硬链接、部分元数据语义不支持
- 小文件、随机读写的性能明显差于对象存储原生 API / SDK
- 多机并发写没有锁协调，需要业务自己保证一致性
- 挂载是单机行为：改代码直接改用 SDK 往往比挂载更合适（详见
  [基本用法](./basic-usage.md#6-url) 的直传模型）

**各家工具速览**

| Bucket           | 推荐工具                            | 备注             |
| ---------------- | ----------------------------------- | ---------------- |
| 阿里云 OSS       | **ossfs2**（新，C++）/ ossfs1（旧） | 官方，本页重点   |
| AWS S3           | mountpoint-s3（官方）/ s3fs-fuse    | 官方工具读吞吐高 |
| Cloudflare R2    | s3fs-fuse / rclone                  | S3 兼容端点      |
| MinIO            | s3fs-fuse / rclone                  | S3 兼容端点      |
| Supabase Storage | 任意 S3 兼容工具                    | 先开启 S3 协议   |

## 阿里云 OSS：OSSFS2（重点）

### 是什么

- [aliyun/ossfs](https://github.com/aliyun/ossfs) 仓库的 **main 分支就是
  OSSFS2**（C++，基于 libfuse3 Low-Level API + PhotonLibOS 协程 HTTP 客户端，
  Apache 2.0）；旧版 OSSFS1 在 `main-v1` 分支，仍会维护
- 相比 OSSFS1，官方 benchmark 显示单线程顺序大文件写吞吐提升约 18 倍、
  128 线程小文件并发读提升 20 倍以上（面向 AI 训练、大数据等场景）

### 安装

- 从 [Releases](https://github.com/aliyun/ossfs/releases) 下载预编译包：
  - Ubuntu（14.04+）→ `.deb`：`sudo dpkg -i <ossfs2>.deb`
  - Alibaba Cloud Linux 2/3、CentOS 7/8 → `.rpm`：`sudo yum install <ossfs2>.rpm -y`
  - aarch64 目前仅 Alibaba Cloud Linux 3 提供
- 其他发行版源码编译（GCC 9–13、CMake 3.8+）
- 验证：`ossfs2 --version`

### 挂载

```bash
ossfs2 mount /mnt/oss \
  --oss_endpoint=oss-cn-hangzhou.aliyuncs.com \
  --oss_bucket=my-bucket

ls /mnt/oss                      # 像本地目录一样操作
echo "123" > /mnt/oss/test.txt
umount /mnt/oss                  # 卸载
```

- 只挂桶内某个前缀：加 `--oss_bucket_prefix=demo/`
- **同地域 ECS 内网访问免流量**：endpoint 用内网地址
  `oss-cn-hangzhou-internal.aliyuncs.com`
- 调试：`--log_level=debug`，日志默认写 `/tmp/ossfs2`（多个 ossfs2 进程时
  建议各配 `--log_dir` 隔离）
- 参数也可以用配置文件组织（官方 configure-ossfs-2-0 文档）；全部选项见
  `ossfs2 mount --help`

### Security Key 处理（重点）

OSSFS2 支持四种凭据来源，安全性差异很大：

| 方式              | 用法                                              | 安全性                      | 建议                               |
| ----------------- | ------------------------------------------------- | --------------------------- | ---------------------------------- |
| ECS 实例 RAM 角色 | `--ram_role=<角色名>`（v2.0.2+）                  | 最高：无 AK 落盘、无明文    | ✅ 生产首选（在 ECS 内）           |
| 外部进程取凭据    | `--credential_process=<命令>`（v2.0.5+）          | 高：凭据不出现在命令行/文件 | ✅ 推荐（对接密钥管理 / 临时凭证） |
| 环境变量          | `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET`     | 高：不进 ps 参数            | ✅ 常用                            |
| 挂载参数          | `--oss_access_key_id` / `--oss_access_key_secret` | 低：ps、shell 历史可见      | ❌ 避免（官方也不推荐）            |

要点：

- **绝不用主账号 AccessKey**：建专用 RAM 用户，只授权目标 bucket 的最小权限
  （RAM Policy 收敛到 `my-bucket`）
- 环境变量方式适合 systemd unit（`Environment=`）或启动脚本先 `source`
  再执行挂载命令，明文不进命令行
- `credential_process` 由外部命令返回凭据（类似 AWS 的 credential_process，
  输出 JSON 含 `AccessKeyId` / `AccessKeySecret` / `Expiration` / `SecurityToken`），
  可对接 KMS / 凭据管家 / STS 服务，实现密钥不落地、自动轮换
- 需要临时凭证（STS）时走 `credential_process` 注入，避免长期 AK 常驻

## AWS S3：mountpoint-s3 与 s3fs-fuse

- **mountpoint-s3**（AWS 官方）：走标准 AWS 凭据链（环境变量 →
  `~/.aws/credentials` → IAM 角色），一条命令挂载：
  ```bash
  mount-s3 my-bucket /mnt/s3
  ```
  读吞吐高、内存占用低；写为创建 + 追加写，不支持随机写等完整 POSIX 语义。
  适合读多写少、大数据分析场景。
- **s3fs-fuse**（[s3fs-fuse/s3fs-fuse](https://github.com/s3fs-fuse/s3fs-fuse)）：
  POSIX 语义更完整，兼容更多场景。凭据三选一：
  - 密码文件：`echo "AK:SK" > ~/.passwd-s3fs && chmod 600 ~/.passwd-s3fs`，
    挂载时 `-o passwd_file=~/.passwd-s3fs`（默认也会读 `~/.passwd-s3fs` /
    `/etc/passwd-s3fs`）
  - 环境变量：`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` /
    `AWS_SESSION_TOKEN`
  - AWS 标准凭据文件 `~/.aws/credentials`

## S3 兼容端点：R2 / MinIO / Supabase

同一套 s3fs-fuse 指向不同端点即可：

```bash
s3fs my-bucket /mnt/s3 \
  -o passwd_file=~/.passwd-s3fs \
  -o url=https://<ACCOUNT_ID>.r2.cloudflarestorage.com \
  -o use_path_request_style
```

- **Cloudflare R2**：`url` 用账号派生端点（`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`）；
  常见示例带 `use_path_request_style`（R2 同时支持路径式与虚拟主机式寻址，
  后者即 r2-client 原型默认行为）
- **MinIO**：`url=http://127.0.0.1:9000` + `use_path_request_style`
  （本地无虚拟主机 DNS，必须路径式寻址）
- **Supabase Storage**：先开启 S3 协议（本地 `supabase/config.toml` 的
  `[storage.s3_protocol] enabled = true`；云端在 dashboard 的 Storage →
  S3 Access Keys 页面生成一对 S3 凭据），拿到 endpoint 与 region 后用任意
  S3 兼容工具挂载。**注意：Supabase 的 S3 凭据绕过 RLS、拥有全桶权限，只能
  放在服务端，绝不能进浏览器 / 客户端**

## 通用方案：rclone mount

一个工具覆盖 OSS / S3 / R2 / MinIO / Supabase 等几乎所有对象存储：

```bash
rclone config                                   # 交互生成 rclone.conf
rclone mount <remote>:<prefix> /mnt/...         # 挂载
```

- 配置存在 `rclone.conf`；密码默认以 `rclone obscure` 混淆存储（注意：混淆
  可逆，不是加密——只是防眼睛，不是防窃取）
- 生产可完全绕开配置文件：用环境变量注入，如
  `RCLONE_CONFIG_<remote>_TYPE=s3`、`RCLONE_CONFIG_<remote>_ACCESS_KEY_ID=...`，
  配合密钥管理注入，明文不落盘

## Security Key 通用处理原则（总结）

1. **不把 AK/SK 明文写进命令行参数** —— `ps` 可见、shell 历史残留，等于泄露
1. 凭据来源优先级：**实例 / 云角色 > 外部进程取凭据（credential_process）>
   环境变量 > 独立密码文件（`chmod 600`）> 混淆存储（obscure）**
1. **最小权限**：专用 RAM / IAM 用户，只授目标 bucket，禁用主账号 AK
1. 生产优先临时凭证（STS / 角色），避免长期 AK 常驻；临时凭证自动过期
1. 自动挂载（fstab / systemd）的凭据单独管理：fstab 里写密码文件路径而非
   明文，systemd 用 `EnvironmentFile` 或注入环境变量
1. **泄露即吊销**：RAM 删除 / 停用 AccessKey、R2 删除 API Token、Supabase
   重新生成 S3 Keys

## 参考

- OSSFS2：[github.com/aliyun/ossfs](https://github.com/aliyun/ossfs)（main =
  OSSFS2）、[OSSFS2 官方文档](https://help.aliyun.com/zh/oss/developer-reference/ossfs-2-0)、
  [Mount Options](https://www.alibabacloud.com/help/en/oss/developer-reference/description-of-mount-options)
- s3fs-fuse：[s3fs-fuse/s3fs-fuse](https://github.com/s3fs-fuse/s3fs-fuse)
- mountpoint-s3：AWS 官方文档（Mountpoint for Amazon S3）
- rclone：[rclone.org](https://rclone.org/)
- 相关文档：[基本用法](./basic-usage.md)、[供应商对比](./vendors-comparison.md)、
  [签名 URL](./signed-url.md)
