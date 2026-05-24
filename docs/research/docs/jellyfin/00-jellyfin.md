---
title: Jellyfin 源码阅读指南
tags:
  - research
  - tech
categories:
  - dev
---

> **⚠️ 免责声明**: 本文档由 AI 自动生成，仅供参考学习使用。
> - 依据 jellyfin 仓库: branch `master`

> **学习前先克隆项目:**
> ```bash
> cd docs/research/external
> git clone --depth 1 https://github.com/jellyfin/jellyfin.git
> ```

---

## 项目概述

Jellyfin 是一个用 C# (.NET) 编写的开源媒体服务器，是 Emby 的一个 fork。它可以让你收集、管理和流式传输你的媒体文件。

- GitHub: https://github.com/jellyfin/jellyfin
- 本地路径: `docs/research/external/jellyfin`

## 项目结构

```
jellyfin/
├── Jellyfin.Server/                   # 入口点，Web 主机 (ASP.NET Core)
│   ├── Program.cs                    # Main() 入口
│   ├── CoreAppHost.cs               # 应用主机实现
│   ├── Startup.cs                   # ASP.NET Core 启动配置
│   └── Migrations/                  # 数据库迁移
├── Jellyfin.Api/                    # REST API 层 (60+ 控制器)
│   ├── Controllers/                 # API 控制器
│   ├── Auth/                        # 认证中间件
│   ├── Middleware/                  # 中间件
│   └── WebSocketListeners/          # WebSocket 支持
├── Jellyfin.Data/                   # 数据访问层 (Entity Framework)
├── Jellyfin.Server.Implementations/ # 服务端实现
├── MediaBrowser.Controller/         # 核心接口/抽象层
├── MediaBrowser.Model/              # 数据模型和 DTO
├── MediaBrowser.Common/             # 公共类型和接口
├── MediaBrowser.Providers/          # 元数据提供者 (IMDB, TMDB, TVDB 等)
├── MediaBrowser.MediaEncoding/      # 媒体编码 (FFmpeg 集成)
├── MediaBrowser.LocalMetadata/      # 本地元数据解析
├── MediaBrowser.XbmcMetadata/       # XBMC/Kodi 格式元数据
├── Emby.Server.Implementations/     # 核心实现 (实际逻辑)
│   ├── ApplicationHost.cs          # 应用主机核心 (DI, 插件, 生命周期)
│   ├── Library/                    # 媒体库管理
│   ├── Session/                    # 会话管理
│   ├── Plugins/                    # 插件系统
│   ├── HttpServer/                 # HTTP 服务
│   ├── IO/                         # 文件 I/O
│   └── Updates/                    # 自动更新
├── Emby.Naming/                     # 文件命名解析
├── Emby.Photos/                     # 照片处理
└── tests/                           # 测试项目
```

## 学习阶段

### 阶段 1: 理解架构分层

Jellyfin 采用**接口-实现分离**的分层架构:

```
┌─────────────────────────────────────────┐
│          Jellyfin.Api (REST API)        │  ← 表现层
├─────────────────────────────────────────┤
│       MediaBrowser.Controller           │  ← 接口/抽象层
├─────────────────────────────────────────┤
│   Emby.Server.Implementations           │  ← 核心实现层
├─────────────────────────────────────────┤
│ Jellyfin.Data / MediaBrowser.Model      │  ← 数据层
└─────────────────────────────────────────┘
```

1. **理解入口点**
   - 阅读 `docs/research/external/jellyfin/Jellyfin.Server/Program.cs` — 了解启动流程
   - 阅读 `docs/research/external/jellyfin/Jellyfin.Server/CoreAppHost.cs` — 应用主机
   - 阅读 `docs/research/external/jellyfin/Jellyfin.Server/Startup.cs` — ASP.NET Core 配置

### 阶段 2: 理解核心机制

2. **应用主机 (ApplicationHost)**
   - `docs/research/external/jellyfin/Emby.Server.Implementations/ApplicationHost.cs` — 核心生命周期管理
   - 了解 DI 容器注册流程
   - 了解插件加载机制

3. **依赖注入**
   - `docs/research/external/jellyfin/Emby.Server.Implementations/ApplicationHost.cs` 中的 `RegisterServices()` 方法
   - 使用 ASP.NET Core 内置 DI (`Microsoft.Extensions.DependencyInjection`)

4. **插件系统**
   - `docs/research/external/jellyfin/MediaBrowser.Common.Plugins.IPlugin` — 插件接口
   - `docs/research/external/jellyfin/Emby.Server.Implementations/Plugins/` — 插件加载和发现
   - `docs/research/external/jellyfin/MediaBrowser.Common.Plugins.BasePlugin` — 插件基类

### 阶段 3: 理解核心业务

5. **媒体库系统**
   - `docs/research/external/jellyfin/Emby.Server.Implementations/Library/` — 媒体库扫描和管理
   - `docs/research/external/jellyfin/MediaBrowser.Controller.Entities/` — 媒体实体 (Movie, Series, Episode 等)

6. **API 层**
   - `docs/research/external/jellyfin/Jellyfin.Api/Controllers/ItemsController.cs` — 媒体项 API
   - `docs/research/external/jellyfin/Jellyfin.Api/Controllers/UserController.cs` — 用户管理
   - `docs/research/external/jellyfin/Jellyfin.Api/Controllers/VideosController.cs` — 视频流

7. **元数据提供者**
   - `docs/research/external/jellyfin/MediaBrowser.Providers/` — 从 TMDB, IMDB 等获取元数据
   - `docs/research/external/jellyfin/MediaBrowser.LocalMetadata/` — 从本地文件 (NFO) 解析元数据

### 阶段 4: 深入功能

8. **媒体编码和流媒体**
   - `docs/research/external/jellyfin/MediaBrowser.MediaEncoding/` — FFmpeg 集成
   - `docs/research/external/jellyfin/Jellyfin.Api/Controllers/DynamicHlsController.cs` — HLS 流

9. **会话和播放状态**
   - `docs/research/external/jellyfin/Emby.Server.Implementations/Session/` — 会话管理
   - `docs/research/external/jellyfin/Jellyfin.Api/Controllers/PlaystateController.cs` — 播放状态上报

## 关键概念

| 概念 | 说明 |
|------|------|
| **ApplicationHost** | 应用主机，管理 DI、插件、生命周期 |
| **IPlugin** | 插件接口，所有功能模块都通过插件集成 |
| **BaseItem** | 媒体实体基类 (Movie, Series, Episode 等) |
| **Resolver** | 媒体文件识别器，从文件名/目录结构确定媒体类型 |
| **Provider** | 元数据提供者，从外部获取/本地解析媒体信息 |
| **DLNA** | 数字生活网络联盟协议，流媒体发现和播放 |
| **HLS** | HTTP Live Streaming，动态转码和分段传输 |
| **Trickplay** | 视频缩略图预览条 |
| **SyncPlay** | 多人同步播放 |

## 核心流程图

### 启动流程

```
Program.Main()
    ↓
StartApp()
    ↓
SetupServer.RunAsync()    → 初始化网络、数据库
    ↓
ApplyStartupMigrationAsync() → 数据库迁移
    ↓
StartServer()
    ↓
new CoreAppHost()         → 创建应用主机
    ↓
appHost.Init()            → 注册 DI、加载插件、初始化服务
    ↓
WebHostBuilder.Run()      → 启动 ASP.NET Core
```

### 媒体扫描流程

```
媒体文件夹扫描
    ↓
Resolver 识别文件 (从文件名/目录结构)
    ↓
Provider 获取元数据 (TMDB/IMDB/NFO)
    ↓
创建/更新 BaseItem 实体
    ↓
存入数据库 (SQLite/PostgreSQL)
    ↓
用户可以通过 API 访问
```

### 视频播放流程

Jellyfin 使用 **HLS (HTTP Live Streaming)** 协议向浏览器传输视频。

#### 整体架构

```
浏览器请求视频
    ↓
GET /Videos/{itemId}/{master|main}.m3u8
    ↓
StreamingHelpers.GetStreamingState() → 决定 Direct Play / Remux / Transcode
    ↓
需要转码? → transcodeManager.StartFfMpeg() → FFmpeg 转码 → HLS 分段输出
不需要   → 直接返回原始文件
    ↓
返回 .m3u8 playlist 给浏览器
    ↓
浏览器逐段请求 .ts/.mp4 片段
```

#### 三种播放模式

| 模式 | 说明 | 触发条件 |
|------|------|----------|
| **Direct Play** | 原文件直接输出 | 浏览器支持原始编码格式 |
| **Direct Stream** | 重新封装容器，不重新编码 | 编码兼容但容器不兼容 |
| **Transcode** | FFmpeg 实时转码 | 编码/分辨率/码率不兼容 |

#### 核心端点

| Endpoint | 用途 |
|----------|------|
| `GET /Videos/{id}/master.m3u8` | 自适应码率主播放列表 (多码率) |
| `GET /Videos/{id}/main.m3u8` | 单一码率播放列表 |
| `GET /Videos/{id}/live.m3u8` | Live 模式播放列表 (低延迟) |
| `GET /Audio/{id}/universal` | 音频通用播放 |
| `GET /Videos/{id}/hls1/{segId}` | HLS 分段数据 (.ts/.mp4) |

#### 详细播放流程

```
1. 浏览器请求: GET /Videos/abc123/master.m3u8
        ↓
2. DynamicHlsHelper.GetMasterHlsPlaylist()
   - 解析设备能力 (User-Agent, codec 支持)
   - 创建 StreamState
   - 决定编码参数 (分辨率/码率/编码器)
        ↓
3. 返回主播放列表 (master.m3u8):
   #EXTM3U
   #EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
   main.m3u8?videoCodec=h264,h265&audioCodec=aac,ac3
        ↓
4. 浏览器请求: GET /Videos/abc123/main.m3u8?videoCodec=h264
        ↓
5. StreamingHelpers.GetStreamingState()
   - 找到原始媒体文件 (MediaSource)
   - 比较原始编码 vs 请求编码
   - 决定是否需要启动 FFmpeg
        ↓
6a. 不需要转码 (Direct Play):
    返回静态播放列表，指向原始文件

6b. 需要转码 (Transcode):
    transcodeManager.StartFfMpeg() 生成 FFmpeg 命令:
    ffmpeg -i input.mkv -map 0:v -map 0:a \
      -c:v libx264 -preset veryfast -b:v 5000k \
      -c:a aac -b:a 128k \
      -f hls -hls_time 3 -hls_segment_type mpegts \
      -hls_playlist_type event \
      output%d.ts output.m3u8
        ↓
7. 返回变体播放列表 (main.m3u8):
   #EXTINF:3.000,
   hls/output0.ts
   #EXTINF:3.000,
   hls/output1.ts
   ...
        ↓
8. 浏览器逐段请求:
   GET /Videos/abc123/hls1/0.ts
   GET /Videos/abc123/hls1/1.ts
   GET /Videos/abc123/hls1/2.ts
   ...
```

#### FFmpeg 命令生成

关键代码: `Jellyfin.Api/Controllers/DynamicHlsController.cs:1574-1651`

```csharp
private string GetCommandLineArguments(outputPath, state, isEventPlaylist, startNumber)
{
    var videoCodec = _encodingHelper.GetVideoEncoder(state, _encodingOptions);
    var threads = EncodingHelper.GetNumberOfThreads(state, ...);

    // 分段格式选择: mpegts (.ts) 或 fmp4 (.mp4)
    if (segmentContainer == "ts")   → "mpegts"
    if (segmentContainer == "mp4")  → "fmp4"

    // 生成完整 FFmpeg 命令
    return $"{inputModifier} {inputArg} -threads {threads} {mapArgs}
             {videoArgs} {audioArgs}
             -f hls -hls_time {segmentLength}
             -hls_segment_type {segmentFormat}
             -hls_playlist_type {vod|event}
             output%d{ext} output.m3u8";
}
```

#### 自适应码率 (ABR)

当客户端请求 master playlist 时，Jellyfin 生成多个码率变体:

```
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=854x480
main.m3u8?videoBitRate=2000000&maxWidth=854

#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1280x720
main.m3u8?videoBitRate=5000000&maxWidth=1280

#EXT-X-STREAM-INF:BANDWIDTH=8000000,RESOLUTION=1920x1080
main.m3u8?videoBitRate=8000000&maxWidth=1920
```

浏览器根据网络状况自动切换码率。

#### 浏览器兼容性

| 编码格式 | Chrome | Firefox | Safari | Edge |
|----------|--------|---------|--------|------|
| H.264 + AAC + .ts | ✅ | ✅ | ✅ | ✅ |
| H.265 + fMP4 | ❌ | ❌ | ✅ | 部分 |
| VP9 | ✅ | ✅ | ❌ | ✅ |
| AV1 | ✅ | ✅ | ❌ | ✅ |

Jellyfin 通过设备配置文件自动选择浏览器支持的编码格式，不兼容时自动启动 FFmpeg 转码。

## Rust 最小播放原型

### 核心思路

最简单的方案：**不转码，只做 Direct Play** — 先把视频预转成 HLS 格式，用 Rust HTTP 服务提供 `.m3u8` 和 `.ts` 文件。

### 第一步：准备 HLS 视频

用 FFmpeg 把视频预转成 HLS 格式：

```bash
ffmpeg -i input.mp4 \
  -c:v libx264 -preset veryfast -b:v 3000k \
  -c:a aac -b:a 128k \
  -f hls -hls_time 5 -hls_segment_type mpegts \
  -hls_playlist_type vod \
  output/playlist.m3u8
```

生成的文件：

```
output/
├── playlist.m3u8     # 播放列表
├── playlist0.ts      # 分段 0
├── playlist1.ts      # 分段 1
└── playlist2.ts      # 分段 2
```

### 第二步：最小 Rust HTTP 服务

**Cargo.toml**

```toml
[package]
name = "mini-streamer"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.7"
tokio = { version = "1", features = ["full"] }
tower-http = { version = "0.5", features = ["fs", "cors"] }
```

**src/main.rs**

```rust
use axum::{Router, routing::get, response::IntoResponse, http::header};
use tower_http::{services::ServeDir, cors::CorsLayer};

async fn playlist() -> impl IntoResponse {
    let content = tokio::fs::read_to_string("output/playlist.m3u8")
        .await
        .unwrap();
    (
        [(header::CONTENT_TYPE, "application/vnd.apple.mpegurl")],
        content,
    )
}

async fn segment(
    axum::extract::Path(seg): axum::extract::Path<String>,
) -> impl IntoResponse {
    let path = format!("output/{}", seg);
    let content = tokio::fs::read(&path).await.unwrap();
    (
        [(header::CONTENT_TYPE, "video/mp2t")],
        content,
    )
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/playlist.m3u8", get(playlist))
        .route("/{seg}", get(segment))
        .layer(CorsLayer::permissive());

    println!("Server running at http://localhost:3000");
    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
```

### 第三步：浏览器测试

```html
<!DOCTYPE html>
<html>
<head><title>Mini Streamer</title></head>
<body>
  <video controls width="800">
    <source src="http://localhost:3000/playlist.m3u8"
      type="application/vnd.apple.mpegurl">
  </video>
  <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
  <script>
    if (Hls.isSupported()) {
      var video = document.querySelector("video");
      var hls = new Hls();
      hls.loadSource("http://localhost:3000/playlist.m3u8");
      hls.attachMedia(video);
    }
  </script>
</body>
</html>
```

> 注意：Chrome/Firefox 不原生支持 HLS，需要 `hls.js` 库。

### 进阶：集成 FFmpeg 实时转码

```rust
use std::process::Command;

fn start_transcode(input_path: &str, output_dir: &str) {
    std::fs::create_dir_all(output_dir).unwrap();

    let output = Command::new("ffmpeg")
        .args([
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", "3000k",
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "hls",
            "-hls_time", "5",
            "-hls_segment_type", "mpegts",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename",
            &format!("{}/segment%d.ts", output_dir),
            &format!("{}/playlist.m3u8", output_dir),
        ])
        .spawn()
        .expect("Failed to start ffmpeg");

    output.wait_with_output().unwrap();
}
```

### 与 Jellyfin 的架构对比

| 维度 | Jellyfin | 最小原型 |
|------|----------|----------|
| 浏览器请求 | REST API Controller | Axum route handler |
| 播放列表生成 | DynamicHlsHelper | 预生成 .m3u8 |
| 分段管理 | transcodeManager | FFmpeg 输出到磁盘 |
| 转码 | FFmpeg 子进程 | FFmpeg 子进程 |
| 设备兼容检测 | DLNA Profile | 跳过 (假设 H.264) |
| 认证 | JWT / API Key | 跳过 |

### 关键注意事项

- **hls.js** — Chrome/Firefox 不原生支持 HLS，必须用此 JS 库
- **CORS** — 后端必须设置 `Access-Control-Allow-Origin`，否则浏览器阻止
- **Content-Type** — `.m3u8` 用 `application/vnd.apple.mpegurl`，`.ts` 用 `video/mp2t`
- **FFmpeg** — 需要安装在系统 PATH 中

## 关键文件

| 文件 | 说明 |
|------|------|
| `Jellyfin.Server/Program.cs` | 程序入口 |
| `Jellyfin.Server/CoreAppHost.cs` | 应用主机 |
| `Emby.Server.Implementations/ApplicationHost.cs` | 核心 DI/插件/生命周期 |
| `Jellyfin.Api/Controllers/ItemsController.cs` | 媒体项 API |
| `Jellyfin.Api/Controllers/VideosController.cs` | 视频流 API |
| `Jellyfin.Api/Controllers/UserController.cs` | 用户管理 API |
| `Emby.Server.Implementations/Library/` | 媒体库管理 |
| `Emby.Server.Implementations/Session/` | 会话管理 |
| `MediaBrowser.Controller/Entities/` | 媒体实体模型 |
| `MediaBrowser.Controller/Plugins/` | 插件接口定义 |
| `MediaBrowser.Providers/` | 元数据提供者 |
| `MediaBrowser.MediaEncoding/` | FFmpeg 编码集成 |
| `MediaBrowser.Model/` | 数据模型和 DTO |

## 技术栈

| 技术 | 用途 |
|------|------|
| **ASP.NET Core** | Web 框架 |
| **Entity Framework Core** | ORM (SQLite/PostgreSQL) |
| **FFmpeg** | 媒体转码和编码 |
| **SkiaSharp** | 图片处理 (缩略图生成) |
| **Serilog** | 日志框架 |
| **CommandLine** | CLI 参数解析 |
