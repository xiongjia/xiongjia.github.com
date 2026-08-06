---
hide:
  - navigation
title: 上海地区底图项目
tags:
  - research
  - tech
  - protomaps
  - pmtiles
  - shanghai
categories:
  - dev
---

# :material-map-marker-radius: 上海地区底图项目

> 动手实践：从 Protomaps 全球底图**远程裁剪**上海地区，不需要下载 128GB 全量文件。
> 本文是 Protomaps 研究的核心项目。

## 项目目标

- 用 `pmtiles extract` 从远程全球底图裁剪上海地区 → `shanghai.pmtiles`
- 本地验证：`pmtiles show` + 浏览器 MapLibre 渲染
- 最终部署：R2 / S3 静态托管

## 1. 安装 pmtiles CLI

安装方式见 [环境准备：pmtiles CLI](./pmtiles.md#21-pmtiles-cli)

## 2. 找到最新的全球底图并裁剪

> **本步目的：** 确定最新构建号（`https://build.protomaps.com/YYYYMMDD.pmtiles`），
> 然后用 `pmtiles extract` 远程裁剪出上海区域——全程不下载 128GB 全量文件。

Protomaps 每日构建的全球底图地址格式：

```
https://build.protomaps.com/YYYYMMDD.pmtiles
```

两种方式找最新构建日期（官方指南推荐网页方式）：

**方式 1：网页查看 [maps.protomaps.com/builds/](https://maps.protomaps.com/builds/)**

浏览器打开即可看到每日构建列表，取最新日期的构建号（如 `20260805`）。

**方式 2：API 查询**

```bash
# 取最新一条构建信息
curl -sL https://build-metadata.protomaps.dev/builds.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
latest = data[-1]
print(f'最新构建: {latest[\"key\"]}')
print(f'版本:     {latest.get(\"version\", \"N/A\")}')
print(f'日期:     {latest.get(\"uploaded\", \"N/A\")}')
print(f'大小:     {latest[\"size\"] / 1024**3:.1f} GB')
"

# 或直接取最新构建文件名
curl -sL https://build-metadata.protomaps.dev/builds.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data[-1]['key'])
"
```

确定构建号后，可先用 `pmtiles show` 远程验证该构建的元数据（OSM 数据截止日期等）：

```bash
pmtiles show https://build.protomaps.com/20260805.pmtiles
# planetiler:osm:osmosisreplicationtime: 2026-08-05T05:00:00Z  ← OSM 数据截止日期
```

> ⚠️ 以下命令中的 `20260805` 均为**示例构建日期**，执行前请替换为第二步查到的实际日期。

> **注意：全球底图约 128GB，不要下载到本地**，直接使用远程 URL 裁剪。
> 参考官方指南：[Getting Started](https://docs.protomaps.com/guide/getting-started)

`pmtiles extract` 支持直接从远程 URL 读取并裁剪，无需下载完整文件：

```bash
# bbox 格式：minLng,minLat,maxLng,maxLat
# 上海市区范围约 120.8,30.6,122.2,31.9（含崇明岛，见下方说明）

pmtiles extract \
  https://build.protomaps.com/20260805.pmtiles \
  shanghai.pmtiles \
  --bbox=120.8,30.6,122.2,31.9
```

**执行过程说明：**

1. CLI 通过 HTTP Range Requests 只读取全球文件的元数据和上海区域的瓦片
1. 根据网络情况，上海区域（zooms 0-15）只需几十秒到几分钟
1. 输出文件 `shanghai.pmtiles` 约 **20~50MB**（视 bbox 大小）

> **原理：** PMTiles 的目录结构经过优化，Region Requests 可以跳过不相关的瓦片数据。
>
> 与官方指南一致，`extract` 也支持只提取部分 zoom 范围（不需要 bbox）：
>
> ```bash
> # 提取全球 zoom 0-6 子集（约 60MB）
> pmtiles extract https://build.protomaps.com/20260805.pmtiles planet_z6.pmtiles --maxzoom=6
> ```

### bbox 参考（中国主要城市群）

| 区域           | bbox                    | 预估文件大小 |
| -------------- | ----------------------- | ------------ |
| 上海市区       | `120.8,30.6,122.2,31.9` | ~20MB        |
| 长三角         | `118.5,29.5,123.0,32.5` | ~80MB        |
| 京津冀（北京） | `115.0,38.5,118.0,41.5` | ~70MB        |
| 珠三角（广州） | `112.5,21.5,115.5,24.0` | ~60MB        |
| 成都/重庆      | `103.0,29.0,107.0,31.5` | ~50MB        |
| 香港           | `113.8,22.1,114.5,22.6` | ~10MB        |

### 上海的 bbox 是怎么来的

bbox 是手工框出来的**外接矩形**（不是算法计算），用 [bboxfinder](http://bboxfinder.com) 在上海市域图上画框复制坐标，或从行政边界取外包矩形。

对照上海市域官方范围（常用表述：东经 120°51′—122°12′，北纬 30°40′—31°53′ ≈ `120.85,30.67,122.2,31.88`）：

| bbox 值         | 对应地理边界                        | 取法                           |
| --------------- | ----------------------------------- | ------------------------------ |
| `120.8`（西界） | 青浦/松江西部，市域西界约 120.85°E  | 留 ~0.05° 白（覆盖到昆山边缘） |
| `30.6`（南界）  | 金山/奉贤南端，杭州湾北岸约 30.67°N | 留 ~0.07° 白（覆盖到平湖边缘） |
| `122.2`（东界） | 长江口/东海，市域东界约 122.2°E     | 与官方东界一致，含外海         |
| `31.9`（北界）  | 崇明岛北端约 31.88°N                | 略大于官方值，完整覆盖崇明岛   |

**要点：**

- 行政边界不是矩形，外接矩形必然包含邻省边缘（青浦西边是江苏、南边是浙江）——这是正常现象
- 旧值北界曾用 `31.8`，会切掉崇明最北端 ~0.08°，已改为 `31.9`
- 想让文件更贴合边界可用下面的 `--region` GeoJSON 方式，但低 zoom 瓦片仍是矩形网格、无法精确贴合
- 重新框选工具：bboxfinder.com（画矩形复制坐标）、geojson.io（导入边界自动显示 bounding box）

### 进阶：GeoJSON 不规则区域提取

```bash
pmtiles extract \
  https://build.protomaps.com/20260805.pmtiles \
  shanghai-area.pmtiles \
  --region=shanghai-region.geojson \
  --maxzoom=14
```

GeoJSON 可用 [geojson.io](https://geojson.io) 在线绘制导出，或从
[openstreetmap.org](https://www.openstreetmap.org/export) 导出行政边界。

## 3. 预览下载的 .pmtiles 地图

下载/裁剪得到 `shanghai.pmtiles` 后，**选择 1：在线工具 [pmtiles.io](https://pmtiles.io/)**：

1. 浏览器打开 [https://pmtiles.io/](https://pmtiles.io/)
1. 把 `shanghai.pmtiles` 拖入页面 Drop Zone（或点击选择文件）
1. 即可交互预览：缩放平移、图层开关、坐标信息——**无需安装任何东西**

选择 2：本地查看（静态服务器 + MapLibre `pmtiles://` 协议）见下方第 5 步——test-map.html 已实测通过。

## 4. 验证裁剪结果

```bash
# 查看文件信息
pmtiles show shanghai.pmtiles

# 输出示例：
#   tile_type:        mvt
#   tiles:            <实际瓦片数>（如 12945）
#   tile_compression: gzip
#   min_zoom:         0
#   max_zoom:         15
#   bounds:           120.8, 30.6, 122.2, 31.9
#   center:           121.5, 31.2
#   description:      Extracted from build.protomaps.com/20260805.pmtiles

# 查看包含哪些图层
pmtiles show --metadata shanghai.pmtiles | python3 -c "import sys,json; d=json.load(sys.stdin); print('图层:', [l.get('id') for l in d.get('vector_layers', [])])"
# 输出示例：图层: ['boundaries', 'buildings', 'earth', 'landcover', 'landuse', 'places', 'pois', 'roads', 'water']
```

## 5. 本地查看 .pmtiles（test-map.html）

> 已实测通过。静态服务器 + MapLibre `pmtiles://` 协议（参考官方 [PMTiles in MapLibre GL](https://docs.protomaps.com/pmtiles/maplibre)）。

```bash
cd /path/to/pmtiles
# npx 免全局安装，首次运行自动下载 http-server
npx -y http-server . --cors --port 8080
# 验证：浏览器访问 http://localhost:8080/shanghai.pmtiles 可下载
```

保存 `test-map.html` 到 http-server 根目录：

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Protomaps Test</title>
  <style>body { margin: 0 } #map { width: 100vw; height: 100vh }</style>
  <script src="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.js"></script>
  <link href="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css" rel="stylesheet" />
  <script src="https://unpkg.com/pmtiles@3/dist/pmtiles.js"></script>
  <script src="https://unpkg.com/@protomaps/basemaps@5/dist/basemaps.js"></script>
</head>
<body>
  <div id="map"></div>
  <script>
    const protocol = new pmtiles.Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);

    const map = new maplibregl.Map({
      container: "map",
      style: {
        version: 8,
        glyphs: "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
        sprite: "https://protomaps.github.io/basemaps-assets/sprites/v4/light",
        sources: {
          protomaps: {
            type: "vector",
            url: "pmtiles:///shanghai.pmtiles",  // http-server 下用相对路径
            attribution: '© <a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org">OpenStreetMap</a>',
          },
        },
        layers: basemaps.layers("protomaps", basemaps.namedFlavor("light"), { lang: "zh" }),
      },
      center: [121.47, 31.23],
      zoom: 12,
    });
  </script>
</body>
</html>
```

访问 `http://localhost:8080/test-map.html` 即可看到上海地图。

> 原理：`pmtiles://` 协议由 pmtiles.js 在客户端实现（header → 目录 → 瓦片三步 Range 请求），
> 详见 [PMTiles 格式与工具链](./pmtiles.md)。

## 部署方案

PMTiles 最大的优势是部署简单——**不需要地图服务器**：

| 平台                | 说明                                                   | 成本                 |
| ------------------- | ------------------------------------------------------ | -------------------- |
| **Cloudflare R2**   | 兼容 S3 API，免流量费                                  | 存储费 ~$0.015/GB/月 |
| **AWS S3**          | 需开启 CORS                                            | 标准 S3 定价         |
| **自建 Web Server** | 需支持 Range Requests（Nginx / Caddy / Apache 等均可） | 取决于服务器         |

> 部署后 MapLibre 中改用完整 URL：
> `url: "pmtiles://https://cdn.example.com/shanghai.pmtiles"`
>
> 参考官方：[Cloud Storage](https://docs.protomaps.com/pmtiles/cloud-storage)（S3 / R2 / 自建对象存储部署指南）

## 常见问题

| 问题                   | 原因                                                                                                           | 解决                                                            |
| ---------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `pmtiles extract` 很慢 | 远程全球文件大，Range 请求有延迟                                                                               | 加 `--maxzoom=12` 限制最大缩放级别                              |
| 能看到上海以外的区域   | 正常：extract 按瓦片复制，低 zoom 瓦片覆盖全球/大洲（zoom 0 一张瓦片=全球）；`pmtiles show` 的 bounds 仍是上海 | 不影响使用；想精简可加 `--minzoom=6`（缩到 minzoom 以下会空白） |
| 裁剪文件过大           | bbox 太大或 zoom 太高                                                                                          | 缩小 bbox 或加 `--maxzoom` 限制                                 |
| 地图白屏               | pmtiles 协议未注册                                                                                             | 确认调用了 `maplibregl.addProtocol("pmtiles", protocol.tile)`   |
| CORS 错误              | http-server 未加 `--cors`                                                                                      | 重新启动：`npx -y http-server . --cors`                         |
| 字体不显示             | glyphs URL 不可达                                                                                              | 使用 Protomaps 托管的字体                                       |
| 中文标签乱码           | 未设置 `lang` 或 OSM 无中文名                                                                                  | 在 `layers()` 中加 `{ lang: "zh" }`                             |

## 参考

- [PMTiles 格式与工具链](./pmtiles.md)
- [MapLibre 集成](./maplibre.md)
- [官方指南 Getting Started](https://docs.protomaps.com/guide/getting-started)
- [bbox 工具](http://bboxfinder.com)
- [在线绘制 GeoJSON](https://geojson.io)
