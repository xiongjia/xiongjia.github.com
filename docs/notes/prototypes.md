---
icon: material/flask-outline
hide:
  - tags
  - toc
---

# :material-flask-outline: Prototypes

实验性 mini-project 集散地：快速验证的想法就地保存在仓库根目录
`prototypes/<name>/`，随仓库一起提交，不影响主站的构建、格式化与 lint 流程。
列表事实来源为仓库内 `prototypes/README.md`，本页保持同步；点击链接在新标签页
打开 GitHub 目录。

## Overview

| Prototype                                           | Category                          | Status          | Created    |
| --------------------------------------------------- | --------------------------------- | --------------- | ---------- |
| [ali-oss-client](#ali-oss-client)                   | [Object Storage](#object-storage) | 🟢 Working      | 2026-08-01 |
| [prototype-example](#prototype-example)             | [Others](#others)                 | 🟡 Experimental | 2026-08-01 |
| [go-cli-urfave](#go-cli-urfave)                     | [Others](#others)                 | 🟢 Working      | 2026-08-03 |
| [supabase-storage-client](#supabase-storage-client) | [Object Storage](#object-storage) | 🟢 Working      | 2026-08-04 |
| [r2-client](#r2-client)                             | [Object Storage](#object-storage) | 🟢 Working      | 2026-08-05 |
| [protomaps-map-view](#protomaps-map-view)           | [Maps](#maps)                     | 🟢 Working      | 2026-08-07 |
| [etl-dbt](#etl-dbt)                                 | [Others](#others)                 | 🟡 Experimental | 2026-08-26 |
| [pg-boss-demo](#pg-boss-demo)                       | [Others](#others)                 | 🟢 Working      | 2026-08-30 |

状态：🟡 Experimental（实验性，随时变化）· 🟢 Working（已验证可用）· ⏸️ Shelved（搁置）· ✅ Done（完成）· 🗑️ Abandoned（废弃）

______________________________________________________________________

## Object Storage

> 相关文档：[对象存储基本用法](./knowledge/infrastructure/cloud/object-storage/basic-usage.md) ·
> [挂载 Bucket（FUSE Mount）](./knowledge/infrastructure/cloud/object-storage/mount-bucket.md) ·
> [供应商对比](./knowledge/infrastructure/cloud/object-storage/vendors-comparison.md) ·
> [签名 URL（Signed URL）](./knowledge/infrastructure/cloud/object-storage/signed-url.md)

### ali-oss-client

TypeScript 原型，用官方 `ali-oss` SDK（pnpm 管理）演示阿里云 OSS 基本用法。

- 环境变量配置（密钥不入代码）
- 列 bucket / 对象
- 上传、下载
- 生成签名 URL（GET 下载 / PUT 上传）
- 删除对象（demo 对象自动清理）
- README 含基本的阿里云 OSS 配置步骤（RAM 用户 + AccessKey、建 bucket、region/endpoint、`.env.dev.local`）
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/ali-oss-client)

### supabase-storage-client

TypeScript 原型，用官方 `@supabase/supabase-js` SDK（pnpm 管理）在**本地**测试 Supabase Storage 基本用法。

- 自带 `supabase/` 项目配置（`supabase init`，storage 默认开启），实现零配置本地运行
- anon key 未配置时自动从 `supabase status -o env` 读取
- 列 bucket、建私有 bucket
- 列对象、上传（upsert）、下载
- 签名 URL（GET 下载 / PUT 上传）、公开 URL
- 删除对象（demo 对象自动清理；bucket 仅当本次运行创建时才删除，已有 bucket 保留）
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/supabase-storage-client)

### r2-client

TypeScript 原型，用 S3 兼容 AWS SDK v3（`@aws-sdk/client-s3` + `@aws-sdk/s3-request-presigner`，pnpm 管理）演示 Cloudflare R2 基本用法。

- 环境变量配置（密钥不入代码）
- 列 bucket、建 bucket（私有，缺失时自动创建）、列对象
- 上传、下载
- 预签名 URL（GET 下载 / PUT 上传）
- 删除对象（demo 对象自动清理；bucket 仅当本次运行创建时才删除）
- README 含测试环境准备（Cloudflare 账号 + 付费方式、R2 API Token、`.env.dev.local`）
- 本地 MinIO（S3 兼容，Docker）测试：`minio:start` / `minio:stop` / `minio:clean-volumes` / `minio:clean-images`，无需 Cloudflare 账号即可跑通；Console 管理界面 http://127.0.0.1:9001
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/r2-client)

______________________________________________________________________

## Others

### go-cli-urfave

Go CLI 原型，用 `urfave/cli` **v3** 框架（官方文档 <https://cli.urfave.org/>）写的命令行程序，已从 v2 迁移至 v3。

- 根命令 `greet`：全局 `--name` / `-n` 参数（默认 `World`）与根 Action
- 子命令：`hello` / `bye`（`bye` 带别名 `b`；`hello` 不加 `h` 别名以避免与内建 `help` 冲突）
- 嵌套命令：`team add <name> --role <role>` / `team remove <name>`，演示二级命令树、局部参数与位置参数（缺参、多余参数、未知命令或空 `--name` 时报错并退出码 2）
- `Justfile`：`just build` / `run` / `fmt` / `vet` / `test` / `clean`
- VS Code 调试：自带 `.vscode/launch.json`（Go/Delve），README 含调试说明
- 原为研究 [Lux](https://github.com/iawia002/lux) 时在 `research/experiments/` 下的实验代码，已迁移至此
- `go.sum` 纳入版本控制，保证依赖可复现构建
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/go-cli-urfave)

### prototype-example

最小 Rust hello-world **示例**，用于验证原型机制的完整流程（不是实际功能原型）。

- 证明非 Python 工具链项目可以干净地放在 `prototypes/` 下
- 不影响 MkDocs 构建、ruff / mdformat 格式化与 lint
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/prototype-example)

### etl-dbt

Python 原型：**dbt-core + DuckDB** 的本地 ETL 最小链路（无服务器、无容器），
模拟电商原始数据 → staging 清洗 → marts（订单事实 / 客户维度 / 商品维度 / 每日汇总）。

- 源库/目标库分离：`data/raw.duckdb` 经 dbt `attach` 挂载为 `raw` catalog，
  转换结果写入 `data/analytics.duckdb`
- 增量演示：`daily_sales` 为 incremental 模型（`delete+insert` + `is_incremental()`），
  模拟数据用 `--append-days` 追加新日期后只增量重建（30→32 行实测）
- 确定性 mock：固定 seed（默认 42）；订单/明细 id 在追加时自动续号
- uv 管理：Python 3.13，dbt-core 1.12.3 / dbt-duckdb 1.11.0 / DuckDB 1.5.5
- 相关文档：[ETL 研究](./research/topics/etl/index.md)
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/etl-dbt)

### pg-boss-demo

NestJS 12 + **pg-boss 12** 的 Job Queue 原型（pnpm 管理）：pg-boss 封装为
NestJS Service（DI / Config / Logger，配置从 `@nestjs/config` 读入），REST API
布置任务、查询状态与结果，演示队列执行、并行控制、重试、状态/结果查询等日常用法。

- 三个演示队列（handler 注册表驱动，1 类型 = 1 队列）：`echo`（立即完成并
  存结果）/ `flaky`（随机失败演示重试，`retryLimit`/`retryBackoff`）/ `slow`
  （sleep 演示并发，`localConcurrency` 控制每队列并行数）
- REST API：`POST /jobs`、`GET /jobs?queue=&state=`、`GET /jobs/:id`、
  `POST /jobs/:id/cancel|retry`、`GET /queues`、`GET /health`；
  Swagger UI `/api/docs`
- handler 为 `@Injectable()` 类，经 DI 容器解析（`ModuleRef.get`），构造函数可
  注入其它 service（演示 `NotificationService`）
- 单测（NestJS `Test.createTestingModule` + `useValue` mock，无 DB）+ e2e
  （真实 Postgres，随机端口，跑完只删除自己创建的任务，实测 0 残留）
- Postgres 18 用 docker compose 启动（`pnpm db:start`，schema 由 pg-boss 自动迁移）；
  `@pg-boss/dashboard` 调试面板（`pnpm dashboard`，http://localhost:3001）
- 状态 Working：端到端已验证（布置三类任务、状态流转、重试、结果查询）
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/pg-boss-demo)

______________________________________________________________________

## Maps

> 相关文档：[Protomaps 自建底图研究](./research/topics/protomaps/index.md)

### protomaps-map-view

React + Vite + TypeScript 原型：在本地 Protomaps 底图上的**通用地图组件**
（MapLibre GL JS + pmtiles 协议 + @protomaps/basemaps 完整样式，pnpm 管理）。

- 本地瓦片：gitignored `.cache/pmtiles/`（`VITE_PMTILES_DIR/FILE` 配置），vite
  内联插件在 dev/preview 同源挂载（HTTP Range 字节读取，无 CORS、无额外服务）
- 通用 `MapView`：中心/缩放、中心 HUD、导航控件、marker（emoji 或圆点 +
  标签 + 弹窗）、轨迹线图层、事件 props（onClick/onMove/onZoom/onIdle）、
  运行时底图切换（多 pmtiles，换 URL 重建地图、换坐标移动相机）
- 架构拆分：`src/lib/map/`（MapController + basemap + layers + hooks，框架无关）
- glyphs 本地化：`.cache/glyphs/` + `scripts/warm-glyphs.ts` 预热（支持
  protomaps / maplibre 双源，后者含 CJK 真字形）
- 可嵌入 widget：`createMapWidget()` 纯 HTML 直接可用（`pnpm build:widget`，
  pmtiles/glyphs 作为参数），`examples/embed.html` 示例；分发不走 npm
  （直接 copy 产物，或 js/css + 瓦片 + 字体一起发 S3）
- 已知限制：官方字体无 CJK（`pnpm warm:glyphs --source=maplibre` 可解）；
  maplibre 固定 v5（v6 与 pmtiles 协议不兼容，见 README Known issue）
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/protomaps-map-view)
