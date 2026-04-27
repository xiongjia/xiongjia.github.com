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

## API Key 插件

包: `packages/api-key/`

### 功能概述

API Key 插件通过 **Hook 拦截 + 伪造 Session** 的方式，让 API Key 可以像普通 Session 一样参与权限控制。

### 工作流程

```
请求 (x-api-key: xxx)
    ↓
before hook 拦截 (matcher 检测 header)
    ↓
validateApiKey() 验证 key
    ↓
伪造 session → 注入 ctx.context.session
    ↓
后续 endpoint 正常执行 (sessionMiddleware 通过)
```

### 核心文件

| 文件 | 用途 |
|------|------|
| `src/index.ts` | 插件主入口，定义 before hook |
| `src/schema.ts` | 数据库模型定义 |
| `src/routes/verify-api-key.ts` | `validateApiKey()` 验证逻辑 |
| `src/routes/create-api-key.ts` | 创建 API Key endpoint |
| `src/routes/list-api-keys.ts` | 列出 API Keys |
| `src/routes/delete-api-key.ts` | 删除 API Key |

### 密钥存储模型

```typescript
apikey: {
  fields: {
    key: { type: "string" },           // SHA-256 hash 存储
    prefix: { type: "string" },         // 前缀 (如 "sk_live_")
    start: { type: "string" },          // 显示前几位字符
    referenceId: { type: "string" },    // 关联 userId/orgId
    enabled: { type: "boolean" },       // 是否启用
    expiresAt: { type: "date" },        // 过期时间
    remaining: { type: "number" },      // 剩余请求次数
    refillInterval: { type: "number" }, // 自动补充间隔
    refillAmount: { type: "number" },   // 自动补充数量
    rateLimitMax: { type: "number" },   // 速率限制
    permissions: { type: "string" },    // JSON 权限配置
    metadata: { type: "string" },       // 自定义元数据
  }
}
```

### metadata 用途

存储与 API Key 关联的任意自定义数据（需 `enableMetadata: true` 开启）:

```typescript
// 创建时附带 metadata
const { data: apiKey } = await client.apiKey.create({
  name: "Production Key",
  metadata: {
    environment: "production",
    team: "backend",
    owner: "john@example.com",
  }
});

// 验证时返回 metadata
const result = await auth.api.verifyApiKey({ key: "..." });
console.log(result.key.metadata);
// { environment: "production", team: "backend", ... }
```

典型用途:
- 环境标识 (`{ env: "production" }`)
- 负责人记录 (`{ owner: "john@company.com" }`)
- 成本中心 (`{ costCenter: "CC-1234" }`)

### 验证逻辑 (validateApiKey)

```typescript
async function validateApiKey({ hashedKey, ... }) {
  // 1. 数据库查找
  const apiKey = await getApiKey(ctx, hashedKey, opts);

  // 2. 启用状态检查
  if (apiKey.enabled === false) throw APIError("UNAUTHORIZED", "KEY_DISABLED");

  // 3. 过期时间检查 (自动删除过期 key)
  if (apiKey.expiresAt && now > expiresAt) throw APIError("UNAUTHORIZED", "KEY_EXPIRED");

  // 4. 剩余次数检查 (用完可自动删除)
  if (apiKey.remaining === 0) throw APIError("TOO_MANY_REQUESTS", "USAGE_EXCEEDED");

  // 5. 速率限制检查
  if (isRateLimited(apiKey)) throw APIError("UNAUTHORIZED", "RATE_LIMITED");

  // 6. 权限验证 (可选)
  if (permissions) r.authorize(permissions);

  // 7. 更新使用统计 (remaining--)
  // 更新数据库...
}
```

### 配置选项

```typescript
apiKey({
  configurations: [{
    apiKeyHeaders: "x-api-key",           // 默认 header 名
    defaultKeyLength: 64,                  // 密钥长度
    enableMetadata: true,                  // 开启 metadata
    disableKeyHashing: false,             // 是否 hash 存储
    rateLimit: {
      enabled: true,
      timeWindow: 1000 * 60 * 60 * 24,  // 24小时窗口
      maxRequests: 1000,
    },
    keyExpiration: {
      defaultExpiresIn: 60 * 60 * 24 * 365, // 1年
    },
    enableSessionForAPIKeys: true,        // 伪造 session
  }]
})
```

### Client 端使用

```typescript
// 1. 安装插件
import { apiKey } from "@better-auth/api-key";
import { apiKeyClient } from "@better-auth/api-key/client";

// 2. 服务端配置
const auth = betterAuth({
  plugins: [apiKey()]
});

// 3. 客户端配置
const authClient = createAuthClient({
  plugins: [apiKeyClient()]
});

// 4. 创建 API Key
const { data: apiKey } = await authClient.apiKey.create({
  name: "My Key",
  expiresIn: 60 * 60 * 24 * 30, // 30 days
});

// 5. 使用 API Key 请求 (自动伪造 session)
const session = await auth.api.getSession({
  headers: { "x-api-key": apiKey.key }
});
```

### Endpoints

| Endpoint | Method | 用途 |
|----------|--------|------|
| `/api-key/create` | POST | 创建 API Key |
| `/api-key/get` | GET | 获取单个 Key |
| `/api-key/list` | GET | 列出所有 Key |
| `/api-key/update` | POST | 更新 Key |
| `/api-key/delete` | POST | 删除 Key |
| `/api-key/verify` | POST | 验证 Key |

## 开发约束（来自 CLAUDE.md）

- **禁止使用 `any` 和 `class`**
- 使用 `Uint8Array` 而非 `Buffer`
- 使用 `import type` 进行类型导入
- 使用 `node:` protocol 引入 Node.js 内置模块
- 必须为 bug fix 和新功能编写测试
