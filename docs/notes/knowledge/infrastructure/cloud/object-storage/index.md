---
hide:
  - navigation
title: Object Storage
tags:
  - knowledge
  - cloud
  - object-storage
categories:
  - infrastructure
---

# :material-database: Object Storage

对象存储知识体系 —— 以 AWS S3、Cloudflare R2、阿里云 OSS、Google Cloud
Storage、Supabase Storage、MinIO 等对象存储服务的**通用概念与机制**为主，
覆盖基本用法、签名与访问控制、权限体系、供应商差异等长期演进的知识点。

## Docs

| Docs                                             | Description                                                      |
| ------------------------------------------------ | ---------------------------------------------------------------- |
| [基本用法（Basic Usage）](./basic-usage.md)      | 概念与常用操作：列桶、列对象、上传下载、签名 URL、删除、通用机制 |
| [挂载 Bucket（FUSE Mount）](./mount-bucket.md)   | FUSE 挂载：OSS（ossfs2 + Security Key）、S3/mountpoint、rclone   |
| [签名 URL（Signed URL）](./signed-url.md)        | 限时下载 / 客户端直传的原理与签名算法（V1/V2 → SigV4）           |
| [供应商对比（Vendors）](./vendors-comparison.md) | S3/R2/OSS/Supabase/MinIO 差异：API、SDK、签名、权限、计费、选型  |
| [数据迁移（Migration）](./data-migration.md)     | 跨厂商搬迁（如 R2 → MinIO）：rclone 流程、客户端兼容性与注意事项 |
