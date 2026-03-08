# Lux 学习计划

## 项目概述

Lux 是一个用 Go 编写的快速、简单的视频下载器，支持从多个视频网站下载视频和音频。

- GitHub: https://github.com/iawia002/lux
- 本地路径: `docs/research/external/lux`

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
   - `cd docs/research/external/lux`
   - `go run . --help` 查看帮助

2. **理解程序入口**
   - 阅读 [main.go](docs/research/external/lux/main.go)
   - 阅读 [app/app.go](docs/research/external/lux/app/app.go) 了解 CLI 结构

### 阶段 2: 核心模块

3. **下载器模块** (`downloader/`)
   - [downloader.go](docs/research/external/lux/downloader/downloader.go) - 下载核心逻辑
   - [types.go](docs/research/external/lux/downloader/types.go) - 数据结构

4. **提取器模块** (`extractors/`)
   - [extractors.go](docs/research/external/lux/extractors/extractors.go) - 提取器接口
   - [types.go](docs/research/external/lux/extractors/types.go) - 数据类型定义

5. **网络请求** (`request/`)
   - 了解如何封装 HTTP 请求
   - 处理 cookie、proxy 等

### 阶段 3: 深入理解

6. **学习一个具体提取器**
   - 推荐从简单的开始: `extractors/youtube/` 或 `extractors/bilibili/`
   - 理解如何解析视频 URL
   - 理解如何提取视频流信息

7. **理解 URL 解析** (`parser/`)
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

## 参考资源

- [README.md](docs/research/external/lux/README.md) - 项目文档
- [CONTRIBUTING.md](docs/research/external/lux/CONTRIBUTING.md) - 贡献指南
