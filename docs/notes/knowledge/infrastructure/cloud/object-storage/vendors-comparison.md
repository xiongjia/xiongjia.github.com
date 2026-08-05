---
hide:
  - navigation
title: 对象存储供应商对比（S3 / R2 / OSS / Supabase / MinIO）
tags:
  - knowledge
  - cloud
  - object-storage
  - vendors
categories:
  - infrastructure
---

# 对象存储供应商对比（S3 / R2 / OSS / Supabase / MinIO）

> 本文对比主流对象存储供应商的**关键差异**，用于选型与切换。
> 基本用法见 [基本用法（Basic Usage）](./basic-usage.md)，
> 签名 URL 原理见 [签名 URL（Signed URL）](./signed-url.md)。
> 结论基于仓库内 3 个客户端原型（`prototypes/ali-oss-client`、
> `prototypes/r2-client`、`prototypes/supabase-storage-client`）的端到端实测，
> 其中 r2-client 的本地测试跑在 MinIO 上。

## 概览对比表

| 维度                    | AWS S3（参照系）     | Cloudflare R2                   | 阿里云 OSS                 | Supabase Storage         | MinIO                       |
| ----------------------- | -------------------- | ------------------------------- | -------------------------- | ------------------------ | --------------------------- |
| 定位                    | 云对象存储事实标准   | Cloudflare 边缘对象存储         | 阿里云对象存储             | Postgres 生态的存储附件  | 自托管 S3 兼容服务器        |
| API 形态                | S3 原生              | **S3 兼容**                     | 原生 API（非 S3）          | REST API（可选 S3 协议） | **S3 兼容**                 |
| 常用 SDK                | `@aws-sdk/client-s3` | `@aws-sdk/client-s3`            | `ali-oss`                  | `@supabase/supabase-js`  | `@aws-sdk/client-s3` / `mc` |
| 签名 URL                | Presigned（SigV4）   | Presigned（SigV4）              | 签名 URL（V1/V4）          | Signed URL（服务端过期） | Presigned（S3 兼容）        |
| Content-Type 是否被签名 | 否                   | 否                              | **是（V1）**               | 否                       | 否                          |
| 凭证                    | IAM User / Role      | R2 API Token                    | RAM AccessKey / STS        | anon key + service_role  | root / 自定义用户           |
| 权限模型                | IAM Policy           | Token 权限层级                  | RAM Policy                 | Postgres RLS             | IAM 风格 Policy             |
| region                  | 必选                 | `auto`（忽略）                  | 必选                       | 无（hosted）/ 固定本地   | `us-east-1` 默认            |
| 地址风格                | virtual-hosted       | virtual-hosted                  | virtual-hosted             | REST 路径                | 需 `forcePathStyle`         |
| 本地开发                | LocalStack（第三方） | 无官方 → 用 MinIO               | 无官方 emulator            | `supabase start` 全栈    | 本身就是本地服务器          |
| 免费额度                | 12 个月免费层        | 免费存储额度 + **零出口流量费** | 新用户免费额度（按量计费） | 免费层                   | 开源（Apache 2.0）          |

## 关键差异

### 1. S3 兼容 = 生态红利（最大的差异）

- **R2 与 MinIO 走 S3 兼容 API**：直接用标准 `@aws-sdk/client-s3`，只需改
  endpoint / credentials / region / forcePathStyle 四个配置即可切换，业务代码
  零改动
- **OSS 与 Supabase 走各自原生 SDK**：`ali-oss`、`@supabase/supabase-js`，
  方法名与返回结构不通用，换厂商要重写客户端
- 意义：选 S3 兼容供应商，SDK、工具（aws cli、mc）、生态组件（CDN、图片处理）
  全部通用，数据搬迁也可用 S3 兼容工具

### 2. 签名 URL 的差异

| 差异              | OSS（V1）                                                                           | S3 / R2 / MinIO                                      | Supabase                                                   |
| ----------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------- |
| Content-Type 绑定 | **绑定**：消费端必须带与签发时相同的 Content-Type，否则 `403 SignatureDoesNotMatch` | **不绑定**：裸 curl PUT 即可（传了只影响对象元数据） | 不绑定                                                     |
| 过期机制          | 客户端签名过期（URL 带 Expires）                                                    | 客户端签名过期（X-Amz-Expires）                      | **服务端决定**（上传 URL 无客户端 expiry，token 存服务端） |
| 上传 URL 覆盖     | 直接覆盖                                                                            | 直接覆盖                                             | 需 `upsert: true`，否则 `Duplicate`                        |

- OSS 的坑最常见：生成 PUT 签名 URL 时必须带上 Content-Type，消费端必须原样
  发送（[signed-url.md](./signed-url.md) 有完整的 curl 验证）
- Supabase 签名上传 URL 没有客户端过期时间，有效期由 Storage API 服务端决定
  （不同版本默认值不同）

### 3. 权限模型（Permission Model）

- **身份策略（OSS / AWS）**：RAM / IAM 用户 + Policy 绑定，粒度到 bucket / 操作；
  生产建议用 STS 临时凭证或角色替代长期 AccessKey
- **Token 权限（R2）**：R2 API Token 自带权限范围 —— **Admin Read & Write**
  才能列桶 / 建桶 / 删桶；**Object Read & Write** 只能做对象级操作
  （`ListBuckets` 会 403）；生产应把 Token 范围缩到单个 bucket
- **数据库级 RLS（Supabase）**：权限用 Postgres RLS Policy 表达；anon key 是
  **公开 JWT**（设计上就进浏览器），**service_role key 绕过 RLS、必须留在
  服务端**。注意：新版 Storage **默认没有任何 RLS policy**，所有非
  service_role 请求都会被拒 —— 必须先建 policy 才能用 anon key 访问

### 4. Region 与 Endpoint

- **OSS**：region 必选（如 `oss-cn-hangzhou`），endpoint 由 region 派生
- **R2**：endpoint 由 **Account ID** 派生
  （`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`），region 传 `auto`（被忽略）
- **MinIO**：本地无虚拟主机 DNS，必须 `forcePathStyle: true`，region 用默认
  `us-east-1`
- **Supabase**：本地全栈固定 `http://127.0.0.1:64321`（API 代理端口），
  Storage 挂在 `/storage/v1`

### 5. 本地开发与测试

- **MinIO 是 S3 生态的本地标准**：没有官方 R2 / AWS 本地 emulator 时，Docker
  起一个 MinIO 即可测所有 S3 兼容供应商（r2-client 原型就是这么测的，代码零
  改动）；数据存在 named volume 里可持久化
- **Supabase 自带本地全栈**：`supabase start` 拉起 Postgres + PostgREST +
  Storage + Auth + Studio，anon key 可自动从 `supabase status` 读取
- **OSS 没有官方 emulator**：本地测试最麻烦，只能连真实服务（或依赖第三方模拟）

### 6. 免费额度与出口流量

- **R2 的杀手锏：零出口流量费（egress free）** —— 对"下载多"的场景（图床、
  静态资源）成本优势明显；另有免费存储额度
- **OSS**：按量计费（存储 + 流量 + 请求数），新用户有免费额度
- **Supabase**：免费层（带存储配额），超出收费
- **MinIO**：开源免费，自托管成本只有机器

## 选型建议

| 场景                                    | 推荐             | 理由                                      |
| --------------------------------------- | ---------------- | ----------------------------------------- |
| 需要 S3 生态兼容 / 多供应商迁移         | R2 / MinIO / AWS | 标准 SDK 通用，切换成本低                 |
| 下载流量大、成本敏感（图床 / CDN 资源） | R2               | 零出口流量费                              |
| 阿里云生态（ECS 同地域内网、RAM、STS）  | OSS              | 内网免流量、与云生态整合                  |
| 已有 Postgres / Supabase 应用           | Supabase Storage | 与 Auth / RLS 深度集成，无需额外存储服务  |
| 本地开发 / CI 测试 S3 兼容代码          | MinIO            | Docker 一键起，行为与 S3 一致             |
| 需要细粒度、可追溯的访问控制            | 任一 + 签名 URL  | 权限在签名 URL 层收敛（见 signed-url.md） |

> 一句话结论：**默认选 S3 兼容**（R2 / MinIO），生态红利最大；只有深度绑定
> 某个平台（阿里云、Supabase）时才用其原生 SDK。

## 参考

- 相关文档：[基本用法（Basic Usage）](./basic-usage.md)、
  [签名 URL（Signed URL）](./signed-url.md)
- 实测来源：[ali-oss-client](../../../../../notes/prototypes.md#ali-oss-client) ·
  [r2-client](../../../../../notes/prototypes.md#r2-client) ·
  [supabase-storage-client](../../../../../notes/prototypes.md#supabase-storage-client)
  —— 三个原型操作完全同构，差异只在 SDK 与配置
