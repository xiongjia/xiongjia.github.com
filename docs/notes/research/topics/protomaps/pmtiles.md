---
hide:
  - navigation
title: PMTiles 格式与工具链
tags:
  - research
  - tech
  - protomaps
  - pmtiles
categories:
  - dev
---

# :material-archive: PMTiles 格式与工具链

> 环境准备：PMTiles 格式原理与工具链（pmtiles CLI、Tippecanoe、Planetiler 的安装与使用）。

## 1. PMTiles 是什么

PMTiles 是一种**单文件瓦片归档格式**：把整棵 Z/X/Y 瓦片金字塔（矢量 MVT 或栅格）打包进一个 `.pmtiles` 文件。

传统瓦片服务需要：

```
很多个小文件（每张瓦片一个）→ 需要瓦片服务器 → 需要运维
```

PMTiles 只需要：

```
一个文件 → 放在对象存储/CDN 上 → HTTP Range Requests 按需读取
```

### 文件内部结构

```
.pmtiles 文件
├── Header（头部）       → 版本、元数据偏移、root directory 偏移等
├── JSON Metadata        → bounds、min/max zoom、vector_layers 等
├── Root Directory       → 瓦片寻址索引（类似 B-tree 的目录）
└── Tile Data            → 实际瓦片数据（支持去重）
```

### 客户端读取流程（单文件如何被读取）

`.pmtiles` 是**可随机寻址的布局**（类似数据库文件 + B-tree 索引），浏览器读取一张瓦片最多 **3 次 Range 请求**：

```js
// 第 1 步：读固定 127 字节 header，拿到目录偏移
fetch(url, { headers: { Range: "bytes=0-126" } })
// → root directory 偏移/length、metadata 偏移

// 第 2 步：读 root directory（瓦片索引，可能一次请求全拿到）
fetch(url, { headers: { Range: `bytes=${dirOffset}-${dirOffset + dirLen - 1}` } })
// → 二分查找 (z,x,y) → tile_id → 得到瓦片的 offset/length

// 第 3 步：只取那一张瓦片的字节
fetch(url, { headers: { Range: `bytes=${tileOffset}-${tileOffset + tileLen - 1}` } })
// → gzip 解压 → MVT 解码 → 交给 MapLibre 渲染
```

要点：

- **pmtiles 协议在客户端做读取**：`pmtiles.js` 的 `Protocol` 实现上述逻辑并注册为 `pmtiles://`，MapLibre 无感使用
- **`pmtiles serve` 是服务器端读取**：ZXY 端点由服务端做同样的寻址，浏览器看到的是普通瓦片 URL（无需协议）
- **pmtiles.io 拖入本地文件**：文件已在内存，按 offset 直接切片，连网络都省了

### 为什么能按需读取

| 特性                    | 说明                                                   |
| ----------------------- | ------------------------------------------------------ |
| **HTTP Range Requests** | 浏览器只请求需要的字节范围，不加载整个文件             |
| **Root Directory 优化** | 目录结构经优化，可以跳过不相关区域的瓦片数据           |
| **瓦片去重**            | 相同内容的瓦片只存一份（例如低 zoom 下的空白海洋瓦片） |
| **JSON 元数据**         | `pmtiles show` 可直接读出 bounds、图层信息             |

### 常见疑问

**问：文件那么大（全球 128GB），浏览器怎么用？**
答：浏览器通过 Range Request 只拉取自己需要的瓦片字节，通常一次请求只有几十 KB。文件总大小只影响存储成本，不影响加载速度。

**问：和传统 XYZ 瓦片目录有什么区别？**
答：传统方案每张瓦片是一个 HTTP 请求（文件多、延迟高、需要瓦片服务器）；PMTiles 一个文件即可服务全部瓦片，配合 CDN 静态托管，零服务器。

## 2. 工具链总览

| 工具                                | 用途                                      |
| ----------------------------------- | ----------------------------------------- |
| **pmtiles CLI**                     | 管理、查看、裁剪、合并 PMTiles 文件       |
| **Tippecanoe**                      | GeoJSON/Shapefile → PMTiles（自己的数据） |
| **Planetiler** (protomaps/basemaps) | OSM PBF → 完整底图 PMTiles（专业级）      |

### 2.1 pmtiles CLI

四种安装方式任选其一：

| 方式                       | 说明                                                                                                                                                                               |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Homebrew**               | `brew install protomaps/tap/pmtiles`，macOS 最方便                                                                                                                                 |
| **GitHub Releases 二进制** | 单文件无依赖；从 [Releases 页面](https://github.com/protomaps/go-pmtiles/releases) 下载对应平台包（v1.31.2 起为 `.zip`，如 `go-pmtiles-<版本>_Darwin_arm64.zip`），解压后放入 PATH |
| **Go 工具链**              | `go install github.com/protomaps/go-pmtiles@latest`，需 Go 1.25+；输出: `go-pmtiles`                                                                                               |
| **Docker**                 | 官方镜像 `protomaps/go-pmtiles`，免安装到本机                                                                                                                                      |

示例一（brew）：

```bash
brew install protomaps/tap/pmtiles
pmtiles --version
```

示例二（go install）：

```bash
go install github.com/protomaps/go-pmtiles@latest
go-pmtiles --version
```

常用子命令：

| 命令              | 说明                                 |
| ----------------- | ------------------------------------ |
| `pmtiles extract` | 从 PMTiles（本地或远程 URL）裁剪区域 |
| `pmtiles show`    | 查看文件元数据、图层、zoom 范围      |
| `pmtiles merge`   | 合并多个**不相交**的 PMTiles 档案    |
| `pmtiles convert` | 在目录/存档/MBTiles 等格式间转换     |
| `pmtiles upload`  | 上传到 S3 兼容对象存储               |

> 合并**重叠区域**的档案（如底图 + 自己的数据）用 tippecanoe 的 `tile-join`，见 [2.2](#22-tippecanoe) 与 [自制 PMTiles 地图](./make-own-map.md)。

### 2.2 Tippecanoe（自有数据 → 瓦片）

将 GeoJSON/Shapefile 转为 PMTiles（v2.17+ 直接支持 `.pmtiles` 输出）。

安装方式（Tippecanoe 是 C++ 项目，无官方二进制发布，也不支持 `go install`）：

| 方式         | 说明                                                                                                 |
| ------------ | ---------------------------------------------------------------------------------------------------- |
| **Homebrew** | `brew install tippecanoe`，macOS 推荐                                                                |
| **源码编译** | `git clone https://github.com/felt/tippecanoe.git && make && sudo make install`，依赖 sqlite3 / zlib |

示例一（brew）：

```bash
brew install tippecanoe
tippecanoe --version
```

示例二（源码编译）：

```bash
git clone https://github.com/felt/tippecanoe.git
cd tippecanoe
make -j
sudo make install
tippecanoe --version
```

将 GeoJSON 转为 PMTiles：

```bash
tippecanoe -zg --projection=EPSG:4326 \
  -o my-data.pmtiles \
  -l my-layer my-data.geojson

# Shapefile 先转 GeoJSON
ogr2ogr -t_srs EPSG:4326 data.json data.shp

# 多个 PMTiles 合并
tile-join -o merged.pmtiles *.pmtiles
```

| 参数                       | 说明                                                        |
| -------------------------- | ----------------------------------------------------------- |
| `-zg`                      | 自动检测最佳最大缩放级别（**单点数据不可用**，需显式 zoom） |
| `--projection=EPSG:4326`   | 输入使用 WGS84 经纬度                                       |
| `-o`                       | 输出文件名                                                  |
| `-l`                       | 图层名称（对应 MapLibre 中的 source-layer）                 |
| `--maxzoom=14`             | 限制最大 zoom（文件更小）                                   |
| `--drop-densest-as-needed` | 自动简化密集数据                                            |

### 2.3 Planetiler（OSM → 完整底图，专业级）

如需构建类似 Protomaps 官方底图的完整图层（道路、水系、建筑、地名），需要 Planetiler 管线。
basemaps 仓库无预编译二进制与 brew 包，需通过 Maven 构建或 Docker 本地构建镜像：

| 方式                | 说明                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------- |
| **Maven 源码构建**  | 官方方式：`git clone ... && mvn clean package`，生成 `*-with-deps.jar`，需 Java 21+ / Maven |
| **Docker 本地构建** | `docker build -t protomaps/basemaps .`，免装 Java / Maven                                   |

示例一（Maven 构建）：

```bash
# 前置：Java 21+ / Maven（macOS）
brew install openjdk@21 maven

# 克隆仓库并构建
git clone https://github.com/protomaps/basemaps
cd basemaps/tiles
mvn clean package
```

示例二（Docker 本地构建）：

```bash
docker build -t protomaps/basemaps .
docker run -v ./data:/tiles/data --rm -it protomaps/basemaps \
  --output=data/monaco.pmtiles --area=monaco
```

运行管线（Maven 产物）：

```bash
# 准备 OSM 区域数据（Geofabrik 中国约 1.2GB）
curl -L https://download.geofabrik.de/asia/china-latest.osm.pbf -o data/sources/china.osm.pbf

# 用边界 GeoJSON 裁剪构建
java -jar target/protomaps-basemap-HEAD-with-deps.jar \
  --clip=shanghai.geojson \
  --area=shanghai \
  --download
```

> `--download` 首次运行会下载辅助资源（预处理水系/陆地多边形、Natural Earth、语言包等），耗时取决于网络。

> 本项目不需要此路径——直接从 Protomaps 官方每日构建裁剪即可，见
> [上海地区底图项目](./shanghai-map.md)。

## 3. 坐标系说明

| 概念              | 值                | 说明                                   |
| ----------------- | ----------------- | -------------------------------------- |
| **输入坐标**      | EPSG:4326 (WGS84) | 经纬度，如 `[121.47, 31.23]`           |
| **瓦片坐标**      | Z / X / Y         | 瓦片行列号，工具自动计算               |
| **瓦片内部**      | EPSG:3857         | 瓦片几何使用 Web Mercator 投影         |
| **MapLibre 显示** | EPSG:4326         | `map.center` 和 GeoJSON 输入仍用经纬度 |

**关键要点：**

- 输入数据（GeoJSON、OSM PBF）都用 EPSG:4326
- Tippecanoe 默认假定输入是 EPSG:4326，`--projection` 大多数时候可省略
- 瓦片内部自动转 EPSG:3857，无需手动处理
- 千万不要把 EPSG:3857 的坐标直接当经纬度传给 tippecanoe

### 瓦片数量示例

| Zoom | 全球瓦片数    | 上海区域瓦片数 | 用途     |
| ---- | ------------- | -------------- | -------- |
| 0    | 1×1 = 1       | 1              | 全球概览 |
| 5    | 32×32         | 1~2            | 大洲     |
| 10   | 1,024×1,024   | ~16            | 城市轮廓 |
| 12   | 4,096×4,096   | ~64            | 城区道路 |
| 14   | 16,384×16,384 | ~256           | 街道级别 |
| 15   | 32,768×32,768 | ~1,000         | 建筑细节 |

> 每个 zoom 的瓦片数量是 2^zoom × 2^zoom。Zoom 15 全球约 10 亿张瓦片，
> PMTiles 正是通过金字塔结构 + 去重实现高效存储。

## 4. 参考链接

| 资源                           | 链接                                                                               |
| ------------------------------ | ---------------------------------------------------------------------------------- |
| PMTiles 概念                   | [https://docs.protomaps.com/pmtiles/](https://docs.protomaps.com/pmtiles/)         |
| protomaps/go-pmtiles（GitHub） | [https://github.com/protomaps/go-pmtiles](https://github.com/protomaps/go-pmtiles) |
| PMTiles Spec                   | [https://github.com/protomaps/PMTiles](https://github.com/protomaps/PMTiles)       |
| Tippecanoe                     | [https://github.com/felt/tippecanoe](https://github.com/felt/tippecanoe)           |
| Planetiler                     | [https://github.com/protomaps/basemaps](https://github.com/protomaps/basemaps)     |
| 在线查看器                     | [https://pmtiles.io/](https://pmtiles.io/)                                         |

→ 下一步：[上海地区底图项目](./shanghai-map.md)
