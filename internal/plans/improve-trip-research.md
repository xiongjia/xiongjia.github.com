---
title: Improve TRIP Research
created: 2026-08-17
tags: [trip, research, improve]
---

# Improve TRIP Research

## Goal

改进现有的 TRIP research 笔记（`docs/notes/research/topics/trip/index.md`）：
TRIP 是一个 FastAPI + Angular 的自托管地图追踪/行程规划工具，
核对笔记与上游最新代码的偏差，补全前后端关键机制，增加实操部署/运行说明。

## Tasks

- [ ] **核对上游版本**

  - 检查 TRIP 仓库最新状态（分支、commit）是否落后于笔记记录
  - 更新依据信息，diff 关键变更（API、数据模型、前端结构）

- [ ] **补全/修正后端部分**

  - 核对 FastAPI 路由、认证（verify_exists_and_owns 等）、数据模型
  - 补充：位置数据如何存储、行程规划逻辑、离线使用机制
  - 修正过时代码片段

- [ ] **补全/修正前端部分**

  - Angular 结构、地图集成（Leaflet/MapLibre？）、状态管理
  - 补充关键组件/服务说明

- [ ] **增加实操说明**

  - 本地 clone + 运行（backend/ 与前端）步骤
  - 与自托管部署（Docker?）相关说明，评估是否能借鉴到本项目（如 City Log）

- [ ] **维护索引**

  - 确保 `docs/notes/research/index.md` 中 trip 的描述与实际一致

## Notes

- 现有笔记 14.9K，先 diff 上游再动手
- TRIP 与本项目 City Log（离线打卡 PWA）主题相近，改进后可交叉参考

## References

- [TRIP Topic](../../docs/notes/research/topics/trip/)
- [TRIP 仓库](https://github.com/itskovacs/trip)
