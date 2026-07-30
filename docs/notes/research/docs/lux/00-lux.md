---
title: Lux 资料整理
tags:
  - research
  - tech
categories:
  - dev
---

# Lux 资料整理

> ⚠️ **本文档由 AI 自动整理**
>
> - 依据 lux 仓库: branch `master` (`dd00f6d`)

> **学习前先克隆项目:**
>
> ```bash
> cd docs/notes/research/external
> git clone --depth 1 https://github.com/iawia002/lux.git
> ```

______________________________________________________________________

## 项目概述

Lux 是一个用 Go 编写的快速、简单的视频下载器，支持从多个视频网站下载视频和音频。

- GitHub: https://github.com/iawia002/lux
- 本地路径: `docs/notes/research/external/lux`

## 项目结构

```
lux/
├── main.go           # 程序入口
├── app/              # CLI 应用逻辑 (使用 urfave/cli)
├── config/           # 配置相关
├── downloader/       # 下载器核心
├── extractors/        # 视频网站提取器 (支持 40+ 网站)
├── parser/           # URL 解析器
├── request/          # HTTP 网络请求封装
├── utils/            # 工具函数
└── test/             # 测试文件
```

## 学习阶段

### 阶段 1: 基础入门

1. **运行项目**

   - 安装 Go 1.21+
   - `cd docs/notes/research/external/lux`
   - `go run . --help` 查看帮助

1. **理解程序入口**

   - 阅读 `docs/notes/research/external/lux/main.go`
   - 阅读 `docs/notes/research/external/lux/app/app.go` 了解 CLI 结构

### 阶段 2: 核心模块

> 建议学习顺序: **request → extractors → downloader** (由底层到上层)

3. **网络请求** (`request/`)

   - 了解如何封装 HTTP 请求
   - 处理 cookie、proxy 等

1. **提取器模块** (`extractors/`)

   - `docs/notes/research/external/lux/extractors/extractors.go` - 提取器接口
   - `docs/notes/research/external/lux/extractors/types.go` - 数据类型定义

1. **下载器模块** (`downloader/`)

   - `docs/notes/research/external/lux/downloader/downloader.go` - 下载核心逻辑
   - `docs/notes/research/external/lux/downloader/types.go` - 数据结构

### 阶段 3: 深入理解

6. **学习一个具体提取器**

   - 推荐从简单的开始: `extractors/youtube/` 或 `extractors/bilibili/`
   - 理解如何解析视频 URL
   - 理解如何提取视频流信息

1. **理解 URL 解析** (`parser/`)

   - 如何识别不同的网站
   - 如何路由到正确的提取器

### 阶段 4: 实践

8. **尝试修改**
   - 添加一个新的网站支持
   - 修改下载逻辑
   - 添加单元测试

## 关键概念

- **Extractor**: 提取器接口，每个网站一个实现
- **Stream**: 视频流 (如 720P, 1080P)
- **Part**: 视频分段 (有些视频需要分段下载后合并)
- **Data**: 提取的完整数据 (包含多个 Stream)
- **Mux**: 音视频合并 (使用 ffmpeg)

## 第三方库

| 库                                   | 用途                                 |
| ------------------------------------ | ------------------------------------ |
| **urfave/cli/v2**                    | CLI 框架，构建命令行应用             |
| **gocolly/colly/v2**                 | 网页爬虫框架，用于抓取网页内容       |
| **PuerkitoBio/goquery**              | HTML 解析库，类似 jQuery 的 DOM 操作 |
| **kkdai/youtube/v2**                 | YouTube 专用提取器                   |
| **dop251/goja**                      | JavaScript 引擎，用于执行 JS 代码    |
| **robertkrimen/otto**                | 另一个 JavaScript 引擎               |
| **fatih/color**                      | 彩色终端输出                         |
| **cheggaaa/pb/v3**                   | 终端进度条                           |
| **buger/jsonparser**                 | 高性能 JSON 解析                     |
| **json-iterator/go**                 | 高性能 JSON 序列化/反序列化          |
| **itchyny/gojq**                     | jq 风格的 JSON 查询                  |
| **EDDYCJY/fake-useragent**           | 随机 User-Agent 生成                 |
| **MercuryEngineering/CookieMonster** | Cookie 管理                          |
| **kr/pretty**                        | 格式化输出 (用于调试)                |
| **pkg/errors**                       | 错误处理增强                         |

## 本地实验

- [go-cli-urfave 实验代码](https://github.com/xiongjia/xiongjia.github.com/tree/master/docs/notes/research/experiments/go-cli-urfave/main.go){:target="\_blank"} - Lux 使用 urfave/cli 框架的实验项目

## 参考资源

- `docs/notes/research/external/lux/README.md` - 项目文档
- `docs/notes/research/external/lux/CONTRIBUTING.md` - 贡献指南

______________________________________________________________________

# Downloader 模块流程分析

本文档分析 lux 项目中 downloader 包的主要下载流程。

## 1. 核心数据结构

### Downloader 结构体

```go
type Downloader struct {
    Bar    *pb.ProgressBar  // 进度条
    option Options         // 下载选项
}
```

### Options 配置项

| 字段            | 说明                 |
| --------------- | -------------------- |
| `InfoOnly`      | 仅显示信息，不下载   |
| `Silent`        | 静默模式，不输出信息 |
| `Stream`        | 指定要下载的流类型   |
| `AudioOnly`     | 仅下载音频           |
| `MultiThread`   | 是否启用多线程下载   |
| `ThreadNumber`  | 线程数量             |
| `ChunkSizeMB`   | 分块大小（MB）       |
| `UseAria2RPC`   | 使用 Aria2 RPC 下载  |
| `EmbedSubtitle` | 内嵌字幕到视频       |

______________________________________________________________________

## 2. 主要下载流程

### 入口方法: `Download()`

```
┌─────────────────────────────────────────────────────────────┐
│                      Download(data)                         │
├─────────────────────────────────────────────────────────────┤
│  1. 验证 streams 不为空                                     │
│  2. 按 Size 排序所有 streams                                │
│  3. 如果 InfoOnly: 打印信息后返回                            │
│  4. 获取输出文件名 (title)                                   │
│  5. 选择要下载的 stream                                      │
│  6. 下载字幕 (Caption)                                      │
│  7. 检查是否使用 Aria2 RPC                                  │
│  8. 检查文件是否已存在                                       │
│  9. 初始化进度条                                            │
│ 10. 下载视频/音频                                           │
│ 11. 合并分片 (如果有多个 parts)                              │
│ 12. 内嵌字幕 (如果启用)                                     │
└─────────────────────────────────────────────────────────────┘
```

### 单文件 vs 多分片下载

#### 单文件流程 (len(stream.Parts) == 1)

```
┌─────────────────────────────────────┐
│           单文件下载                  │
├─────────────────────────────────────┤
│ if MultiThread:                     │
│     multiThreadSave()               │
│ else:                               │
│     save()                          │
└─────────────────────────────────────┘
```

#### 多分片流程 (len(stream.Parts) > 1)

```
┌─────────────────────────────────────────────┐
│              多分片下载                       │
├─────────────────────────────────────────────┤
│  1. 使用 WaitGroupPool 并行下载各分片         │
│  2. 每个分片调用 save() 或 multiThreadSave() │
│  3. 等待所有分片下载完成                       │
│  4. 合并所有分片为完整文件                      │
│  5. 内嵌字幕 (可选)                           │
└─────────────────────────────────────────────┘
```

______________________________________________________________________

## 3. 核心下载方法

### 3.1 `save()` - 单线程下载

```go
func (downloader *Downloader) save(part *extractors.Part, refer, fileName string) error
```

**流程:**

```
┌─────────────────────────────────────────────────────────┐
│                      save()                             │
├─────────────────────────────────────────────────────────┤
│  1. 生成最终文件路径                                      │
│  2. 检查文件是否已完整下载 (跳过)                          │
│  3. 创建临时文件 (xxx.download)                           │
│  4. 检查临时文件是否已存在 (断点续传)                       │
│  5. 设置 HTTP Headers (Referer, Range)                   │
│  6. 下载数据到临时文件                                    │
│     - 如果 ChunkSizeMB > 0: 分块下载                       │
│     - 否则: 单次下载                                      │
│  7. 支持重试 (RetryTimes)                                │
│  8. 关闭文件并重命名为最终文件名                           │
└─────────────────────────────────────────────────────────┘
```

**断点续传支持:**

- 下载前检查 `xxx.download` 临时文件是否存在
- 如果存在，读取已下载大小，设置 `Range: bytes={size}-` 头部
- 从断点位置继续下载

### 3.2 `multiThreadSave()` - 多线程下载

```go
func (downloader *Downloader) multiThreadSave(dataPart *extractors.Part, refer, fileName string) error
```

**流程:**

```
┌─────────────────────────────────────────────────────────────┐
│                  multiThreadSave()                         │
├─────────────────────────────────────────────────────────────┤
│  1. 检查最终文件和临时文件是否存在                           │
│  2. 扫描已有的分片文件 (.part0, .part1, ...)               │
│  3. 分析已下载状态:                                         │
│     - 找出已完成的分片                                      │
│     - 找出未完成的分片                                      │
│     - 计算已下载总大小                                      │
│  4. 如果已下载大小 == 总大小: 合并并返回                     │
│  5. 使用 WaitGroupPool 并行下载未完成的分片                 │
│  6. 每个分片独立下载，支持断点续传                          │
│  7. 合并所有分片                                            │
└─────────────────────────────────────────────────────────────┘
```

**分片文件结构:**

- 每个分片存储为 `xxx.part{index}` 文件
- 文件头包含 `FilePartMeta` 元数据 (Index, Start, End, Cur)
- 实际数据从元数据之后开始

### 3.3 `writeFile()` - HTTP 写入文件

```go
func (downloader *Downloader) writeFile(url string, file *os.File, headers map[string]string) (int64, error)
```

- 发起 HTTP GET 请求
- 使用 progress bar 包装 writer 追踪进度
- 返回写入的字节数

______________________________________________________________________

## 4. 字幕下载

```go
func (downloader *Downloader) caption(url, fileName, ext string, transform func([]byte) ([]byte, error)) error
```

- 下载字幕/弹幕文件
- 支持格式转换 (如 XML -> SRT)
- 如果启用 `EmbedSubtitle`: 内嵌到视频中

______________________________________________________________________

## 5. Aria2 RPC 支持

```go
func (downloader *Downloader) aria2(title string, stream *extractors.Stream) error
```

- 通过 Aria2 JSON-RPC 接口添加下载任务
- 支持分片并行下载
- 需要配置 `Aria2Token`, `Aria2Method`, `Aria2Addr`

______________________________________________________________________

## 6. 文件合并 (FFmpeg)

当视频有多个分片时，需要调用 `utils` 包的 ffmpeg 函数合并:

```go
// 通用合并 (支持音视频合并)
// 使用 ffmpeg: -c:v copy -c:a copy
utils.MergeFilesWithSameExtension(parts, mergedFilePath)

// MP4 合并 (使用 concat demuxer)
// 使用 ffmpeg concat 模式，自动处理 aac_adtstoasc bitstream filter
utils.MergeToMP4(parts, mergedFilePath, title)

// 内嵌字幕到视频
// 根据容器格式选择字幕 codec (mp4 -> mov_text, webm -> webvtt)
utils.EmbedSubtitles(mergedFilePath, subtitlePaths, subtitleLangs)
```

**FFmpeg 相关函数位于 `utils/ffmpeg.go`:**

| 函数                            | 用途                                   |
| ------------------------------- | -------------------------------------- |
| `MergeFilesWithSameExtension()` | 合并相同扩展名文件，音视频合成         |
| `MergeToMP4()`                  | 合并 MP4 分片，添加 aac_adtstoasc 滤镜 |
| `EmbedSubtitles()`              | 内嵌字幕到视频容器                     |

______________________________________________________________________

## 7. 关键文件

| 文件                                            | 说明             |
| ----------------------------------------------- | ---------------- |
| `../external/lux/downloader/downloader.go`      | 主下载逻辑       |
| `../external/lux/downloader/types.go`           | 类型定义         |
| `../external/lux/downloader/utils.go`           | 辅助函数         |
| `../external/lux/downloader/downloader_test.go` | 测试用例         |
| `../external/lux/utils/ffmpeg.go`               | FFmpeg 合并/转码 |

______________________________________________________________________

## 8. 流程图

```
用户调用 Download()
       │
       ▼
┌──────────────────┐
│  检查 InfoOnly   │
└────────┬─────────┘
         │ 是
         ▼
┌──────────────────┐
│   打印视频信息    │
└────────┬─────────┘
         │ 否
         ▼
┌──────────────────┐
│  下载字幕文件    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 检查 Aria2 RPC   │
└────────┬─────────┘
         │ 是
         ▼
┌──────────────────┐
│  调用 aria2()    │
└────────┬─────────┘
         │ 否
         ▼
┌──────────────────┐
│ 检查文件已存在   │
└────────┬─────────┘
         │ 是
         ▼
┌──────────────────┐
│    跳过下载      │
└────────┬─────────┘
         │ 否
         ▼
┌──────────────────┐
│ 初始化进度条     │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
  单文件    多分片
    │         │
    ▼         ▼
┌────────┐  ┌────────────────┐
│ save() │  │ 并行下载各分片 │
│ 或     │  │   (WaitGroup)  │
│multi   │  └────────┬───────┘
│Thread  │           │
│Save()  │           ▼
└────────┘  ┌────────────────┐
            │  合并分片文件   │
            └────────┬───────┘
                     │
                     ▼
            ┌────────────────┐
            │  内嵌字幕(可选) │
            └────────────────┘
```
