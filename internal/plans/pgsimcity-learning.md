---
title: PGSimCity 学习计划 — PostgreSQL 内部机制 3D 可视化
created: 2026-08-01
tags: [postgresql, database, learning, research, visualization]
---

# PGSimCity 学习计划 — PostgreSQL 内部机制 3D 可视化

## Goal

通过 **PGSimCity**（https://nikolays.github.io/PGSimCity/）学习 PostgreSQL
数据库引擎的内部机制。PGSimCity 把 PG 集群映射为一座可探索的 3D 虚拟城市：
每个城区对应一组内部组件，颜色即语义（WAL 琥珀色、脏页红色、vacuum 紫色、
checkpoint 粉色、复制橙色、存储绿色、索引青色、锁红色），并实时展示
TPS、缓存命中率、WAL 流量等关键指标。

学习目标：

- 建立 PG 内存/磁盘/进程模型的空间心智地图：shared_buffers、WAL、
  检查点、autovacuum、standby 复制、存储（8 KiB 页 / B-tree / TOAST / FSM）
- 通过预设场景直观理解"为什么"：检查点风暴的延迟尖刺、缓存激冷时
  clock sweep 竞争、长事务阻塞 xmin horizon 导致表膨胀、
  `synchronous_commit=off` 的取舍、standby replay 各 LSN 拉开
- 对照官方文档验证模拟模型的准确性，能指出模型的简化之处
- （进阶）阅读源码理解模拟如何构建，可选本地运行

阅读笔记（中文）发布到 `docs/notes/research/topics/pgsimcity/`。

## Tasks

- [ ] **上手：导览 + 基本操作**

  - 按 `T` 走完 14 章节引导导览（从 client 连接一路到 planning、caching、
    WAL、checkpoints、vacuum、replication）
  - 掌握视角/快捷键：`F` 飞行 / `G` 步行、`?` 键位图与颜色图例、
    `,` `.` 调速、`K`/`P` 暂停、`1`–`8` 跳转城区、`Enter` 运行语句
  - 记录城市地图：Client sky / Postmaster / Backend row / Buffer pool /
    Storage / WAL district / Maintenance yard / Standbys / Continuity /
    Query lab 各自代表什么
  - 发布阅读笔记到 `docs/notes/research/topics/pgsimcity/index.md`

- [ ] **深入城区：内存与进程模型**

  - Buffer pool（`shared_buffers` 1024 帧采样、`wal_buffers`、ProcArray、
    lock table、CLOG、buffer mapping table）；观察 clock sweep 换页
  - Backend row：16 个 backend，灯光状态即进程状态（含 `idle in transaction`）
  - Postmaster 与 fork 机制、锁与阻塞可视化
  - 对照 Postgres 文档写笔记，标注模型简化之处

- [ ] **深入城区：WAL / 检查点 / 维护 / 复制**

  - WAL district：walwriter → `pg_wal` 段 → archiver → walsender
  - Maintenance yard：checkpointer（fsync 阶段）、background writer、
    autovacuum launcher + workers
  - Standbys：walreceiver、startup 进程 replay、stream lag；
    Continuity：WAL archive、base backup、PITR、delayed replay
  - Storage：heap 文件按 8 KiB 页、B-tree 真树、TOAST、FSM、visibility map、
    OS page cache
  - 发布阅读笔记（可分多篇）

- [ ] **跑预设场景，观察现象与指标**

  - **Checkpoint storm**：checkpointer 飞轮、fsync 抖动、checkpoint 后
    full-page writes 涌入 WAL
  - **Cache thrash / 缓存激冷**：`shared_buffers` 降到 16 MiB，clock sweep
    竞争，backend 自己写脏 victim
  - **Long-running transaction**：xmin horizon 下沉变红、autovacuum 报告
    0 可清理行、`sessions` 表持续膨胀；释放事务后恢复
  - **`synchronous_commit=off`**：backend 不再等在 `commit_wait`，体会代价
  - **Slow replay**：`sent_lsn / write_lsn / flush_lsn / replay_lsn` 拉开
  - 用控制面板自定义事务频率、读写比例等参数，观察 TPS / 缓存命中率 /
    WAL 流量变化；`Enter` 追踪单条语句（如 Non-HOT UPDATE）完整路径

- [ ] **（进阶）本地运行与源码阅读**

  - `npm install && npm run dev`（Node 20+，WebGL2），`npm test` / `npm run typecheck`
  - 读 `src/` 结构：`core`（事件总线/registry）、`sim`（PG 模拟）、
    `world`（城市几何，每城区一个模块）、`engine`（渲染/相机）、
    `ui`、`observability`（诊断界面）；`machine/` 为 psql 工作台
  - 理解三条设计规则：`world/layout.ts` 为地理唯一事实源、sim 不依赖
    three.js、渲染与模拟通过 `SimState` 解耦
  - 了解 PGlite 可选模式：真实 PostgreSQL（WASM）提供解析/计划/统计，
    视觉模型提供隐藏内部

- [ ] **总结与索引**

  - 汇总：PG 关键机制（缓冲池替换、WAL 刷写与 checkpoint 触发点
    `max_wal_size / (1 + checkpoint_completion_target)`、xmin 与膨胀、
    autovacuum、复制协议）的因果链笔记
  - 更新 `docs/notes/research/index.md` 索引

## Notes

- 作者：Nikolay Samokhvalov（NikolayS），Postgres 领域专家（Postgres.AI 创始人）
- 授权：Apache-2.0；TypeScript + three.js r185 + Vite；Plausible 匿名统计
- **重要**：3D 城市是 PostgreSQL 的**模型**（model）而非模拟器（emulator），
  未运行真实 PG 源码，数值经缩放以便观察；已进行 3 轮专家回审 + 独立审计，
  但项目仍为 0.x 早期原型，可能有错误（欢迎提 issue / PR）
- PGlite 模式（Query flow / Machine）需读者显式同意后才会加载真实 PG（WASM）
- 路线图与已知问题见 `ROADMAP.md`

## References

- [Collection: Database → PostgreSQL](../../docs/notes/collection/database.md)
- [PGSimCity 官网](https://nikolays.github.io/PGSimCity/)
- [PGSimCity GitHub](https://github.com/NikolayS/PGSimCity)
- [ROADMAP.md](https://github.com/NikolayS/PGSimCity/blob/main/ROADMAP.md)
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/current/)
- [Research 索引](../../docs/notes/research/index.md)
