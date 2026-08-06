---
hide:
  - navigation
title: 自制 PMTiles 地图（最简单例子）
tags:
  - research
  - tech
  - protomaps
  - pmtiles
  - tippecanoe
categories:
  - dev
---

# :material-map-plus: 自制 PMTiles 地图（最简单例子）

> **本页目的：** 用**自己的数据**（不依赖 OSM 底图）制作一张最简单的 PMTiles 地图并渲染。
> 流程：GeoJSON → Tippecanoe → `.pmtiles` → MapLibre，全程本地完成。
>
> 前置：需要安装 Tippecanoe（见 [PMTiles 格式与工具链](./pmtiles.md#22-tippecanoe)）。
> 进阶：从 OSM 构建完整底图（含道路/水系/地名）参考官方 [Building Tiles](https://docs.protomaps.com/basemaps/build)，见 [PMTiles 格式与工具链](./pmtiles.md#23-planetiler)。

## 1. 准备数据（GeoJSON）

> 示例坐标是上海（与上海项目一致，仅作演示）；可换成任意经纬度。
> 注意：自制文件只含自己的数据，**不含 OSM 底图**；pmtiles.io 会叠加它**内置**的 Protomaps 底图
> （界面 basemap 开关，默认关、黑色风格）——关掉开关就只剩自己的点。

以 3 个咖啡店点为例，保存为 `coffee.geojson`：

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "name": "咖啡A" },
      "geometry": { "type": "Point", "coordinates": [121.47, 31.23] }
    },
    {
      "type": "Feature",
      "properties": { "name": "咖啡B" },
      "geometry": { "type": "Point", "coordinates": [121.49, 31.21] }
    },
    {
      "type": "Feature",
      "properties": { "name": "咖啡C" },
      "geometry": { "type": "Point", "coordinates": [121.44, 31.26] }
    }
  ]
}
```

### 怎么取坐标（地址 → 经纬度）

| 方式               | 说明                                                                                            |
| ------------------ | ----------------------------------------------------------------------------------------------- |
| **geojson.io**     | 搜地址 → 地图点选 → 自动生成 GeoJSON，直接就是本页格式                                          |
| **自己的地图点选** | test-map.html 加 `map.on("click", e => console.log(e.lngLat))`，点哪取哪                        |
| **高德拾取坐标**   | https://lbs.amap.com/tools/picker 搜中文地址                                                    |
| **OSM Nominatim**  | `curl "https://nominatim.openstreetmap.org/search?format=json&q=上海南京东路100号"`（代码场景） |

> ⚠️ **坐标系坑：** 高德/百度拾取的是 **GCJ-02 火星坐标**（加密偏移），直接用于 OSM/MapLibre（WGS-84）会偏移约 300~500 米；
> 用 geojson.io / Nominatim 取坐标则无此问题，或自行 GCJ-02 → WGS-84 转换。

#### 实例：地址 → 单点 pmtiles（上海东方体育中心）

以高德拾取的坐标 `121.48, 31.16`（GCJ-02）为例，完整流程：

**1. GCJ-02 → WGS-84 转换**（高德坐标必须转，否则偏移 300~500 米）：

```bash
python3 <<'EOF'
import math
def _tlat(x, y):
    r = -100.0 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    r += (20*math.sin(6*x*math.pi) + 20*math.sin(2*x*math.pi)) * 2/3
    r += (20*math.sin(y*math.pi) + 40*math.sin(y/3*math.pi)) * 2/3
    r += (160*math.sin(y/12*math.pi) + 320*math.sin(y*math.pi/30)) * 2/3
    return r
def _tlng(x, y):
    r = 300.0 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    r += (20*math.sin(6*x*math.pi) + 20*math.sin(2*x*math.pi)) * 2/3
    r += (20*math.sin(x*math.pi) + 40*math.sin(x/3*math.pi)) * 2/3
    r += (150*math.sin(x/12*math.pi) + 300*math.sin(x/30*math.pi)) * 2/3
    return r
def gcj2wgs(lng, lat):
    dlat = _tlat(lng-105, lat-35); dlng = _tlng(lng-105, lat-35)
    rad = lat/180*math.pi; magic = math.sin(rad); magic = 1 - 0.00669342162296594323*magic*magic
    sq = math.sqrt(magic)
    dlat = dlat*180/((6378245*(1-0.00669342162296594323))/(magic*sq)*math.pi)
    dlng = dlng*180/(6378245/sq*math.cos(rad)*math.pi)
    return lng*2-(lng+dlng), lat*2-(lat+dlat)
print('%f, %f' % gcj2wgs(121.48, 31.16))
EOF
# 输出：121.475504, 31.161994  ← 这就是 WGS-84 坐标
```

**2. GeoJSON（用转换后的 WGS-84 坐标）**：

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "name": "上海东方体育中心" },
      "geometry": { "type": "Point", "coordinates": [121.475504, 31.161994] }
    }
  ]
}
```

**3. tippecanoe 转 PMTiles**（单点不能用 `-zg`，需显式 zoom）：

```bash
tippecanoe -Z0 -z14 --projection=EPSG:4326 \
  -o oriental-sports.pmtiles \
  -l poi oriental-sports.geojson
```

**4. 验证与测试**：

```bash
pmtiles show --metadata oriental-sports.pmtiles | python3 -c "import sys,json; d=json.load(sys.stdin); print('图层:', [l.get('id') for l in d.get('vector_layers', [])])"
# 图层: ['poi']
```

浏览器测试：pmtiles.io 拖入文件，或本地 test-map.html 里 `source-layer` 用 `poi`、`url: "pmtiles:///oriental-sports.pmtiles"`。

## 2. Tippecanoe 转为 PMTiles

```bash
tippecanoe -zg --projection=EPSG:4326 \
  -o coffee.pmtiles \
  -l coffee coffee.geojson
```

| 参数                | 说明                                                    |
| ------------------- | ------------------------------------------------------- |
| `-zg`               | 自动检测最佳最大缩放级别（**单点数据不可用**）          |
| `-Z0 -z14`          | 单点/少量点：显式指定 minzoom/maxzoom                   |
| `-o coffee.pmtiles` | 输出文件                                                |
| `-l coffee`         | **图层名**（对应 MapLibre 的 `source-layer`，必须一致） |

验证：

```bash
pmtiles show --metadata coffee.pmtiles | python3 -c "import sys,json; d=json.load(sys.stdin); print('图层:', [l.get('id') for l in d.get('vector_layers', [])])"
# 图层: ['coffee']
```

## 3. MapLibre 渲染

`coffee.pmtiles` 放到 http-server 根目录，页面用 circle 图层显示点：

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>My Coffee Map</title>
  <style>body { margin: 0 } #map { width: 100vw; height: 100vh }</style>
  <script src="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.js"></script>
  <link href="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css" rel="stylesheet" />
  <script src="https://unpkg.com/pmtiles@3/dist/pmtiles.js"></script>
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
        sources: {
          coffee: {
            type: "vector",
            url: "pmtiles:///coffee.pmtiles",
          },
        },
        layers: [
          {
            id: "coffee-circle",
            type: "circle",
            source: "coffee",
            "source-layer": "coffee",   // 与 tippecanoe -l 一致
            paint: {
              "circle-color": "#3b82f6",
              "circle-radius": 8,
            },
          },
        ],
      },
      center: [121.47, 31.23],
      zoom: 11,
    });
  </script>
</body>
</html>
```

```bash
cd /path/to/pmtiles
npx -y http-server . --cors --port 8080
# 访问 http://localhost:8080/coffee-map.html 看到 3 个蓝色圆点
```

> **关键点：** `source-layer` 必须等于 tippecanoe 的 `-l` 参数（本例 `coffee`），否则地图不显示。

## 4. 叠加到已有底图（多 pmtiles 示例）

把 `coffee.pmtiles` 叠加到 `shanghai.pmtiles` 底图上：**一个 Map 里加两个 source**，不需要合并文件。

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Shanghai + Coffee</title>
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
          // source 1：shanghai 底图（9 个图层）
          protomaps: {
            type: "vector",
            url: "pmtiles:///shanghai.pmtiles",
            attribution: '© <a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org">OpenStreetMap</a>',
          },
          // source 2：自己的数据
          coffee: {
            type: "vector",
            url: "pmtiles:///coffee.pmtiles",
          },
        },
        layers: [
          // shanghai 底图的完整样式（道路/水系/地名等）
          ...basemaps.layers("protomaps", basemaps.namedFlavor("light"), { lang: "zh" }),
          // 自己的咖啡点（叠加在上层）
          {
            id: "coffee-circle",
            type: "circle",
            source: "coffee",
            "source-layer": "coffee",
            paint: {
              "circle-color": "#ef4444",
              "circle-radius": 8,
              "circle-stroke-width": 2,
              "circle-stroke-color": "#ffffff",
            },
          },
        ],
      },
      center: [121.47, 31.23],
      zoom: 11,
    });
  </script>
</body>
</html>
```

```bash
# 两个 pmtiles 文件放同一目录
cd /path/to/pmtiles
npx -y http-server . --cors --port 8080
# 访问 http://localhost:8080/overlay.html：完整上海底图 + 红色咖啡点
```

> 想分发**单文件**时再合并：`tile-join -o combined.pmtiles shanghai.pmtiles coffee.pmtiles`（图层名不能冲突；`pmtiles merge` 只支持不相交档案，不适用）。

## 5. 进阶

- **点变标签**：加一个 symbol 图层，`layout: { "text-field": ["get", "name"] }` 显示店名
- **区域/线数据**：GeoJSON 换成 Polygon / LineString 即可，图层类型用 `fill` / `line`
- **数据更新**：改 GeoJSON 后重新跑 tippecanoe 覆盖 `coffee.pmtiles` 即可
- **从 OSM 构建完整底图**：官方 [Building Tiles](https://docs.protomaps.com/basemaps/build)（Planetiler 管线），见 [PMTiles 格式与工具链](./pmtiles.md#23-planetiler)
