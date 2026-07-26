---
title: Redash 源码阅读指南
tags:
  - research
  - tech
  - redash
categories:
  - dev
---

> **⚠️ 免责声明**: 本文档由 AI 自动生成，仅供参考学习使用。

# Redash 查询缓存与 Dashboard 布局实现原理

## 一、查询结果缓存机制

Redash 的查询结果缓存是一个多层级的系统，涵盖 hash 去重、Redis 分布式锁、PostgreSQL 持久化存储、TTL 过期和定期清理。

### 核心概念

| 概念              | 说明                                      |
| ----------------- | ----------------------------------------- |
| `query_hash`      | 查询文本的 MD5 hash，用于去重和复用       |
| `QueryResult`     | 持久化在 PostgreSQL 中的查询结果记录      |
| `job_lock`        | Redis 中的分布式锁，防止相同查询并发执行  |
| `max_age`         | 允许返回的缓存结果最大年龄（秒）          |
| `JOB_EXPIRY_TIME` | Job 结果在 Redis 中的 TTL（默认 12 小时） |

### 主要组件

| 组件                       | 文件                                                                                                                | 职责                           |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| `gen_query_hash`           | [`redash/utils/__init__.py:54`](docs/research/external/redash/redash/utils/__init__.py#L54)                         | 生成查询文本的 MD5 hash        |
| `QueryResult.get_latest`   | [`redash/models/__init__.py:348`](docs/research/external/redash/redash/models/__init__.py#L348)                     | 按 hash + max_age 查找最新缓存 |
| `QueryResult.store_result` | [`redash/models/__init__.py:369`](docs/research/external/redash/redash/models/__init__.py#L369)                     | 持久化查询结果到 PostgreSQL    |
| `enqueue_query`            | [`redash/tasks/queries/execution.py:32`](docs/research/external/redash/redash/tasks/queries/execution.py#L32)       | 入队任务，含 hash 去重逻辑     |
| `QueryExecutor`            | [`redash/tasks/queries/execution.py:174`](docs/research/external/redash/redash/tasks/queries/execution.py#L174)     | 执行查询并将结果存储           |
| `run_query`                | [`redash/handlers/query_results.py:59`](docs/research/external/redash/redash/handlers/query_results.py#L59)         | API 层缓存命中检查入口         |
| `cleanup_query_results`    | [`redash/tasks/queries/maintenance.py:120`](docs/research/external/redash/redash/tasks/queries/maintenance.py#L120) | 定期清理未使用的查询结果       |

### 整体流程

```
用户发起查询请求 (POST /api/query_results)
    │
    ▼
run_query()  ─── max_age > 0?
    │               │
    │ YES          │ NO (max_age=0)
    ▼               ▼
QueryResult.get_latest()    enqueue_query()
    │               │
    ▼               ▼
找到了且未过期?     生成 query_hash
    │               │
    ├── YES ──►    检查 Redis job_lock
    │               │
    │               ├── 锁定存在且 Job 未完成 ──► 复用已有 Job
    │               │
    │               └── 无锁或已完成 ──► 创建新 Job
    │                       │
    ▼                       ▼
返回缓存结果            Worker 异步执行
                        │
                        ▼
                    QueryExecutor.run()
                        │
                        ▼
                    query_runner.run_query()
                        │
                        ▼
                    QueryResult.store_result()  ──► 存入 PostgreSQL
                        │
                        ▼
                    Query.update_latest_result() ──► 关联 Query → QueryResult
                        │
                        ▼
                    check_alerts_for_query() ──► 触发告警检查
```

### Hash 去重原理

#### 1. 生成查询 Hash

[`redash/utils/__init__.py:54-64`](docs/research/external/redash/redash/utils/__init__.py#L54-L64):

```python
def gen_query_hash(sql):
    """Return hash of the given query after stripping all comments, line breaks
    and multiple spaces.
    """
    sql = COMMENTS_REGEX.sub("", sql)  # 去除 /* ... */ 注释
    sql = "".join(sql.split())  # 去除所有空白字符
    return hashlib.md5(sql.encode("utf-8"), usedforsecurity=False).hexdigest()
```

**要点**：

- 去注释、去空白后取 MD5，确保格式不同但语义相同的查询产生相同 hash
- 大小写敏感：`SELECT 1` 和 `select 1` 会产生不同 hash
- 这也是为什么 Redash 需要 `update_query_hash()` 在保存 Query 时更新 hash

#### 2. Redis 分布式锁防止重复执行

[`redash/tasks/queries/execution.py:32-123`](docs/research/external/redash/redash/tasks/queries/execution.py#L32-L123):

```python
def enqueue_query(query, data_source, user_id, ...):
    query_hash = gen_query_hash(query)
    
    while try_count < 5:
        pipe = redis_connection.pipeline()
        try:
            pipe.watch(_job_lock_id(query_hash, data_source.id))
            job_id = pipe.get(_job_lock_id(query_hash, data_source.id))
            
            if job_id:
                # 已有 job，检查其状态
                job = Job.fetch(job_id)
                status = job.get_status()
                job_complete = status in [JobStatus.FINISHED, JobStatus.FAILED]
                
                if job_complete or job_cancelled:
                    # 已完成或已取消 → 释放锁，允许新 job
                    redis_connection.delete(lock_key)
                else:
                    # 正在执行 → 复用已有 job，不创建新的
                    break
            
            if not job:
                # 无锁或锁已过期 → 创建新 job
                pipe.multi()
                job = queue.enqueue(execute_query, query, data_source.id, ...)
                pipe.set(lock_key, job.id, settings.JOB_EXPIRY_TIME)
                pipe.execute()
            break
            
        except redis.WatchError:
            continue  # 乐观锁冲突，重试
```

**核心机制**：

- Lock key 格式：`query_hash_job:{data_source_id}:{query_hash}`
- 使用 Redis `WATCH` + `MULTI` 实现乐观锁
- 最多重试 5 次处理并发冲突
- 相同 query_hash + data_source 的查询复用同一个 Job

### PostgreSQL 持久化 — 表结构与存储

Redash 使用 PostgreSQL 作为元数据库，所有 Query、QueryResult、Dashboard、Widget 等核心数据都以关系表的形式持久化。

#### 核心表 ER 关系

```
┌──────────────────┐       ┌──────────────────┐
│  data_sources    │       │  organizations   │
│──────────────────│       │──────────────────│
│ id (PK)          │◄──┐   │ id (PK)          │
│ org_id (FK)      │   │   │ name, slug       │
│ name, type       │   │   │ settings (JSONB) │
│ options (enc)    │   │   └────────┬─────────┘
│ queue_name       │   │            │
└────────┬─────────┘   │            │
         │              │            │
         │    ┌─────────┴────────────┴─────────┐
         │    │          query_results          │
         │    │────────────────────────────────│
         │    │ id (PK)                        │
         │    │ org_id (FK → organizations)    │
         │    │ data_source_id (FK)            │◄──── data_source
         │    │ query_hash (VARCHAR 32)        │      └─ INDEXED
         │    │ query (TEXT)                   │
         │    │ data (TEXT / JSON)             │
         │    │ runtime (DOUBLE PRECISION)     │
         │    │ retrieved_at (TIMESTAMP)       │
         │    └────────┬───────────────────────┘
         │             │
         │             │ latest_query_data_id (FK)
         │             ▼
         │    ┌──────────────────┐       ┌──────────────────┐
         │    │     queries      │       │  visualizations  │
         │    │──────────────────│       │──────────────────│
         │    │ id (PK)          │───┐   │ id (PK)          │
         │    │ org_id (FK)      │   │   │ query_id (FK)    │◄──┐
         │    │ data_source_id   │───┼───│ type (VARCHAR)   │   │
         │    │ latest_query_data│   │   │ name, description│   │
         │    │   _id (FK)       │   │   │ options (JSONB)  │   │
         │    │ name, description│   │   └──────────────────┘   │
         │    │ query (TEXT)     │   │                          │
         │    │ query_hash       │   │   ┌──────────────────┐   │
         │    │ schedule (JSONB) │   │   │     widgets      │   │
         │    │ options (JSONB)  │   │   │──────────────────│   │
         │    │ is_draft, is_arch│   │   │ id (PK)          │   │
         │    │ tags (ARRAY)     │   │   │ visualization_id ├───┘
         │    └──────────────────┘   │   │ dashboard_id (FK)│
         │                           │   │ text (TEXT)      │
         │                           │   │ width (INTEGER)  │
         │                           │   │ options (JSONB)  │
         │                           │   └──────────────────┘
         │                           │
         │                           │   ┌──────────────────┐
         │                           │   │    dashboards    │
         │                           │   │──────────────────│
         │                           │   │ id (PK)          │
         │                           │   │ org_id (FK)      │
         │                           │   │ user_id (FK)     │
         │                           │   │ name, slug       │
         │                           │   │ layout (JSONB)   │
         │                           │   │ options (JSONB)  │
         │                           │   │ is_draft, is_arch│
         │                           │   │ version (INT)    │
         │                           └───│ tags (ARRAY)     │
         │                               └──────────────────┘
         │
         ▼
  (其他表: alerts, events, favorites, api_keys, ...)
```

#### 核心表 DDL

##### query_results — 查询结果缓存表

这是缓存机制的核心存储表。每次查询执行完毕后，结果以 JSON 文本形式写入此表：

```sql
CREATE TABLE query_results (
    id              SERIAL PRIMARY KEY,
    org_id          INTEGER REFERENCES organizations(id),
    data_source_id  INTEGER REFERENCES data_sources(id),
    query_hash      VARCHAR(32),            -- MD5 hash，有索引，用于缓存查找
    query           TEXT,                   -- 原始查询文本
    data            TEXT,                   -- JSON 格式的查询结果
    runtime         DOUBLE PRECISION,       -- 执行耗时（秒）
    retrieved_at    TIMESTAMP WITH TIME ZONE -- 结果生成时间
);
CREATE INDEX ix_query_results_query_hash ON query_results (query_hash);
```

**字段说明**：

| 字段             | 类型                 | 说明                                                              |
| ---------------- | -------------------- | ----------------------------------------------------------------- |
| `id`             | `SERIAL`             | 自增主键                                                          |
| `org_id`         | `FK → organizations` | 所属组织                                                          |
| `data_source_id` | `FK → data_sources`  | 数据源                                                            |
| `query_hash`     | `VARCHAR(32)`        | 查询文本的 MD5，**有索引**，是缓存查找的关键                      |
| `query`          | `TEXT`               | 原始 SQL / 查询文本                                               |
| `data`           | `JSON/Text`          | 查询返回的数据，结构为 `{"columns": [...], "rows": [[...], ...]}` |
| `runtime`        | `DOUBLE PRECISION`   | 查询执行耗时（秒）                                                |
| `retrieved_at`   | `TIMESTAMPTZ`        | 结果生成时间，用于判断缓存是否过期                                |

**data 字段的 JSON 结构**：

```json
{
  "columns": [
    {"name": "date",       "friendly_name": "Date",       "type": "datetime"},
    {"name": "revenue",    "friendly_name": "Revenue",    "type": "float"},
    {"name": "users",      "friendly_name": "Users",      "type": "integer"}
  ],
  "rows": [
    {"date": "2024-01-01", "revenue": 12345.67, "users": 1024},
    {"date": "2024-01-02", "revenue": 13456.78, "users": 1156}
  ],
  "columns_types": null   // 可选
}
```

> **注意**：`data` 列在旧版本中为 `VARCHAR/Text` 存储 JSON 字符串，较新版本迁移为 PostgreSQL `JSON`/`JSONB` 类型（参见迁移 `7205816877ec`）。

##### queries — 查询定义表

保存用户创建的查询定义（SQL + 参数 + 调度）：

```sql
CREATE TABLE queries (
    id                    SERIAL PRIMARY KEY,
    version               INTEGER DEFAULT 1,
    org_id                INTEGER REFERENCES organizations(id),
    data_source_id        INTEGER REFERENCES data_sources(id),
    latest_query_data_id  INTEGER REFERENCES query_results(id),  -- 指向最新缓存结果
    name                  VARCHAR(255),
    description           VARCHAR(4096),
    query                 TEXT,                -- 查询文本（含 {{mustache}} 参数）
    query_hash            VARCHAR(32),         -- 查询文本 hash
    api_key               VARCHAR(40),
    user_id               INTEGER REFERENCES users(id),
    last_modified_by_id   INTEGER REFERENCES users(id),
    is_archived           BOOLEAN DEFAULT FALSE,
    is_draft              BOOLEAN DEFAULT TRUE,
    schedule              JSONB,               -- 定时调度配置 {"interval": 3600, "time": null, ...}
    schedule_failures     INTEGER DEFAULT 0,
    options               JSONB DEFAULT '{}',  -- {"parameters": [...], "apply_auto_limit": false}
    tags                  VARCHAR[]            -- PostgreSQL ARRAY 类型
);
```

**关键关联**：

- `latest_query_data_id → query_results.id`：每个 Query 通过此外键指向最新的 `QueryResult`。多个 Query 对象如果 `query_hash` 相同，可以共享同一个 `QueryResult`。
- `query_hash`：在 `before_insert` / `before_update` 时由 `update_query_hash()` 自动计算。

##### dashboards — 仪表盘表

```sql
CREATE TABLE dashboards (
    id                          SERIAL PRIMARY KEY,
    version                     INTEGER,
    org_id                      INTEGER REFERENCES organizations(id),
    slug                        VARCHAR(140),     -- URL 友好名称，有索引
    name                        VARCHAR(100),
    user_id                     INTEGER REFERENCES users(id),
    layout                      JSONB DEFAULT '[]',  -- 旧版布局，已废弃
    dashboard_filters_enabled   BOOLEAN DEFAULT FALSE,
    is_archived                 BOOLEAN DEFAULT FALSE,
    is_draft                    BOOLEAN DEFAULT TRUE,
    tags                        VARCHAR[],
    options                     JSONB DEFAULT '{}'
);
```

##### widgets — 仪表盘组件表

```sql
CREATE TABLE widgets (
    id                SERIAL PRIMARY KEY,
    visualization_id  INTEGER REFERENCES visualizations(id),
    text              TEXT,               -- Textbox 内容
    width             INTEGER,            -- 向后兼容
    options           JSONB DEFAULT '{}', -- 含 position 等
    dashboard_id      INTEGER REFERENCES dashboards(id),  -- 有索引
    created_at        TIMESTAMP,
    updated_at        TIMESTAMP
);
CREATE INDEX ix_widgets_dashboard_id ON widgets (dashboard_id);
```

**`widgets.options` JSONB 结构**：

```json
{
  "position": {
    "col": 0,          // 起始列 (0-indexed)
    "row": 0,          // 起始行
    "sizeX": 6,        // 宽度（占 6 列，即半宽）
    "sizeY": 4,        // 高度（占 4 行，即 200px）
    "autoHeight": false,
    "minSizeX": 2, "maxSizeX": 12,
    "minSizeY": 2, "maxSizeY": 1000
  },
  "isHidden": false,
  "parameterMappings": {
    "param_name": {
      "name": "param_name",
      "type": "dashboard-level",
      "mapTo": "global_param",
      "value": null,
      "title": ""
    }
  },
  "paramOrder": ["param1", "param2"]
}
```

##### visualizations — 可视化定义表

```sql
CREATE TABLE visualizations (
    id          SERIAL PRIMARY KEY,
    type        VARCHAR(100),       -- 'TABLE', 'CHART', 'COUNTER', 'MAP', ...
    query_id    INTEGER REFERENCES queries(id),
    name        VARCHAR(255),
    description VARCHAR(4096),
    options     JSONB               -- 图表配置（x 轴、y 轴、颜色等）
);
```

#### 查询结果写入流程 (SQL 视角)

从用户发起查询到结果持久化的完整链路：

```
1. 用户 POST /api/query_results  {query: "SELECT ...", data_source_id: 1, max_age: 0}

2. run_query() 
   ├── max_age > 0 ?
   │   ├── YES → SELECT * FROM query_results        ←── 缓存查找
   │   │         WHERE query_hash = 'abc123'
   │   │           AND data_source_id = 1
   │   │           AND retrieved_at + INTERVAL '<max_age> seconds' >= NOW()
   │   │         ORDER BY retrieved_at DESC LIMIT 1
   │   │         → 命中则直接返回，不再执行查询
   │   └── NO  → 继续下一步

3. enqueue_query()
   └── Redis SET "query_hash_job:1:abc123" = "<job_id>" EX 43200   ←── 加锁

4. Worker 异步执行
   ├── QueryExecutor.run()
   ├── query_runner.run_query("SELECT ...")  → 连接实际数据源执行
   └── 返回 data = {"columns": [...], "rows": [[...], ...]}

5. QueryResult.store_result()
   └── INSERT INTO query_results             ←── 持久化写入
       (org_id, data_source_id, query_hash, query, data, runtime, retrieved_at)
       VALUES (1, 1, 'abc123', 'SELECT ...', '{"columns":...}', 1.23, NOW())
       RETURNING id  → 得到 query_result_id = 42

6. Query.update_latest_result()
   └── UPDATE queries                        ←── 关联更新
       SET latest_query_data_id = 42
       WHERE query_hash = 'abc123'
         AND data_source_id = 1
         AND is_archived = FALSE

7. Redis DEL "query_hash_job:1:abc123"       ←── 释放锁
```

#### 缓存查找 SQL 详解

[`redash/models/__init__.py:348-366`](docs/research/external/redash/redash/models/__init__.py#L348-L366) — `QueryResult.get_latest()`:

```python
@classmethod
def get_latest(cls, data_source, query, max_age=0):
    query_hash = gen_query_hash(query)

    if max_age == -1 and settings.QUERY_RESULTS_EXPIRED_TTL_ENABLED:
        max_age = settings.QUERY_RESULTS_EXPIRED_TTL  # 默认 86400s

    if max_age == -1:
        # 不限时间：找最新的匹配结果
        query = cls.query.filter(cls.query_hash == query_hash, cls.data_source == data_source)
    else:
        # 限 max_age：结果 retrieved_at 必须在 max_age 秒内
        query = cls.query.filter(
            cls.query_hash == query_hash,
            cls.data_source == data_source,
            db.func.timezone("utc", cls.retrieved_at) + datetime.timedelta(seconds=max_age)
            >= db.func.timezone("utc", db.func.now()),
        )

    return query.order_by(cls.retrieved_at.desc()).first()
```

等价 SQL：

```sql
-- max_age = -1 (不限时间)
SELECT * FROM query_results
WHERE query_hash = 'abc123'
  AND data_source_id = 1
ORDER BY retrieved_at DESC
LIMIT 1;

-- max_age = 300 (5 分钟内)
SELECT * FROM query_results
WHERE query_hash = 'abc123'
  AND data_source_id = 1
  AND retrieved_at + INTERVAL '300 seconds' >= NOW()
ORDER BY retrieved_at DESC
LIMIT 1;
```

#### store_result 存储逻辑

[`redash/models/__init__.py:369-383`](docs/research/external/redash/redash/models/__init__.py#L369-L383):

```python
@classmethod
def store_result(cls, org, data_source, query_hash, query, data, run_time, retrieved_at):
    query_result = cls(
        org_id=org,
        query_hash=query_hash,
        query_text=query,
        runtime=run_time,
        data_source=data_source,
        retrieved_at=retrieved_at,
        data=data,
    )
    db.session.add(query_result)
    logging.info("Inserted query (%s) data; id=%s", query_hash, query_result.id)
    # 注意：此时还未 commit，由调用方 QueryExecutor.run() 统一 commit
    return query_result
```

等价 SQL：

```sql
INSERT INTO query_results
  (org_id, query_hash, query, runtime, data_source_id, retrieved_at, data)
VALUES
  (1, 'abc123', 'SELECT ...', 1.23, 1, '2024-01-01T00:00:00Z', '{"columns":[...],"rows":[[...]]}')
RETURNING id;
```

### max_age 参数说明

| max_age 值    | 行为                                                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `0`           | 始终执行新查询，不使用缓存                                                                                               |
| `-1`          | 返回任意时间的缓存结果；如果 `QUERY_RESULTS_EXPIRED_TTL_ENABLED=true`，则使用 `QUERY_RESULTS_EXPIRED_TTL`（默认 86400s） |
| `>0` (如 300) | 如果 300 秒内有缓存结果则返回缓存，否则执行新查询                                                                        |

### 缓存清理机制

[`redash/tasks/queries/maintenance.py:120-140`](docs/research/external/redash/redash/tasks/queries/maintenance.py#L120-L140):

```python
def cleanup_query_results():
    """
    定期清理未被任何 Query 引用的旧结果。
    每次最多删除 QUERY_RESULTS_CLEANUP_COUNT (默认 100) 条，
    且只删除 QUERY_RESULTS_CLEANUP_MAX_AGE (默认 7 天) 之前的。
    """
    unused_query_results = models.QueryResult.unused(settings.QUERY_RESULTS_CLEANUP_MAX_AGE)
    deleted_count = models.QueryResult.query.filter(
        models.QueryResult.id.in_(
            unused_query_results.limit(settings.QUERY_RESULTS_CLEANUP_COUNT).subquery()
        )
    ).delete(synchronize_session=False)
```

**清理策略**：

- 由 RQ Scheduler 每 5 分钟触发一次
- 通过 `QueryResult.unused()` 找到未被任何 Query 引用的结果
- 每次只删 100 条，避免锁表
- 只清理 7 天前的结果，避免误删仍在浏览器中展示的数据

### Query 与 QueryResult 的关联

```python
# models/__init__.py:773
@classmethod
def update_latest_result(cls, query_result):
    """当新结果产生时，更新所有使用相同 query_hash 的 Query"""
    queries = Query.query.filter(
        Query.query_hash == query_result.query_hash,
        Query.data_source == query_result.data_source,
        Query.is_archived.is_(False),
    )
    for q in queries:
        q.latest_query_data = query_result  # 建立外键关联
        q.skip_updated_at = True
        db.session.add(q)
```

**关键设计**：多个 Query 对象可以共享同一个 `QueryResult`——只要它们使用相同的 query_text 和 data_source，就会产生相同的 `query_hash`，从而复用缓存结果。

______________________________________________________________________

## 二、Dashboard 自定义布局实现

Redash 的 Dashboard 基于 `react-grid-layout` 实现响应式网格布局，支持拖拽调整大小和位置、自适应高度、以及移动端单列布局。

### 核心概念

| 概念                         | 说明                                                                   |
| ---------------------------- | ---------------------------------------------------------------------- |
| `react-grid-layout`          | React 网格布局库，提供拖拽和调整大小能力                               |
| `Responsive + WidthProvider` | 响应式布局 HOC，根据屏幕宽度切换列数                                   |
| `layout` (后端)              | Dashboard 的 JSONB 字段，存储 `[[widget_id, ...], ...]` 格式的旧版布局 |
| `position` (前端)            | Widget.options.position，存储 `{col, row, sizeX, sizeY, ...}`          |
| `AutoHeightController`       | 自适应高度控制器，定时检测内容高度变化                                 |

### 主要组件

| 组件                     | 文件                                                                                                                                                 | 职责                                 |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| `Dashboard` (Model)      | [`redash/models/__init__.py:1116`](docs/research/external/redash/redash/models/__init__.py#L1116)                                                    | Dashboard 数据模型                   |
| `Widget` (Model)         | [`redash/models/__init__.py:1270`](docs/research/external/redash/redash/models/__init__.py#L1270)                                                    | Widget 数据模型，含 width 和 options |
| `DashboardPage`          | [`client/app/pages/dashboards/DashboardPage.jsx`](docs/research/external/redash/client/app/pages/dashboards/DashboardPage.jsx)                       | Dashboard 页面组件                   |
| `DashboardGrid`          | [`client/app/components/dashboards/DashboardGrid.jsx`](docs/research/external/redash/client/app/components/dashboards/DashboardGrid.jsx)             | 网格布局核心组件                     |
| `AutoHeightController`   | [`client/app/components/dashboards/AutoHeightController.js`](docs/research/external/redash/client/app/components/dashboards/AutoHeightController.js) | 自适应高度控制器                     |
| `Widget` (Service)       | [`client/app/services/widget.js`](docs/research/external/redash/client/app/services/widget.js)                                                       | 前端 Widget 数据模型                 |
| `Dashboard` (Service)    | [`client/app/services/dashboard.js`](docs/research/external/redash/client/app/services/dashboard.js)                                                 | 前端 Dashboard 数据模型              |
| `dashboard-grid-options` | [`client/app/config/dashboard-grid-options.js`](docs/research/external/redash/client/app/config/dashboard-grid-options.js)                           | 网格配置常量                         |

### 整体架构

```
┌─────────────────────────────────────────────────┐
│                  DashboardPage                   │
│  ┌───────────────────────────────────────────┐  │
│  │          DashboardHeader                   │  │
│  ├───────────────────────────────────────────┤  │
│  │          Parameters (Dashboard Level)      │  │
│  ├───────────────────────────────────────────┤  │
│  │          Filters                           │  │
│  ├───────────────────────────────────────────┤  │
│  │          DashboardGrid                     │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │  ResponsiveGridLayout               │  │  │
│  │  │  ┌─────────┐ ┌─────────┐ ┌───────┐ │  │  │
│  │  │  │ Widget A │ │ Widget B │ │Widget │ │  │  │
│  │  │  │ (Chart)  │ │ (Table)  │ │ C(Txt)│ │  │  │
│  │  │  └─────────┘ └─────────┘ └───────┘ │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 网格配置

[`client/app/config/dashboard-grid-options.js`](docs/research/external/redash/client/app/config/dashboard-grid-options.js):

```javascript
export default {
  columns: 12,          // 桌面端 12 列网格
  rowHeight: 50,        // 每行高度 50px（含 margin）
  margins: 15,          // Widget 间距 15px
  mobileBreakPoint: 800, // ≤800px 切换为单列
  defaultSizeX: 6,      // 默认占 6 列（半宽）
  defaultSizeY: 3,      // 默认占 3 行（150px）
  minSizeX: 2,
  maxSizeX: 12,
  minSizeY: 2,
  maxSizeY: 1000,
};
```

### 数据模型

#### 后端 (Python/SQLAlchemy)

```python
# Dashboard 模型
class Dashboard(db.Model):
    layout = Column(MutableList.as_mutable(JSONB), default=[])
    # layout 是旧版格式: [[widget_id_1, widget_id_2], [widget_id_3]]
    # 新版中，位置信息存储在 Widget.options.position 中


# Widget 模型
class Widget(db.Model):
    visualization_id = Column(...)  # 关联的 Visualization
    text = Column(db.Text, nullable=True)  # Textbox 内容
    width = Column(db.Integer)  # 向后兼容的宽度字段
    options = Column(MutableDict.as_mutable(JSONB), default={})
    # options.position = {
    #     col: 0,        // 起始列
    #     row: 0,        // 起始行
    #     sizeX: 6,      // 宽度（列数）
    #     sizeY: 3,      // 高度（行数）
    #     autoHeight: false,
    #     minSizeX, maxSizeX, minSizeY, maxSizeY
    # }
```

#### 前端 (JavaScript)

```javascript
// Widget Service - calculatePositionOptions()
// 根据 Visualization 类型决定默认尺寸
function calculatePositionOptions(widget) {
  const config = registeredVisualizations[widget.visualization.type];

  const visualizationOptions = {
    autoHeight: false,
    sizeX: Math.round(dashboardGridOptions.columns / 2),  // 默认半宽
    sizeY: dashboardGridOptions.defaultSizeY,
    minSizeX: dashboardGridOptions.minSizeX,
    maxSizeX: dashboardGridOptions.maxSizeX,
    minSizeY: dashboardGridOptions.minSizeY,
    maxSizeY: dashboardGridOptions.maxSizeY,
  };

  // 从 Visualization 类型配置中覆盖默认值
  if (config) {
    if (config.autoHeight) visualizationOptions.autoHeight = true;
    if (config.minColumns) visualizationOptions.minSizeX = config.minColumns;
    if (config.maxColumns) visualizationOptions.maxSizeX = config.maxColumns;
    if (config.defaultColumns) visualizationOptions.sizeX = config.defaultColumns;
    if (config.defaultRows) visualizationOptions.sizeY = config.defaultRows;
    // ...
  }

  return visualizationOptions;
}
```

### 布局计算流程

#### 1. DashboardGrid.normalizeFrom — Widget → react-grid-layout 格式

```javascript
// [DashboardGrid.jsx:112]
static normalizeFrom(widget) {
  const { id, options: { position: pos } } = widget;
  return {
    i: id.toString(),    // react-grid-layout 要求的唯一 ID
    x: pos.col,          // 起始列
    y: pos.row,          // 起始行
    w: pos.sizeX,        // 宽度（列数）
    h: pos.sizeY,        // 高度（行数）
    minW: pos.minSizeX,
    maxW: pos.maxSizeX,
    minH: pos.minSizeY,
    maxH: pos.maxSizeY,
  };
}
```

#### 2. 新 Widget 自动计算位置

[`client/app/services/dashboard.js:83-127`](docs/research/external/redash/client/app/services/dashboard.js#L83-L127):

```javascript
function calculateNewWidgetPosition(existingWidgets, newWidget) {
  // 1. 构建每列的"底部线"——该列被 Widget 占用的最深行号
  const bottomLine = existingWidgets
    .map(w => ({
      left: w.options.position.col,
      right: w.options.position.col + w.options.position.sizeX,
      bottom: w.options.position.row + w.options.position.sizeY,
    }))
    .reduce((result, item) => {
      for (let i = item.left; i < item.right; i++) {
        result[i] = Math.max(result[i], item.bottom);
      }
      return result;
    }, new Array(12).fill(0));  // 12 列全部初始化为 0

  // 2. 滑动窗口扫描，找到需要的最浅位置
  return _.range(0, 12 - newWidgetWidth + 1)
    .map(col => ({
      col,
      row: Math.max(...bottomLine.slice(col, col + newWidgetWidth)),
    }))
    .sortBy("row")
    .first()  // 返回 row 最小的位置
    .value();
}
```

**算法说明**：

- 维护一个长度为 12 的数组 `bottomLine`，表示每一列已有 Widget 的最深位置
- 对新 Widget，遍历所有可能的起始列（`0` ~ `12-width`）
- 对每个候选列，取该列范围内所有列的 `bottomLine` 最大值作为起始行
- 选择起始行最浅（row 最小）的位置，使 Widget 尽可能靠上

#### 3. DashboardGrid 布局变更处理

```javascript
// [DashboardGrid.jsx:166]
onLayoutChange = (_, layouts) => {
  // 只保存多列模式的布局（单列模式不持久化）
  if (this.mode === SINGLE) return;

  // 将 react-grid-layout 格式转回 Widget position 格式
  const normalized = chain(layouts[MULTI])
    .keyBy("i")
    .mapValues(this.normalizeTo)
    .value();

  this.props.onLayoutChange(normalized);
};

normalizeTo = layout => ({
  col: layout.x,
  row: layout.y,
  sizeX: layout.w,
  sizeY: layout.h,
  autoHeight: this.autoHeightCtrl.exists(layout.i),
});
```

### 自适应高度 (AutoHeight)

某些可视化组件（如 Table）的内容高度可能动态变化。Redash 实现了 `AutoHeightController` 来自动调整 Widget 的行高。

[`client/app/components/dashboards/AutoHeightController.js`](docs/research/external/redash/client/app/components/dashboards/AutoHeightController.js):

```javascript
export default class AutoHeightController {
  // 每 200ms 检查一次内容高度变化
  checkHeightChanges = () => {
    Object.keys(this.widgets)
      .filter(this.exists)
      .forEach(id => {
        const [getHeight, prevHeight] = this.widgets[id];
        const height = getHeight();  // 测量 DOM 实际高度
        if (height && height !== prevHeight) {
          this.widgets[id][1] = height;  // 更新缓存高度
          this.onHeightChange(id, height);  // 通知 DashboardGrid 更新布局
        }
      });
  };

  // 注册自适应高度 Widget
  add = id => {
    this.widgets[id] = [
      function getHeight() {
        // 测量 widget-header + visualization + footer 的总高度
        const els = widgetEl.querySelectorAll(
          ".widget-header, .visualization-renderer, .scrollbox .alert, " +
          ".spinner-container, .tile__bottom-control"
        );
        return reduce(els, (acc, el) => 
          acc + (el ? el.getBoundingClientRect().height : 0), 0);
      },
    ];
  };
}
```

**工作流程**：

1. 当 `widget.options.position.autoHeight = true` 时启用
1. 每 200ms 轮询实际 DOM 高度
1. 高度变化时通过 `onWidgetHeightUpdated` 回调更新 `react-grid-layout` 的 `layouts` state
1. 用户手动调整高度后，自动高度功能对该 Widget 禁用

### 响应式布局

```javascript
// 双断点设计
const SINGLE = "single-column";  // ≤800px
const MULTI = "multi-column";    // >800px

<ResponsiveGridLayout
  cols={{ [MULTI]: 12, [SINGLE]: 1 }}       // 多列=12列，单列=1列
  breakpoints={{ [MULTI]: 800, [SINGLE]: 0 }} // 800px 断点
  isDraggable={isEditing}                     // 仅编辑模式可拖拽
  isResizable={isEditing}                     // 仅编辑模式可调整大小
  ...
>
```

### Dashboard 保存流程

```
用户调整布局
    │
    ▼
onLayoutChange(layouts)
    │
    ▼
normalizeTo() — 转换为 Widget position 格式
    │
    ▼
saveDashboardLayout()
    │
    ▼
遍历所有 widgets，调用 widget.save("options", { position })
    │
    ▼
POST /api/widgets/{id}  ──► WidgetResource.post()
    │                         更新 widget.options (含 position)
    ▼
updateDashboard({ version })
    │
    ▼
POST /api/dashboards/{id} ──► DashboardResource.post()
    │                         更新 version（乐观锁）
    ▼
完成
```

注意：布局位置保存在每个 Widget 的 `options.position` 中，而非 Dashboard 的 `layout` 字段（后者是旧版格式，已废弃）。Dashboard 的 `version` 字段用于乐观锁，防止并发修改冲突。

### Widget 类型

| 类型            | 判断条件                                     | 前端组件              |
| --------------- | -------------------------------------------- | --------------------- |
| `VISUALIZATION` | `widget.visualization` 存在                  | `VisualizationWidget` |
| `TEXTBOX`       | `widget.visualization` 不存在且非 restricted | `TextboxWidget`       |
| `RESTRICTED`    | `widget.restricted === true`                 | `RestrictedWidget`    |

### 参数映射 (Parameter Mapping)

Dashboard 级别的参数系统允许将 Widget 内查询的参数提升到 Dashboard 级别：

```javascript
// 三种映射类型
ParameterMappingType = {
  DashboardLevel: "dashboard-level",  // 提升到 Dashboard 全局参数
  WidgetLevel: "widget-level",        // 保持 Widget 本地参数
  StaticValue: "static-value",        // 静态值（不显示参数输入）
};
```

[`client/app/services/dashboard.js:190-233`](docs/research/external/redash/client/app/services/dashboard.js#L190-L233) — `Dashboard.prototype.getParametersDefs()` 收集所有标记为 `DashboardLevel` 的参数，合并同名参数，生成全局参数列表。

______________________________________________________________________

## 核心文件索引

### 后端 (Python)

| 文件                                                                                                       | 说明                                                     |
| ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| [`redash/utils/__init__.py`](docs/research/external/redash/redash/utils/__init__.py)                       | `gen_query_hash` — 查询 hash 生成                        |
| [`redash/models/__init__.py`](docs/research/external/redash/redash/models/__init__.py)                     | `QueryResult`, `Query`, `Dashboard`, `Widget` 等核心模型 |
| [`redash/handlers/query_results.py`](docs/research/external/redash/redash/handlers/query_results.py)       | API 层缓存命中与查询执行入口                             |
| [`redash/handlers/dashboards.py`](docs/research/external/redash/redash/handlers/dashboards.py)             | Dashboard CRUD API                                       |
| [`redash/handlers/widgets.py`](docs/research/external/redash/redash/handlers/widgets.py)                   | Widget CRUD API                                          |
| [`redash/tasks/queries/execution.py`](docs/research/external/redash/redash/tasks/queries/execution.py)     | 查询执行、job lock、结果存储                             |
| [`redash/tasks/queries/maintenance.py`](docs/research/external/redash/redash/tasks/queries/maintenance.py) | 缓存清理、定时查询刷新                                   |
| [`redash/serializers/__init__.py`](docs/research/external/redash/redash/serializers/__init__.py)           | `serialize_dashboard` — Dashboard 序列化                 |
| [`redash/settings/__init__.py`](docs/research/external/redash/redash/settings/__init__.py)                 | 缓存和 Job 相关配置项                                    |
| [`redash/__init__.py`](docs/research/external/redash/redash/__init__.py)                                   | `redis_connection` — Redis 连接初始化                    |

### 前端 (JavaScript/React)

| 文件                                                                                                                                                 | 说明                                     |
| ---------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| [`client/app/config/dashboard-grid-options.js`](docs/research/external/redash/client/app/config/dashboard-grid-options.js)                           | 网格配置（列数、行高、断点等）           |
| [`client/app/components/dashboards/DashboardGrid.jsx`](docs/research/external/redash/client/app/components/dashboards/DashboardGrid.jsx)             | 响应式网格布局核心                       |
| [`client/app/components/dashboards/AutoHeightController.js`](docs/research/external/redash/client/app/components/dashboards/AutoHeightController.js) | 自适应高度控制器                         |
| [`client/app/services/dashboard.js`](docs/research/external/redash/client/app/services/dashboard.js)                                                 | Dashboard 前端模型（布局计算、参数收集） |
| [`client/app/services/widget.js`](docs/research/external/redash/client/app/services/widget.js)                                                       | Widget 前端模型（位置计算、参数映射）    |
| [`client/app/pages/dashboards/DashboardPage.jsx`](docs/research/external/redash/client/app/pages/dashboards/DashboardPage.jsx)                       | Dashboard 页面入口                       |
| [`client/app/pages/dashboards/hooks/useDashboard.js`](docs/research/external/redash/client/app/pages/dashboards/hooks/useDashboard.js)               | Dashboard 状态管理 Hook                  |

______________________________________________________________________

## 总结

### 查询缓存

1. **Hash 去重** — `gen_query_hash` 去除注释和空白后取 MD5，确保相同语义的查询复用缓存
1. **Redis 分布式锁** — `query_hash_job:{ds_id}:{hash}` 格式的锁，防止相同查询并发执行
1. **max_age 分级控制** — `0`=强制执行，`-1`=任意缓存，`>0`=TTL 限制
1. **PostgreSQL 持久化** — `QueryResult` 模型存储完整查询结果，`data` 字段为 JSON
1. **定期清理** — 每 5 分钟清理超过 7 天未被引用的结果，每次限 100 条

### Dashboard 布局

1. **react-grid-layout** — 基于此开源库实现拖拽、调整大小和响应式布局
1. **12 列网格系统** — 桌面端 12 列，≤800px 自动切换单列
1. **位置计算算法** — 新 Widget 通过"底部线"扫描找到最靠上的空闲位置
1. **自适应高度** — `AutoHeightController` 每 200ms 检测 DOM 高度变化并自动调整网格
1. **Widget 级位置存储** — 位置信息存储在 `Widget.options.position` 中，与 Dashboard 解耦
1. **乐观锁版本控制** — Dashboard 的 `version` 字段防止并发编辑冲突
