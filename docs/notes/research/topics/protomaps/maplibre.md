---
hide:
  - navigation
title: MapLibre 集成 Protomaps
tags:
  - research
  - tech
  - protomaps
  - pmtiles
  - maplibre
categories:
  - dev
---

# :material-code-tags: MapLibre 集成

> **本页目的：** 讲解如何在前端（MapLibre GL JS）渲染已制作好的 `.pmtiles` 底图（如 [上海地区底图项目](./shanghai-map.md) 裁剪出的 `shanghai.pmtiles`）。
> 只涉及**渲染代码**——数据就是那一个 `.pmtiles` 文件，**无需下载任何额外数据**。
>
> 与「上海地区底图项目」第 5 步（test-map.html 快速验证）不同，本页系统讲解集成到**自己应用**的方法：
> 协议原理、`@protomaps/basemaps` 完整样式、React 组件、样式切换与性能。
>
> ⚠️ **3D 地形（TerrainControl）不在本页范围**——它需要单独的 DEM 高程数据，与 Protomaps 底图无关。

## 1. 原理：pmtiles 自定义协议

MapLibre 默认不认识 `.pmtiles` 文件。通过 `pmtiles` npm 包的 `Protocol` 注册一个
自定义 URL 协议（`pmtiles://`），MapLibre 请求瓦片时就会走该协议处理器，
由它通过 HTTP Range Requests 从 PMTiles 文件中提取所需瓦片：

```bash
pnpm add pmtiles
```

```ts
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";

// 注册 pmtiles 协议（全局一次即可）
const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);
```

> **关键点：** source 的 `url` 必须以 `pmtiles://` 为前缀，MapLibre 才会使用注册的协议处理器。

## 2. 最简集成

```ts
const map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    sources: {
      protomaps: {
        type: "vector",
        url: "pmtiles:///shanghai.pmtiles", // 本地相对路径
        attribution: '© <a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org">OpenStreetMap</a>',
      },
    },
    layers: [ /* 矢量图层定义 */ ],
  },
  center: [121.47, 31.23],
  zoom: 11,
});
```

URL 写法：

| 场景                        | url                                                  |
| --------------------------- | ---------------------------------------------------- |
| 本地相对路径（http-server） | `pmtiles:///shanghai.pmtiles`                        |
| 远程对象存储                | `pmtiles://https://cdn.example.com/shanghai.pmtiles` |

## 3. 完整底图样式：@protomaps/basemaps（推荐）

手写所有道路、水系、建筑、地名图层太繁琐。Protomaps 提供 npm 包自动生成完整样式：

```bash
pnpm add @protomaps/basemaps
```

```ts
import { layers, namedFlavor } from "@protomaps/basemaps";
import { Protocol } from "pmtiles";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const protocol = new Protocol();
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
        url: "pmtiles:///shanghai.pmtiles",
        attribution: '© <a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org">OpenStreetMap</a>',
      },
    },
    layers: layers("protomaps", namedFlavor("light"), { lang: "zh" }),
  },
  center: [121.47, 31.23],
  zoom: 11,
});
```

### layers() 函数签名

```ts
layers(
  sourceName: string,      // 对应 sources 中的 key
  flavor: Flavor,          // 风格：light / dark / white / black / grayscale
  options?: {
    lang?: string;         // 语言，如 "zh"、"en"、"ja"、"ko"，默认英文
    labelsOnly?: boolean;  // 是否只显示文字标签
  }
)
```

### 支持的 Flavor（风格）

| 值                         | 效果         |
| -------------------------- | ------------ |
| `namedFlavor("light")`     | 浅色（默认） |
| `namedFlavor("dark")`      | 深色         |
| `namedFlavor("white")`     | 纯白极简     |
| `namedFlavor("black")`     | 纯黑         |
| `namedFlavor("grayscale")` | 灰度         |

> **中文标签：** 设置 `lang: "zh"` 后，城市名称、道路名称等会使用中文渲染（如果 OSM 数据中有中文名）。

## 4. React 集成模板

```tsx
import * as React from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { layers, namedFlavor } from "@protomaps/basemaps";

export const MapViewProtomaps = () => {
  const mapRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const protocol = new Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);

    const map = new maplibregl.Map({
      container: mapRef.current!,
      style: {
        version: 8,
        glyphs: "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
        sprite: "https://protomaps.github.io/basemaps-assets/sprites/v4/light",
        sources: {
          protomaps: {
            type: "vector",
            url: "pmtiles:///shanghai.pmtiles",
            attribution: '© <a href="https://protomaps.com">Protomaps</a>',
          },
        },
        layers: layers("protomaps", namedFlavor("light"), { lang: "zh" }),
      },
      center: [121.47, 31.23],
      zoom: 11,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    return () => { map.remove(); }; // 防内存泄漏
  }, []);

  return <div ref={mapRef} style={{ width: "100%", height: "500px" }} />;
};
```

> **React 要点：** Map 必须在 `useEffect` 内创建，cleanup 中 `map.remove()`。

## 5. 底图切换（可选）

```ts
const switchToSatellite = () => {
  const mapStyle = map.getStyle();
  mapStyle.sources = {
    satellite: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
    },
  };
  mapStyle.layers = [{ id: "satellite", type: "raster", source: "satellite" }];
  map.setStyle(mapStyle);
};
```

> `setStyle()` 会重置地图状态（控件、图层），需要重新添加。

## 6. 性能清单

- [x] `map.remove()` 在组件卸载时调用
- [x] 事件监听在 useEffect cleanup 中移除
- [x] `pmtiles://` 协议全局只注册一次
- [x] 大量点数据用 Layer + GeoJSON source（而非 Marker）
- [x] 生产环境将 PMTiles 放到 CDN / R2（免流量费）

## 7. 参考链接

| 资源                      | 链接                                                                                         |
| ------------------------- | -------------------------------------------------------------------------------------------- |
| MapLibre GL JS 文档       | [https://maplibre.org/maplibre-gl-js/docs/](https://maplibre.org/maplibre-gl-js/docs/)       |
| MapLibre PMTiles 集成指南 | [https://docs.protomaps.com/pmtiles/maplibre](https://docs.protomaps.com/pmtiles/maplibre)   |
| @protomaps/basemaps API   | [https://docs.protomaps.com/basemaps/maplibre](https://docs.protomaps.com/basemaps/maplibre) |
| MapLibre Demo Tiles       | [https://demotiles.maplibre.org/](https://demotiles.maplibre.org/)                           |
| 底图下载与预览            | [https://maps.protomaps.com/](https://maps.protomaps.com/)                                   |

→ 上一站：[上海地区底图项目](./shanghai-map.md)
