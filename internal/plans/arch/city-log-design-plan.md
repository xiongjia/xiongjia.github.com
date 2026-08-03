---
title: City Log — 城市打卡 App 设计文档
created: 2026-07-31
archived: 2026-08-04
status: cancelled
tags: [city-log, pwa, maplibre, pmtiles, offline-first]
---

# City Log — 城市打卡 App 设计文档

> **归档说明**：设计文档已被 [city-log-project.md](../city-log-project.md) 取代（该计划沿用并细化本设计）。

> **项目定位**：个人城市足迹记录工具，照片 + 地图双核心，支持离线使用。
> **目标平台**：Web App（PWA），后续可扩展为 React Native / Flutter。
> **核心体验**：打开即见地图，随手标记，离线可用，数据完全自主。

______________________________________________________________________

## 一、核心设计原则

| 原则                  | 说明                                   |
| --------------------- | -------------------------------------- |
| **离线优先**          | 地图底图、照片、打卡数据全部可离线访问 |
| **零配置上手**        | 无需注册账号，打开即用，数据存本地     |
| **空间 + 时间双维度** | 地图回答"我在哪"，时间线回答"什么时候" |
| **轻量**              | 城市级地图 < 50MB，首屏 < 2MB，秒开    |
| **渐进增强**          | 有网时自动同步/更新，无网时完整可用    |

______________________________________________________________________

## 二、技术栈

| 层级         | 技术                                               | 用途                                     |
| ------------ | -------------------------------------------------- | ---------------------------------------- |
| **地图引擎** | MapLibre GL JS                                     | 渲染矢量瓦片、标记、交互                 |
| **瓦片格式** | PMTiles                                            | 单文件矢量瓦片，支持 HTTP Range 按需读取 |
| **瓦片来源** | Protomaps 每日构建（裁剪后）                       | OSM 数据，中文标签完整                   |
| **离线缓存** | Service Worker + Cache Storage                     | 拦截 Range 请求，整文件缓存              |
| **前端框架** | Vanilla JS / Vue 3 / React（任选）                 | 界面逻辑                                 |
| **数据存储** | IndexedDB (Dexie.js)                               | 打卡记录、照片元数据、用户设置           |
| **照片存储** | IndexedDB Blob / OPFS (Origin Private File System) | 照片二进制数据                           |
| **打包**     | Vite                                               | 构建、PWA 配置                           |

______________________________________________________________________

## 三、数据模型

### 3.1 打卡记录 (CheckIn)

```typescript
interface CheckIn {
  id: string;              // UUID
  lat: number;             // 纬度
  lng: number;             // 经度
  title: string;           // 地点名称
  description: string;     // 个人笔记
  photos: Photo[];         // 关联照片
  tags: string[];          // 标签：美食/景点/咖啡/购物...
  rating: number;          // 1-5 星
  visitedAt: Date;         // 打卡时间
  createdAt: Date;         // 记录创建时间
  updatedAt: Date;         // 最后修改时间
}

interface Photo {
  id: string;
  blob: Blob;              // 照片二进制
  thumbnailBlob: Blob;     // 缩略图（地图标记用）
  width: number;
  height: number;
  takenAt: Date;           // EXIF 拍摄时间
}
```

### 3.2 地图配置 (MapConfig)

```typescript
interface MapConfig {
  cityName: string;        // 当前城市，如 "上海市"
  bbox: [number, number, number, number]; // 城市边界 [minLng, minLat, maxLng, maxLat]
  pmtilesUrl: string;      // 本地或远程 PMTiles 路径
  styleUrl: string;        // MapLibre Style JSON 路径
  center: [number, number]; // 默认中心坐标
  zoom: number;            // 默认缩放级别
}
```

______________________________________________________________________

## 四、界面架构（三层信息模型）

### 4.0 界面原型概览

以下原型展示了 City Log 的核心界面状态与交互流程：

```
┌─────────────────────────────────────┐
│  📍 上海市          [网格] [筛选]    │  ← 顶部栏：城市定位 + 视图切换
├─────────────────────────────────────┤
│                                     │
│    ═══════════ 街道 ═══════════     │
│         ┌───┐                       │
│    ═════│🖼️ │════ 街道 ═════════     │  ← 空间层：地图 + 照片标记
│         └───┘  南京路                │      圆形缩略图标记，选中带脉冲
│              ┌───┐                  │
│    公园 ████│🖼️ │████              │
│             └───┘  淮海路           │
│    ═══════════ 街道 ═══════════     │
│                  ┌───┐              │
│    ~~~~~~~~ 水域  │🖼️ │ 陆家嘴       │
│                  └───┘              │
│                                     │
├─────────────────────────────────────┤
│  ────                               │
│  最近打卡              5 个地点      │  ← 时间层：底部横向时间线
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ │      卡片 = 缩略图 + 标题 + 日期
│  │ 🖼️  │ │ 🖼️  │ │ 🖼️  │ │ 🖼️  │ │      点击 ↔ 地图标记高亮联动
│  │●外滩 │ │ 面馆 │ │东方明珠│ │Brunch│ │
│  └─────┘ └─────┘ └─────┘ └─────┘ │
│                                     │
└─────────────────────────────────────┘
              [ + ]                   ← FAB：添加打卡
```

**界面状态说明：**

| 状态                 | 说明                                             |
| -------------------- | ------------------------------------------------ |
| **地图视图（默认）** | 地图占满屏幕，底部叠加时间线滑块，右下角 FAB     |
| **网格视图**         | 地图隐藏，显示按月份分组的照片墙，FAB 移至右下角 |
| **详情弹窗**         | 从底部滑出的 Sheet，展示单条打卡的完整信息       |
| **筛选面板**         | 从顶部右侧滑出的浮层，按标签/时间过滤            |
| **添加流程**         | 点击 FAB → 提示"点击地图位置" → 弹出表单         |

**交互流程图：**

```
打开 App
   │
   ▼
┌─────────────┐
│  地图视图    │ ← 默认状态，显示当前城市地图 + 最近打卡时间线
└──────┬──────┘
       │
   ┌───┴───┐
   ▼       ▼
点击标记  点击时间线卡片
   │       │
   └───┬───┘
       ▼
┌─────────────┐
│  详情弹窗    │ ← 从底部滑出，展示照片/笔记/元信息/操作按钮
└──────┬──────┘
       │
   ┌───┴───┐
   ▼       ▼
  编辑     删除
   │
   ▼
┌─────────────┐
│  添加打卡    │ ← 长按地图 或 点击 FAB
└─────────────┘
```

### 4.1 空间层 — 地图视图

### 4.1 空间层 — 地图视图

- **地图底图**：PMTiles 矢量瓦片，自定义样式（浅色/深色/卫星混合）
- **打卡标记**：圆形照片缩略图（44px），替代传统 pin
  - 选中状态：红色脉冲动画 + 放大 1.2x
  - 悬停/触摸：放大 + 提升 z-index
- **聚类**：同区域多个打卡自动聚合成数字气泡，点击展开
- **轨迹线**：可选，按时间顺序连接打卡点，形成城市足迹线

### 4.2 时间层 — 底部时间线（Bottom Sheet）

- **横向滚动卡片**：最近打卡按时间倒序排列
- **双向联动**：
  - 点击时间线卡片 → 地图飞移到对应标记并高亮
  - 点击地图标记 → 时间线滚动到对应卡片并高亮
- **上滑展开**：拖动横条可上滑为全屏列表，支持按月份分组

### 4.3 详情层 — 打卡详情（Sheet Modal）

- **触发**：点击标记或时间线卡片
- **动画**：从底部滑入（Bottom Sheet），背景遮罩 + 模糊
- **内容结构**：
  1. 大图（首张照片，可横向滑动查看多张）
  1. 标题 + 星级评分
  1. 标签云
  1. 个人笔记
  1. 元信息（日期、地址、天气——可选）
  1. 操作按钮（导航、编辑、删除）

### 4.4 辅助视图

| 视图         | 触发方式     | 用途                                |
| ------------ | ------------ | ----------------------------------- |
| **网格视图** | 顶部切换按钮 | 按月份分组的照片墙，快速浏览        |
| **筛选面板** | 顶部筛选按钮 | 按标签/时间范围过滤                 |
| **添加打卡** | 右下角 FAB   | 长按地图位置或点击 FAB 进入添加流程 |

______________________________________________________________________

## 五、离线地图方案（核心实现）

### 5.1 PMTiles 按需读取原理

```
PMTiles 文件结构：
┌─────────────┐  ← Header (前 127 bytes)：目录偏移位置
├─────────────┤
│  瓦片数据区  │  ← 实际瓦片数据，按需跳读
├─────────────┤
│  目录索引    │  ← 记录每个瓦片 {offset, length}
└─────────────┘

加载流程：
1. 读取 Header → 知道 Directory 在哪
2. 读取 Directory → 建立 "z/x/y → 文件偏移" 映射表
3. 用户缩放/平移 → 只 Range 请求当前视野需要的瓦片
```

### 5.2 Service Worker 缓存策略

**核心问题**：浏览器原生缓存不擅长处理 Range 请求（按 URL+请求头做 key，Range 请求被视为不同资源）。

**解决方案**：SW 把 `.pmtiles` 当作整体缓存，自己切分返回。

```javascript
// sw.js — 关键逻辑

const CACHE_NAME = 'citylog-map-v1';
const PMTILES_URL = '/data/shanghai.pmtiles';

// 安装时：预缓存整份 PMTiles
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.add(PMTILES_URL))
  );
  self.skipWaiting();
});

// 拦截所有 Range 请求，从缓存中切片返回
self.addEventListener('fetch', (e) => {
  if (e.request.url.includes('.pmtiles') && e.request.headers.has('range')) {
    e.respondWith(handleRange(e.request));
  }
});

async function handleRange(request) {
  const cache = await caches.open(CACHE_NAME);
  const response = await cache.match(PMTILES_URL);
  if (!response) return fetch(request); // 回退网络

  const blob = await response.blob();
  const range = request.headers.get('range'); // "bytes=1024-2048"
  const [start, end] = parseRange(range, blob.size);

  return new Response(blob.slice(start, end + 1), {
    status: 206,
    headers: {
      'Content-Range': `bytes ${start}-${end}/${blob.size}`,
      'Content-Length': String(end - start + 1),
      'Accept-Ranges': 'bytes'
    }
  });
}
```

### 5.3 城市级数据裁剪

```bash
# 从全球数据提取上海市区（约 50MB → 5~15MB）
pmtiles extract   https://build.protomaps.com/20260727.pmtiles   shanghai.pmtiles   --bbox=121.30,31.00,121.60,31.40

# 放到项目 public/data/ 目录，构建时自动包含
```

### 5.4 缓存策略选择

| 策略                       | 适用场景               | 配置                                 |
| -------------------------- | ---------------------- | ------------------------------------ |
| **Cache-First** ⭐         | 地图底图（变化不频繁） | 安装时预缓存，更新时改版本号         |
| **Network-First**          | 打卡数据同步           | 先读网络，失败 fallback 到 IndexedDB |
| **Stale-While-Revalidate** | 样式文件               | 立即返回缓存，后台静默更新           |

______________________________________________________________________

## 六、开发路线图

### Phase 1：地图底座（Week 1）

**目标**：能显示离线地图，能缩放平移。

- [ ] 搭建 Vite + Vanilla JS / Vue 3 项目骨架
- [ ] 集成 MapLibre GL JS
- [ ] 下载并裁剪目标城市的 PMTiles 文件
- [ ] 配置 MapLibre Style JSON（引用本地 PMTiles）
- [ ] 注册 Service Worker，实现 Range 请求缓存
- [ ] 验证：断网后刷新页面，地图仍能正常显示

**验收标准**：Chrome DevTools Network 面板勾选 Offline 后，地图正常渲染。

### Phase 2：打卡核心（Week 2）

**目标**：能在地图上添加、查看、删除打卡记录。

- [ ] 设计 IndexedDB 表结构（Dexie.js）
- [ ] 实现"长按地图添加打卡"交互
- [ ] 打卡表单：标题、笔记、标签、评分、照片上传
- [ ] 照片压缩 + 缩略图生成（Canvas resize）
- [ ] 地图标记渲染（自定义 DOM Marker，圆形照片缩略图）
- [ ] 点击标记弹出详情 Bottom Sheet
- [ ] 编辑 / 删除打卡

**验收标准**：完整走通"添加 → 查看 → 编辑 → 删除"闭环，数据持久化到 IndexedDB。

### Phase 3：时间线与视图（Week 3）

**目标**：时间线、网格视图、筛选、双向联动。

- [ ] 底部横向时间线组件（最近打卡倒序）
- [ ] 时间线 ↔ 地图标记 双向高亮联动
- [ ] 上滑展开全屏时间线（按月份分组）
- [ ] 网格视图（照片墙，按月份分组，瀑布流/网格布局）
- [ ] 地图视图 ↔ 网格视图 切换动画
- [ ] 筛选面板（标签过滤、时间范围过滤）
- [ ] 空状态设计（无打卡时的引导）

**验收标准**：三种视图切换流畅，筛选后地图标记和列表同步更新。

### Phase 4：打磨与 PWA（Week 4）

**目标**：离线可用、安装到桌面、性能优化。

- [ ] PWA 配置（manifest.json、图标、主题色）
- [ ] 离线页面（所有资源走 Service Worker）
- [ ] 照片懒加载（时间线/网格视图中，IntersectionObserver）
- [ ] 标记聚类（MapLibre MarkerCluster 或自定义）
- [ ] 深色模式适配
- [ ] 手势优化（地图与 Bottom Sheet 滑动不冲突）
- [ ] 性能审计：Lighthouse 评分 > 90

**验收标准**：手机浏览器"添加到主屏幕"后，断网能完整使用所有功能。

______________________________________________________________________

## 七、关键技术实现清单

### 7.1 MapLibre + PMTiles 接入

```javascript
import maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';

// 注册 PMTiles 协议
const protocol = new Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

const map = new maplibregl.Map({
  container: 'map',
  style: '/styles/city-style.json', // 引用 pmtiles:// 数据源
  center: [121.47, 31.23], // 上海
  zoom: 12,
  hash: true, // URL 同步坐标
});
```

### 7.2 自定义照片标记

```javascript
// 为每个打卡点创建 DOM 标记
const el = document.createElement('div');
el.className = 'map-pin';
el.style.backgroundImage = `url(${checkIn.photos[0].thumbnailUrl})`;

const marker = new maplibregl.Marker({ element: el })
  .setLngLat([checkIn.lng, checkIn.lat])
  .addTo(map);

marker.getElement().addEventListener('click', () => showDetail(checkIn));
```

### 7.3 照片压缩（上传时）

```javascript
async function compressImage(file, maxWidth = 1200) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const scale = maxWidth / img.width;
      canvas.width = maxWidth;
      canvas.height = img.height * scale;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(resolve, 'image/jpeg', 0.85);
    };
    img.src = URL.createObjectURL(file);
  });
}
```

### 7.4 IndexedDB 结构（Dexie.js）

```javascript
import Dexie from 'dexie';

const db = new Dexie('CityLogDB');

db.version(1).stores({
  checkIns: '++id, lat, lng, visitedAt, *tags', // 主键自增，索引坐标/时间/标签
  photos: 'id, checkInId',                        // 关联打卡记录
  settings: 'key'                                 // 用户配置
});
```

______________________________________________________________________

## 八、项目文件结构

```
city-log/
├── public/
│   ├── data/
│   │   └── shanghai.pmtiles          # 城市瓦片数据（构建时放入）
│   ├── styles/
│   │   └── city-style.json           # MapLibre 样式定义
│   ├── icons/                        # PWA 图标
│   └── manifest.json
├── src/
│   ├── components/
│   │   ├── MapView.vue               # 地图主视图
│   │   ├── Timeline.vue              # 底部时间线
│   │   ├── DetailSheet.vue           # 打卡详情弹窗
│   │   ├── PhotoGrid.vue             # 网格视图
│   │   ├── FilterPanel.vue           # 筛选面板
│   │   └── AddCheckIn.vue            # 添加打卡表单
│   ├── stores/
│   │   ├── mapStore.js               # 地图状态（中心、缩放、选中标记）
│   │   └── checkInStore.js           # 打卡数据（CRUD + 筛选）
│   ├── db/
│   │   └── index.js                  # Dexie 数据库初始化
│   ├── sw.js                         # Service Worker（Range 缓存核心）
│   ├── main.js                       # 入口
│   └── style.css                     # 全局样式
├── scripts/
│   └── extract-city.js               # 自动裁剪城市 PMTiles
├── vite.config.js
└── package.json
```

______________________________________________________________________

## 九、后续扩展方向

| 阶段     | 功能       | 技术点                                           |
| -------- | ---------- | ------------------------------------------------ |
| **v1.1** | 多城市切换 | 多个 PMTiles 文件动态加载/卸载                   |
| **v1.2** | 足迹动画   | 按时间顺序播放打卡轨迹（MapLibre 动画）          |
| **v1.3** | 数据导出   | GeoJSON / GPX 导出，可导入 Google Earth          |
| **v2.0** | 云同步     | 可选 WebDAV / S3 备份，端到端加密                |
| **v2.1** | 社交分享   | 生成打卡卡片图（html2canvas），分享至微信/小红书 |
| **v3.0** | 原生 App   | Capacitor / Tauri 打包，调用原生相机/定位        |

______________________________________________________________________

## 十、参考资源

- [PMTiles 官方文档](https://docs.protomaps.com/pmtiles/)
- [MapLibre GL JS 文档](https://maplibre.org/maplibre-gl-js/docs/)
- [Protomaps 样式指南](https://docs.protomaps.com/basemaps/)
- [Dexie.js IndexedDB 封装](https://dexie.org/)
- [Service Worker Range 请求处理](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests)

______________________________________________________________________

> **下一步行动**：从 Phase 1 开始，先搭建一个能显示离线 PMTiles 地图的 Vite 项目骨架。
