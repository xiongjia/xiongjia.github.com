---
title: NestJS 源码阅读指南
tags:
  - research
  - tech
categories:
  - dev
---

> **⚠️ 免责声明**: 本文档由 AI 自动生成，仅供参考学习使用。

# NestJS Module 注入原理

## 核心概念

NestJS 的依赖注入（DI）系统是其核心特性，基于 TypeScript 装饰器和元数据实现。

### 主要组件

| 组件              | 文件                           | 职责                                   |
| ----------------- | ------------------------------ | -------------------------------------- |
| `NestContainer`   | `injector/container.ts`        | 全局容器，管理所有模块                 |
| `Module`          | `injector/module.ts`           | 单个模块，管理其 providers/controllers |
| `Injector`        | `injector/injector.ts`         | 依赖解析和实例化                       |
| `InstanceWrapper` | `injector/instance-wrapper.ts` | Provider 的包装器，包含实例元数据      |
| `InstanceLoader`  | `injector/instance-loader.ts`  | 批量创建实例                           |

## 整体流程

```
AppModule 定义
    ↓
NestFactory.create()
    ↓
Container.addModule()     // 注册模块到容器
    ↓
InstanceLoader.createInstancesOfDependencies()
    ↓
Injector.loadInstance()   // 解析并实例化每个 Provider
    ↓
resolveConstructorParams() → 读取 PARAMTYPES_METADATA
    ↓
new Class(...dependencies)  // 实例化
```

## 依赖解析原理

### 1. 装饰器收集元数据

```typescript
// 使用 @Injectable() 标记
@Injectable()
class UsersService {
  constructor(
    private readonly usersRepository: UsersRepository,  // 依赖 A
    private readonly logger: LoggerService               // 依赖 B
  ) {}
}

// 编译后，NestJS 通过 reflect-metadata 存储：
Reflect.defineMetadata(PARAMTYPES_METADATA, [UsersRepository, LoggerService], UsersService);
Reflect.defineMetadata(OPTIONAL_DEPS_METADATA, [false, false], UsersService);
```

关键常量 (from `@nestjs/common/constants`):

- `PARAMTYPES_METADATA` — 构造函数参数类型
- `OPTIONAL_DEPS_METADATA` — 可选依赖标记
- `SELF_DECLARED_DEPS_METADATA` — 自定义注入 token
- `PROPERTY_DEPS_METADATA` — 属性注入

### 2. Injector 解析依赖

```typescript
// injector.ts:440 - 读取构造函数参数
public reflectConstructorParams<T>(type: Type<T>): any[] {
  const paramtypes = Reflect.getMetadata(PARAMTYPES_METADATA, type) || [];
  return Array.from(paramtypes);
}
```

### 3. 递归解析依赖树

```typescript
// injector.ts:128 - 加载实例
public async loadInstance<T>(
  wrapper: InstanceWrapper<T>,
  collection: Map<InjectionToken, InstanceWrapper>,
  moduleRef: Module,
) {
  // 1. 解析构造函数参数
  // 2. 递归解析每个依赖的实例
  // 3. 创建最终实例
  await this.resolveConstructorParams<T>(wrapper, moduleRef, inject, callback);
}
```

## Provider 类型处理

### Class Provider

```typescript
@Injectable()
class UsersService {}

// 自动解析: new UsersService(instanceA, instanceB)
```

### Value Provider

```typescript
const config = { apiKey: 'xxx' };
providers: [{ provide: 'CONFIG', useValue: config }]
// 注入: ctx.get('CONFIG') → { apiKey: 'xxx' }
```

### Factory Provider

```typescript
providers: [{
  provide: 'CACHE',
  useFactory: (logger: LoggerService) => new CacheService(logger),
  inject: [LoggerService]  // 显式声明依赖
}]
```

### Token Provider

```typescript
providers: [{
  provide: 'USERSRepository',
  useClass: TypeORMRepository,
}]
// 解析: token 'USERSRepository' → TypeORMRepository 实例
```

## 实例作用域 (Scope)

| Scope       | 说明                       |
| ----------- | -------------------------- |
| `DEFAULT`   | 单例，整个应用共享         |
| `REQUEST`   | 每个请求创建一个实例       |
| `TRANSIENT` | 每次注入创建一个新实例     |
| `SINGLETON` | 应用启动时创建，只创建一次 |

## Module 之间的关系

### 导入 (imports)

```typescript
@Module({
  imports: [DatabaseModule],  // 导入 DatabaseModule 的 exported providers
})
class AppModule {}
```

### 导出 (exports)

```typescript
@Module({
  exports: [UsersService],  // 导出给其他模块使用
})
class UsersModule {}
```

### 全局模块 (global)

```typescript
@Module({})
@Global()
class DatabaseModule {}
// 全局可用，无需导入
```

## 请求作用域 (Request Scope) 实现

```typescript
// packages/core/injector/instance-wrapper.ts:36
export interface ContextId {
  readonly id: number;
  payload?: unknown;
  getParent?(info: HostComponentInfo): ContextId;
}
```

每个请求有唯一的 `ContextId`，Transient/Request Scope 的 Provider 会为每个 contextId 创建独立实例。

## InstanceWrapper 标识与防重复初始化

### 标识机制

`InstanceWrapper` 使用三重标识来唯一确定一个 Provider/Service:

```typescript
// packages/core/injector/instance-wrapper.ts:61-80
export class InstanceWrapper<T = any> {
  public readonly token: InjectionToken;     // ① Injection Token (主要标识，用于 Map 查找)
  public readonly name: any;               // ② 名称 (用于日志/调试)
  private readonly [INSTANCE_ID_SYMBOL]: string;  // ③ 内部 UUID (唯一ID)
}
```

| 标识    | 用途                                  |
| ------- | ------------------------------------- |
| `token` | Provider 的唯一标识，用于 Map 查找    |
| `name`  | 人类可读的名称 (通常是 token 的 name) |
| `id`    | 内部生成的 UUID，用于追踪             |

### 防重复初始化机制

NestJS 通过三层检查避免重复初始化:

**1. Module 级防重** (`packages/core/injector/container.ts:109-114`)

```typescript
if (this.modules.has(token)) {
  return {
    moduleRef: this.modules.get(token)!,
    inserted: true,  // 已存在，跳过
  };
}
```

**2. Provider 级防重** (`packages/core/injector/module.ts`)

```typescript
public addProvider(provider: Provider, enhancerSubtype?): string | symbol {
  if (this._providers.has(token)) {
    return token;  // 直接返回，不重复添加
  }
  // ...
}
```

**3. 实例状态检查** (`packages/core/injector/injector.ts:162`)

```typescript
if (instanceHost.isResolved) {
  return settlementSignal.complete();  // 已解析，直接返回
}
```

### 关键状态字段

```typescript
// packages/core/injector/instance-wrapper.ts:42-48
export interface InstancePerContext<T> {
  instance: T;
  isResolved?: boolean;    // 是否已解析
  isPending?: boolean;     // 是否正在解析中 (防止并发重复解析)
  donePromise?: Promise<unknown>;
  isConstructorCalled?: boolean;
}
```

### 防重复初始化流程图

```
addProvider(MyService)
    ↓
检查 _providers.has(MyService.token)
    ↓
已存在 → 直接返回，不重复创建 InstanceWrapper
    ↓
不存在 → 创建新的 InstanceWrapper
    ↓
loadInstance()
    ↓
检查 instanceHost.isResolved
    ↓
已解析 → 直接返回
    ↓
未解析 → 执行 resolveConstructorParams → 实例化
```

### 并发保护

当多个请求同时需要解析同一个依赖时:

```typescript
// packages/core/injector/injector.ts:141
if (instanceHost.isPending) {
  // 另一个请求正在解析，等待完成后再返回
  return instanceHost.donePromise!.then((err?: unknown) => {
    if (err) throw err;
  });
}
```

### 存储结构

```
NestContainer (全局容器)
    └── ModulesContainer (Map<string, Module>)
            └── Module
                    └── _providers (Map<token, InstanceWrapper>)
                            └── InstanceWrapper
                                    └── values (WeakMap<ContextId, InstancePerContext>)
                                            └── instance (实际对象)
```

单例模式时，所有请求共享同一个实例，存储在 `STATIC_CONTEXT` 对应的 `InstancePerContext` 中。

## 核心文件

| 文件                           | 说明               |
| ------------------------------ | ------------------ |
| `injector/container.ts`        | 全局容器，模块注册 |
| `injector/injector.ts`         | 依赖解析核心逻辑   |
| `injector/instance-loader.ts`  | 批量实例加载       |
| `injector/instance-wrapper.ts` | 实例包装器         |
| `injector/module.ts`           | 模块定义和管理     |

## 调试技巧

```typescript
// 1. 查看已注册的模块
const container = app.get(NestApplicationContext).container;
console.log(container.getModules());

// 2. 查看 Provider 实例
const moduleRef = container.getModuleByKey('AppModule');
console.log(moduleRef.providers);

// 3. 打印依赖树
// 在 injector.ts 的 loadInstance 中添加日志
```

## 总结

1. **元数据驱动** — 通过 `reflect-metadata` 在编译时存储依赖信息
1. **递归解析** — 类似树的先序遍历，解析完依赖才实例化
1. **容器管理** — `NestContainer` 管理所有模块，`Module` 管理单个模块的 providers
1. **作用域控制** — 通过 `ContextId` 隔离不同请求的实例
