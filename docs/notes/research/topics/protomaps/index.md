---
hide:
  - navigation
title: Protomaps 自建底图研究
tags:
  - research
  - tech
  - protomaps
  - pmtiles
  - maplibre
categories:
  - dev
---

# :material-map: Protomaps

开源地图系统研究 —— PMTiles 单文件瓦片格式、工具链、上海地区底图自建项目与 MapLibre 集成。

- 官方文档: [https://docs.protomaps.com/](https://docs.protomaps.com/)
- GitHub (protomaps/go-pmtiles): [https://github.com/protomaps/go-pmtiles](https://github.com/protomaps/go-pmtiles)
- GitHub (basemaps/planetiler): [https://github.com/protomaps/basemaps](https://github.com/protomaps/basemaps)
- 底图下载与预览: [https://maps.protomaps.com/](https://maps.protomaps.com/)
- 在线查看器: [https://pmtiles.io/](https://pmtiles.io/)

## Sub Topics

| 阅读顺序 | 主题                                   | 描述                                                                                             |
| -------- | -------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 1        | [PMTiles 格式与工具链](./pmtiles.md)   | 格式原理（HTTP Range Requests、文件结构、去重）与工具链（pmtiles CLI / Tippecanoe / Planetiler） |
| 2        | [上海地区底图项目](./shanghai-map.md)  | 动手实践 —— 从全球底图远程裁剪上海、本地验证、部署                                               |
| 3        | [自制 PMTiles 地图](./make-own-map.md) | 最简单例子：GeoJSON → Tippecanoe → .pmtiles → MapLibre 渲染                                      |
| 4        | [MapLibre 集成](./maplibre.md)         | pmtiles 协议注册、@protomaps/basemaps 完整样式、中文标签                                         |

## 推荐阅读顺序

1. **理解 PMTiles 格式与工具链** → [PMTiles 格式与工具链](./pmtiles.md)：格式原理（单文件 + Range 读取）、pmtiles CLI / Tippecanoe / Planetiler 安装
1. **动手实践上海底图** → [上海地区底图项目](./shanghai-map.md)：找到构建 → extract 裁剪 → 预览（pmtiles.io）→ 验证 → 本地查看（test-map.html）→ 部署（R2 / S3）
1. **自制 PMTiles 地图** → [自制 PMTiles 地图](./make-own-map.md)：自己的 GeoJSON → Tippecanoe → .pmtiles → MapLibre 渲染（进阶）

> MapLibre 深入集成（React 组件、样式切换、性能优化）另见 [MapLibre 集成](./maplibre.md)。

## 相关笔记

- [Collection Maps](../../../collection/maps.md)：地图相关资源收藏
