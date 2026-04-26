---
title: Better Auth 源码阅读指南
tags:
  - research
  - tech
categories:
  - dev
---

> **⚠️ 免责声明**: 本文档由 AI 自动生成，仅供参考学习使用。

# Better Auth 源码阅读指南

## 项目概述

Better Auth 是一个 **框架无关 (framework-agnostic)** 的 TypeScript 认证/授权框架，支持 Node.js、Bun、Deno 和 Cloudflare Workers。

## 核心包结构

```
packages/
├── better-auth/          # 主库入口
├── core/                # 核心类型和共用工具
├── cli/                 # CLI 工具
└── [adapter-*]/         # 数据库适配器 (drizzle, prisma, kysely, mongo, ...)
    [plugin-*]/          # 插件 (passkey, oauth-provider, 2fa, ...)
```

## 核心入口路径

### 1. 库入口（了解整体结构）
- [packages/better-auth/src/index.ts](packages/better-auth/src/index.ts) — 主导出
- [packages/better-auth/src/auth/full.ts](packages/better-auth/src/auth/full.ts) — `betterAuth()` 函数入口
- [packages/better-auth/src/auth/base.ts](packages/better-auth/src/auth/base.ts) — `createBetterAuth()` 核心逻辑

### 2. 请求处理流程
- [packages/better-auth/src/api/index.ts](packages/better-auth/src/api/index.ts) — 路由注册 (`getEndpoints`, `router`)
- [packages/better-auth/src/api/routes/](packages/better-auth/src/api/routes/) — 所有 endpoint handler（signInSocial, signOut, getSession 等）

### 3. Context 初始化
- `packages/better-auth/src/context/` — 请求上下文解析

### 4. 核心类型定义
- [packages/better-auth/src/types/](packages/better-auth/src/types/) — 主库类型
- [packages/core/src/types/](packages/core/src/types/) — 核心共享类型（BetterAuthOptions 等）

## 推荐阅读顺序

### 第一步：理解核心抽象

```
1. better-auth/src/auth/full.ts
   → betterAuth() 入口函数

2. better-auth/src/auth/base.ts
   → createBetterAuth() 核心实现
   → 理解 auth context 初始化和请求处理流程

3. better-auth/src/api/index.ts (前 100 行)
   → getEndpoints() 和 router()
   → 了解有哪些 endpoints 注册
```

### 第二步：理解请求处理

```
1. better-auth/src/api/index.ts (273-402 行)
   → router() 函数
   → onRequest / onResponse 中间件流程
   → 错误处理

2. better-auth/src/api/middlewares/
   → originCheckMiddleware（CSRF 防护）
```

### 第三步：理解核心 Features

```
1. Session 管理
   → packages/better-auth/src/api/routes/getSession.ts
   → packages/better-auth/src/api/routes/listSessions.ts
   → packages/better-auth/src/api/routes/revokeSession.ts

2. Email 认证流程
   → packages/better-auth/src/api/routes/signUpEmail.ts
   → packages/better-auth/src/api/routes/signInEmail.ts
   → packages/better-auth/src/api/routes/verifyEmail.ts

3. OAuth / Social Login
   → packages/better-auth/src/api/routes/signInSocial.ts
   → packages/better-auth/src/api/routes/callbackOAuth.ts

4. Password 管理
   → packages/better-auth/src/api/routes/changePassword.ts
   → packages/better-auth/src/api/routes/setPassword.ts
   → packages/better-auth/src/api/routes/resetPassword.ts
```

### 第四步：理解 Plugin 机制

```
1. packages/core/src/plugins/
   → 理解 BetterAuthPlugin 接口定义

2. 查看已有插件实现
   → packages/passkey/
   → packages/oauth-provider/
```

## 关键文件速查

| 功能 | 文件 |
|------|------|
| 主入口 | `better-auth/src/auth/full.ts` |
| 请求路由 | `better-auth/src/api/index.ts` |
| Session 读取 | `better-auth/src/api/routes/getSession.ts` |
| 登录注册 | `better-auth/src/api/routes/signUpEmail.ts` |
| Social Login | `better-auth/src/api/routes/signInSocial.ts` |
| CSRF 防护 | `better-auth/src/api/middlewares/` |
| 类型定义 | `core/src/types/` |

## 开发测试命令

```bash
# 单个测试文件
pnpm vitest packages/better-auth/src/auth/full.test.ts -t "pattern"

# 类型检查
pnpm typecheck
```

## 开发约束（来自 CLAUDE.md）

- **禁止使用 `any` 和 `class`**
- 使用 `Uint8Array` 而非 `Buffer`
- 使用 `import type` 进行类型导入
- 使用 `node:` protocol 引入 Node.js 内置模块
- 必须为 bug fix 和新功能编写测试
