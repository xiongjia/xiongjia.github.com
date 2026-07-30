---
title: TRIP 项目核心原理与代码阅读指南
tags:
  - research
  - tech
categories:
  - dev
---

# TRIP 项目核心原理与代码阅读指南

## 项目概述

**TRIP** (Tourism and Recreational Interest Points) 是一个自托管的极简地图追踪器与行程规划工具。

- **GitHub**: https://github.com/itskovacs/trip
- **前端**: Angular (位于 `src/` 目录)
- **后端**: Python/FastAPI (位于 `backend/trip/` 目录)

______________________________________________________________________

## 目录结构

```
docs/notes/research/external/trip/
├── src/                          # Angular 前端
│   ├── src/app/                  # Angular 组件、服务
│   └── ...
├── backend/trip/                 # Python 后端 (FastAPI)
│   ├── main.py                   # FastAPI 应用入口
│   ├── config.py                 # 配置管理 (Pydantic Settings)
│   ├── security.py               # 认证: JWT/TOTP/OIDC
│   ├── deps.py                   # 依赖注入 (SessionDep)
│   ├── models/
│   │   └── models.py             # SQLModel ORM 模型定义
│   ├── db/
│   │   └── core.py               # 数据库连接与迁移
│   └── routers/                  # API 路由
│       ├── auth.py               # 认证相关
│       ├── trips.py              # 行程 CRUD
│       ├── places.py             # 地点 CRUD
│       ├── categories.py         # 分类
│       ├── token.py              # Token 管理
│       ├── providers.py          # 地图 provider
│       ├── settings.py           # 设置
│       └── admin.py              # 管理接口
└── docs/                         # Docusaurus 文档
```

______________________________________________________________________

## 核心原理

### 1. 认证与授权

**技术栈**: JWT + Argon2 + TOTP (可选) + OIDC (可选)

| 文件              | 职责                                                                                               |
| ----------------- | -------------------------------------------------------------------------------------------------- |
| `security.py`     | `hash_password()`, `verify_password()`, `create_access_token()`, `verify_totp_code()`, OIDC 客户端 |
| `deps.py`         | `SessionDep` (数据库会话 DI), `get_current_username()` (从 JWT 提取当前用户)                       |
| `routers/auth.py` | 登录/注册/Token 刷新                                                                               |

**Token 流程**:

1. 用户登录 → `verify_password()` 验证密码 → `create_tokens()` 生成 access + refresh token
1. 后续请求携带 `Authorization: Bearer <token>`
1. `oauth_password_scheme` + `get_current_username()` 从 JWT 解码出 `sub` (username)

**关键代码路径**: `deps.py:get_current_username()` → `security.py:verify_password()` → `config.py:SECRET_KEY`

______________________________________________________________________

### 2. 数据模型

**核心模型** (`models/models.py`):

| 模型                                        | 关系                                                    |
| ------------------------------------------- | ------------------------------------------------------- |
| `User`                                      | 认证主体，可选 TOTP secret                              |
| `Place`                                     | POI (兴趣点)，含坐标、分类、图片                        |
| `Trip`                                      | 行程，含多天 `TripDay`                                  |
| `TripDay`                                   | 行程中的一天，含多个 `TripItem`                         |
| `TripItem`                                  | 行程项 (可标记状态: pending/booked/constraint/optional) |
| `TripShare`                                 | 分享链接 (token 机制)                                   |
| `TripMember`                                | 行程成员                                                |
| `TripInvitation`                            | 邀请                                                    |
| `Image`                                     | 图片                                                    |
| `Category`                                  | 地点分类 (默认 8 类)                                    |
| `TripPackingListItem` / `TripChecklistItem` | 行李/清单                                               |

**关键设计**:

- 使用 `sqlmodel` (SQLAlchemy + Pydantic 混合)
- 软删除通过 `deleted_at` timestamp 实现
- `after_commit` hook 清理待删除文件

______________________________________________________________________

### 3. 数据库与迁移

**技术栈**: SQLite + Alembic

| 文件               | 职责                                                        |
| ------------------ | ----------------------------------------------------------- |
| `db/core.py`       | `get_engine()` (单例), `init_and_migrate_db()` (启动时迁移) |
| `alembic.ini`      | Alembic 配置                                                |
| `db/migrations.py` | 数据迁移 (填充默认值等)                                     |

**迁移流程** (`main.py:lifespan`):

1. 启动时调用 `init_and_migrate_db()`
1. 检查 SQLite 文件是否存在
1. 不存在 → `command.upgrade("head")`
1. 存在但无 Alembic 版本表 → `command.stamp("b2ed4bf9c1b2")` (标记初始版本)
1. 已有版本 → `command.upgrade("head")`

______________________________________________________________________

### 4. API 路由设计

**RESTful 风格**，前缀 `/api/`

| Router          | 路由                                             | 说明                      |
| --------------- | ------------------------------------------------ | ------------------------- |
| `auth.py`       | `/auth/login`, `/auth/register`, `/auth/refresh` | 认证                      |
| `trips.py`      | `/api/trips`                                     | 行程 CRUD、分享、成员管理 |
| `places.py`     | `/api/places`                                    | 地点 CRUD                 |
| `categories.py` | `/api/categories`                                | 分类管理                  |
| `token.py`      | `/token`                                         | Token 操作                |
| `providers.py`  | `/api/providers`                                 | 地图 provider             |
| `settings.py`   | `/api/settings`                                  | 用户设置                  |
| `admin.py`      | `/api/admin`                                     | 管理功能                  |

**权限检查模式** (`deps.py` + `security.py:verify_exists_and_owns`):

```python
def verify_exists_and_owns(username: str, obj) -> None:
    if not obj:
        raise HTTPException(status_code=404)
    if obj.user != username:
        raise HTTPException(status_code=403)
```

______________________________________________________________________

### 5. 前端架构 (Angular)

**主要目录** (`src/src/app/`):

- `app.component.ts` - 根组件
- `components/` - 共享组件
- `pages/` - 页面 (map, trips, places, settings 等)
- `services/` - API 服务 (trip.service.ts, place.service.ts 等)
- `models/` - TypeScript 接口定义
- `shared/map.ts` - 地图相关工具函数

**关键特性**:

- Angular Service 进行 HTTP 调用后端 API
- 地图使用 Leaflet + leaflet.markercluster (聚合) + leaflet-contextmenu
- PWA 支持 (`ngsw-config.json`)

______________________________________________________________________

### 6. 地图处理

TRIP 的地图处理分两部分：**前端渲染** + **后端搜索/路由**。

#### 前端 (Leaflet)

**核心文件**: `src/src/app/shared/map.ts`

| 函数                   | 用途                                        |
| ---------------------- | ------------------------------------------- |
| `createMap()`          | 初始化 Leaflet 地图，默认底图 CARTO Voyager |
| `placeToMarker()`      | 完整圆形标记 (含分类图标)                   |
| `placeToDotMarker()`   | 小圆点 (列表视图用)                         |
| `tripDayMarker()`      | 行程中的日程点                              |
| `toDotMarker()`        | 任意坐标点                                  |
| `gpxToPolyline()`      | 解析 GPX XML 绘制轨迹线                     |
| `openNavigation()`     | 调用 Google Maps 网页版导航                 |
| `createClusterGroup()` | 聚合标记组 (zoom < 11 时聚合成簇)           |

**底图**:

- 默认: CARTO Voyager (`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png`)
- 用户可配置: `User.custom_tile_layer` (自定义瓦片 URL)

**数据模型** (`models/models.py`):

- `User.map_provider` — "osm" 或 "google"
- `User.custom_tile_layer` — 自定义瓦片 URL
- `User.google_apikey` — Google API Key
- `User.map_lat/lng/zoom` — 地图初始位置

#### 后端 Provider 抽象

**目录**: `utils/providers/`

| 文件        | 职责                                                         |
| ----------- | ------------------------------------------------------------ |
| `base.py`   | 抽象基类 `BaseMapProvider`，定义接口 + encoded polyline 解码 |
| `osm.py`    | OpenStreetMap (Nominatim 搜索 + OSRM 路由)                   |
| `google.py` | Google Maps (Places API, Directions API)                     |

**OpenStreetMapProvider** (`osm.py`):

- 搜索: `https://nominatim.openstreetmap.org/search`
- 路由: `https://routing.openstreetmap.de/routed-{profile}/route/v1/driving`
- 支持 profile: `car`, `foot`, `bike`
- 地点分类映射: `TYPES_MAPPER` 将 OSM amenity/shop/tourism 标签映射到 TRIP 的 8 分类

**API 端点** (`routers/providers.py`):

| 端点                                                      | 功能                      |
| --------------------------------------------------------- | ------------------------- |
| `POST /api/completions/search`                            | 文本搜索地点              |
| `POST /api/completions/nearby`                            | 附近搜索 (仅 Google)      |
| `GET /api/completions/geocode`                            | 地址 → 边界框             |
| `POST /api/completions/route`                             | 路线规划                  |
| `POST /api/completions/bulk`                              | 批量导入 Google Maps 链接 |
| `POST /api/completions/mymaps-import`                     | Google My Maps KMZ 导入   |
| `POST /api/completions/takeout-import`                    | Google Takeout CSV 导入   |
| `GET /api/completions/google/resolve-shortlink/{link_id}` | 解析 Google 短链接        |

**批量处理**: `_process_batch()` 使用 `asyncio.Semaphore(4)` 限流，并发处理最多 4 个请求。

______________________________________________________________________

## 代码阅读顺序

推荐按以下顺序阅读核心代码:

### 阶段 1: 理解应用骨架

1. `main.py` - FastAPI 应用初始化、路由注册、中间件
1. `config.py` - 配置管理、环境变量

### 阶段 2: 理解认证流程

3. `deps.py` - 依赖注入模式
1. `security.py` - JWT、密码哈希、TOTP、OIDC

### 阶段 3: 理解数据层

5. `models/models.py` - ORM 模型定义 (Trip, Place, User 关系)
1. `db/core.py` - 数据库初始化与迁移

### 阶段 4: 理解业务逻辑

7. `routers/trips.py` - 行程核心逻辑 (最复杂)
1. `routers/places.py` - 地点 CRUD
1. `routers/auth.py` - 认证流程

### 阶段 5: 理解前端

10. Angular services (`src/src/app/services/`) - API 调用
01. Angular pages (`src/src/app/pages/`) - 页面组件

### 阶段 6: 理解地图

12. `shared/map.ts` - Leaflet 地图初始化、标记、GPX 绘制
01. `utils/providers/base.py` - Provider 抽象接口
01. `utils/providers/osm.py` - OSM 搜索与路由
01. `routers/providers.py` - 地图 API 端点

______________________________________________________________________

## 关键文件速查

| 目标           | 文件                      | 关键函数/类                                       |
| -------------- | ------------------------- | ------------------------------------------------- |
| JWT Token 验证 | `deps.py`                 | `get_current_username()`                          |
| 密码哈希       | `security.py`             | `hash_password()`, `verify_password()`            |
| 创建 Token     | `security.py`             | `create_access_token()`, `create_refresh_token()` |
| 数据库连接     | `db/core.py`              | `get_engine()`                                    |
| 启动迁移       | `db/core.py`              | `init_and_migrate_db()`                           |
| Trip 创建      | `routers/trips.py`        | `create_trip()`                                   |
| Place 创建     | `routers/places.py`       | `create_place()`                                  |
| 权限检查       | `security.py`             | `verify_exists_and_owns()`                        |
| 图片处理       | `utils/utils.py`          | `save_image_to_file()`, `patch_image()`           |
| 地图初始化     | `shared/map.ts`           | `createMap()`                                     |
| 地点搜索       | `routers/providers.py`    | `text_search()`                                   |
| 路线规划       | `utils/providers/osm.py`  | `get_route()`                                     |
| Provider 基类  | `utils/providers/base.py` | `BaseMapProvider`                                 |

______________________________________________________________________

## 依赖关系图

```
main.py (应用入口)
    ├── config.py (get_settings)
    ├── db/core.py (get_engine, init_and_migrate_db)
    │       └── models/models.py (SQLModel models)
    ├── routers/* (API endpoints)
    │       ├── deps.py (SessionDep, get_current_username)
    │       ├── security.py (JWT, password, verify_exists_and_owns)
    │       └── models/models.py
    └── security.py (token creation, password hashing)
```

______________________________________________________________________

## 调试技巧

1. **API 测试**: 启动后端后直接访问 `/api/info` 获取版本
1. **数据库**: `storage/trip.sqlite` 可用 `sqlite3` 直接查看
1. **日志**: `utils/utils.py:silence_http_logging()` 默认抑制 FastAPI HTTP 日志
1. **配置**: `storage/config.env` 运行时配置

______________________________________________________________________

## 研究问题清单

- [ ] 行程分享的 token 机制是如何工作的？
- [ ] TOTP 2FA 的完整验证流程？
- [ ] OIDC 认证的完整流程？
- [ ] 图片上传和处理的完整流程？
- [ ] TripDay 和 TripItem 的嵌套关系如何持久化？
- [ ] 前端如何与后端 API 交互？
- [ ] OSM Provider 如何将 Nominatim 结果映射到 TRIP 分类？
- [ ] Google My Maps KMZ 导入的完整解析流程？
- [ ] 批量导入的并发限流是如何实现的？
