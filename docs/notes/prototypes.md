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
| [go-cli-urfave](#go-cli-urfave)                     | [Utilities](#utilities)           | 🟢 Working      | 2026-08-03 |
| [supabase-storage-client](#supabase-storage-client) | [Object Storage](#object-storage) | 🟢 Working      | 2026-08-04 |
| [r2-client](#r2-client)                             | [Object Storage](#object-storage) | 🟢 Working      | 2026-08-05 |
| [protomaps-map-view](#protomaps-map-view)           | [Maps](#maps)                     | 🟢 Working      | 2026-08-07 |
| [etl-dbt](#etl-dbt)                                 | [ETL](#etl)                       | 🟢 Working      | 2026-08-26 |
| [pg-boss-demo](#pg-boss-demo)                       | [Job Queue](#job-queue)           | 🟢 Working      | 2026-08-30 |
| [tiny-bitcask](#tiny-bitcask)                       | [Database](#database)             | 🟡 Experimental | 2026-09-11 |
| [rust-patterns](#rust-patterns)                     | [Rust](#rust)                     | 🟡 Experimental | 2026-09-25 |
| [tauri-demo](#tauri-demo)                           | [Desktop](#desktop)               | 🟢 Working      | 2026-10-07 |
| [web-harvester](#web-harvester)                     | [Scraping](#scraping)             | 🟢 Working      | 2026-10-25 |

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

## Job Queue

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

## ETL

### etl-dbt

Python 原型：**dbt-core + DuckDB** 的最小调用链演示（无服务器、无容器），
CSV 源数据 → seed → 单个 staging 视图转换。

- 源数据：`seeds/test_data.csv` **10 条固定订单记录**（无随机），`dbt seed` 直接载入
- 唯一转换模型 `stg_test_data`（视图）：过滤 `cancelled`、新增计算列 `line_total`
- 测试两层：schema.yml 通用测试（unique / not_null）+ 两个 singular 测试
  （断言无 cancelled 泄漏、断言 `line_total = qty * unit_price` 重算一致）
- 完整调用链演示：seed → run → test → build → compile，编译产物可审查真实 SQL
- 工程化：`uv run poe fmt`（sqlfmt 格式化 dbt Jinja SQL + mdformat）、`poe fmt-check`
- uv 管理：Python 3.13，dbt-core 1.12.3 / dbt-duckdb 1.11.0 / DuckDB 1.5.5
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/etl-dbt)

## Utilities

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

## Database

> 相关文档：[Bitcask 存储模型](./knowledge/database/kv/bitcask.md)

### tiny-bitcask

Rust 原型：最小可用的 Bitcask 风格 KV 存储（append-only 数据文件 + 内存
keydir，`clap` 命令行）。目标是学 Rust（语法 / 文件操作 / 模块 / 异步 IO）与
Bitcask 数据结构，README 即设计文档。

> 状态：实验性，仍在手工验证中；磁盘格式 / API / 命令行都可能再变。

- 记录格式与论文一致（14 字节头部：CRC32 + 时间戳 + key 长度 + value 长度），
  删除写 tombstone（value size 哨兵），CRC 覆盖头部剩余字段 + key + value
- 子命令：`put` / `get` / `del` / `list` / `files` / `stats` / `merge` / `bench`；
  `--max-file-size` 控制文件 rotate，`--sync` 控制每次写是否 fsync，
  `--verify-reads` 让 `get` 重新读取整条记录并校验 CRC（默认走 keydir 快路径）
- `merge`：只重写 live 记录、丢弃旧版本与 tombstone，写 `*.hint` 加速文件
  （最后一个文件除外，它成为新的 active file）；输出全部写盘后先写 `.merge-ready`
  标记，再把新文件 rename 进目录、最后删旧文件。中断的 merge 由下次 `open` 收尾
  （有标记则把残留文件接入，无标记则丢弃），不会丢最新数据
- 崩溃恢复：数据文件即日志（无需 replay WAL），启动扫描重建 keydir；活动文件
  尾部的半写 / CRC 损坏记录截断丢弃，非最后文件损坏则报 `Corrupt` 错误；头部
  声明的 key/value 长度先与文件剩余字节比对再分配缓冲区
- hint 文件不会被无条件信任：需要按 offset 完整铺满对应数据文件（无空洞）才
  采用，否则回退全量扫描 —— 截断/损坏的 hint 不会静默丢 key
- 异步层：核心引擎保持同步，`Arc<Mutex<Bitcask>>` + `spawn_blocking` 包装；
  `backup_to` 用 `tokio::fs::copy` 备份数据 / hint 文件；`bench` 对比顺序与
  并发读写吞吐
- 42 个测试（单元 + 集成 + `#[tokio::test]`），覆盖 rotate、torn tail、CRC
  损坏、merge 回收与 hint 文件（含截断 hint 回退扫描、中断 merge 的标记恢复）、
  单写者锁、并发无丢键
- 局限（README 有完整说明）：keyspace 必须放进内存、merge 的 rename/prune 之间
  崩溃可能复活合并前已删除的 key（但既不会丢数据也不会读到旧版本）、单写者
  （不做只读并发打开）、无范围扫描 / TTL / batch / 压缩
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/tiny-bitcask)

## Rust

### rust-patterns

Rust 抽象的学习原型（长期维护）：把平时反复遇到的抽象写成能跑的小例子，为什么这么
写就写在代码旁边（用法与各模式的说明见原型 README）。

- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/rust-patterns)

______________________________________________________________________

## Desktop

### tauri-demo

Tauri 2 桌面 Dashboard 原型：Rust 采集本机指标 → IPC → React + shadcn 图表。
目标是跑通链路（`#[tauri::command]` → `invoke()` → 类型化数据 → 图表），
不是做一个完整产品。

- Rust 侧用 `sysinfo` 采集 CPU（全局 + 每核）/ 内存 / 磁盘 / 进程，长驻
  `MetricsState`（复用 `System` handle，CPU 占用取两次刷新的差值）
- 历史用容量 60 的环形缓冲（`VecDeque<HistoryPoint>`），支撑折线图
- 两个命令：`system_snapshot`（采样并追加历史）、`system_history`（返回缓冲）；
  `serde(rename_all = "camelCase")` 让 TS 接口与 Rust 结构体字段一一对应
- 纯函数 helper（`percent` / `push_history` / `top_processes`）不依赖 Tauri 运行时，
  可直接单测
- 前端 React 19 + Tailwind v4 + shadcn/ui（`radix-nova` preset）+ Recharts 3.8：
  4 个 KPI 卡片、CPU/内存折线、每核占用、Top 8 进程条形、磁盘环形 + 明细列表、
  Tabs 切换、深色模式，每 2s 轮询一次
- 浏览器 mock：`pnpm dev` 不启动 Rust 也能跑（badge 显示 `Browser mock`，
  Tauri 内显示 `Tauri / Rust`），方便前端调试与自动化断言
- 验证不靠截图：前端用 **Vitest（jsdom + Testing Library）63 个测试**，直接断言
  渲染后的 DOM（含 Recharts 的真实路径几何：两条折线、每进程一根柱、每挂载点一个
  扇形；`src/test/setup.ts` 补了 jsdom 缺的 `ResizeObserver` / `matchMedia`）；
  Rust 侧 `cargo test` 10 个单测 + `cargo clippy --all-targets -- -D warnings` 无告警
- 工具链彩蛋：脚手架用 Rust CLI（`cargo create-tauri-app`）、TypeScript 7（Go 版，
  `tsc` 只剩类型检查，JS 编译器 API 已移除 → 用 `oxlint` + `oxlint-tsgolint`
  做类型感知 lint，因为 `typescript-eslint` 的 peer 限制不支持 TS 7）
- 打包未做（`tauri build` 的 `.app` 约 4.2 MB），README 记录了
  `recharts 3.x`、APFS 卷重复上报等踩坑
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/tauri-demo)

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

## Scraping

### web-harvester

Node + TypeScript（NestJS 12，pnpm）的浏览器自动化采集原型：一个可热换脚本的
**flow 引擎**（抓取脚本是 `.jsonc` 数据，不是代码）＋ 小红书的登录与关注列表，
对外提供 REST（Swagger 在 `/api/docs`）。

- **Flow 引擎**：一个 flow = 一个 `.jsonc` 文件（类型化 input、步骤数组、output
  映射），zod 校验、自动生成 `flow.schema.json` 给编辑器补全；原语含
  `goto / wait / click / fill / press / text / extract / scroll / screenshot / assertNotBlocked / include / if`，支持候选选择器、`{{input.x}}` 插值、
  `retry`、按 mtime 热加载
- **组合**：`include` 把 `kind: "fragment"` 的 flow 插到当前位置（同页面同变量），
  环与 >5 层嵌套拒绝；`GET /api/v1/flows` 直接给「谁 include 谁」的图
- **异步执行**：`POST /flows/:name/runs` → `202 + runId`，`GET /runs/:id` 查状态、
  `/output` 取 JSON、`/artifacts` 列产物、`/events` 走 SSE、`/cancel` 取消；
  结果落 `data/runs/<id>/`（`run.json` 状态机 + `output.json` + `artifacts/`），
  失败自动留现场截图。标了 `"sync": true` 的短 flow 还可以走
  `POST /flows/:name/run` 一步拿结果，`?artifact=qr` 直接把产物当响应体返回
- **Profile**：一个 profile 一套独立浏览器目录（cookies/localStorage）+ 冻结的
  Camoufox 指纹 preset，`?profile=` 选身份、`/profiles` 列表、
  `PATCH/DELETE` 增删改；默认 profile 沿用原有 `.cache/profile`，登录态不丢
- **浏览器可回收**：context 默认常驻（第二次跑得快），`HARVEST_BROWSER_IDLE_MS`
  设成毫秒数就在空闲那么久后自动关掉（默认 `0` = 不关），
  `POST /api/v1/browser/close` 随时手动关，`GET /api/v1/browser` 看谁开着、空闲多久；
  关闭只释放内存和子进程，cookie 与指纹在 profile 目录里，下次启动即恢复
- **节流写在 flow 里**：flow 可声明 `throttle`（最小间隔 + `scope`），三个 xhs
  flow 共用 `scope: "xhs"`、20 秒间隔 —— 手动连打或脚本突发都会被拉平到同一节奏，
  其他 flow 不受影响
- **引擎可换**：默认 **Camoufox**（Firefox 定制内核，指纹一致），`patchright`
  （驱动本机 Chrome，零下载）作兜底，**CloakBrowser**（源码级 patch 的 Chromium）
  走隐匿路线，三者共用同一个 `BrowserBackend` 接口；`HARVEST_BROWSER` 是切换开关
  （不设 = 每个 profile 用自己的引擎，设了 = 全局覆盖），每个引擎各占一个
  `<browser dir>/<engine>` 子目录，来回切都不丢对面登录态；引擎留在进程内（不做
  独立 engine 进程）
- 小红书扫码登录：也是 flow —— `flows/xhs-login-qr.jsonc` 负责出二维码（宿主把
  `artifacts/qr.png` 当响应体返回）、`flows/xhs-login-check.jsonc` 负责回读只有登录
  后才有的侧栏身份作为 `verified` 证据；会话保存在 profile 的持久浏览器目录里，
  0600 cookie jar 只作可移植副本，`/status` 有 60s 验证缓存
- 关注列表：`flows/xhs-following.jsonc` 点开「关注」面板、滚
  `.xhs-following-scroll`、用 `extract`（含 `{ selector, attr }` 读头像 `src`）抓
  `.xhs-relation-item`；手写的 `/api/v1/xhs/following` 与调试端点已退役（迁移前
  做过 A/B，账号与头像完全一致）
- 排障：`/api/v1/xhs/debug/following` dump 选择器命中数、面板 DOM、候选元素与
  截图；风控页（`安全限制 / 300012`）会返回 503 并说明原因
- 工程：zod 校验配置、ESLint 10 + Prettier + `pnpm check` 门禁、204 个 Vitest
  单测（引擎用 DI token 注入假实现，测试不开浏览器）
- 未实现（roadmap）：推荐流 / 搜索 / 笔记详情、MCP server、CLI、发布、限速与
  `/healthz`
- :simple-github: [Source](https://github.com/xiongjia/xiongjia.github.com/tree/master/prototypes/web-harvester)
