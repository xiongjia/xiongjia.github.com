---
icon: material/flask
hide:
  - navigation
  - tags
  - toc
---

# :material-flask: Projects

从收集知识到深入研究再到动手的练习记录。

## Overview

| Project                         | Status         | Category           |
| ------------------------------- | -------------- | ------------------ |
| [seedling](#seedling)           | 🟢 Active      | Frontend & UI      |
| [vine](#vine)                   | 🟡 Maintenance | Frontend & UI      |
| [playground](#playground)       | 🟢 Active      | Automation Toolkit |
| [mung](#mung)                   | 🟢 Active      | AI & Skills        |
| [Running Otaku](#running-otaku) | 📦 Archived    | Health & Sports    |

状态：🟢 Active（活跃开发）· 🟡 Maintenance（维护模式，仅小修小补）· 📦 Archived（归档）

______________________________________________________________________

## Frontend & UI

### seedling

React 写的 Dashboard Demo UI，支持多语言、多皮肤模式，用来整理日常开发的组件原型。

- :simple-github: [Source](https://github.com/xiongjia/seedling)
- :material-web: [Demo](https://xiongjia.github.io/seedling/)
- :material-file-document: [Docs](https://xiongjia.github.io/seedling/docs/)

**Pipeline**: Collection(frontend) → Research(shadcn/ui CLI) → Project

### vine

完全静态的地图方案（零后端）：可复用的 MapView 组件（React + 原生 HTML widget）、pmtiles 区域管理 CLI、演示站点与组件 playground，可部署到 GitHub Pages / S3 / R2 等任意静态托管。

- :simple-github: [Source](https://github.com/xiongjia/vine)
- :material-web: [Demo](https://xiongjia.github.io/vine/)

**Pipeline**: Collection(map visualization) → React + MapLibre GL → Project

______________________________________________________________________

## Automation Toolkit

### playground

个人自动化工具集：加密增量备份（restic）、yt-dlp 视频下载与管理、通知 CLI、beancount 记账查账、Markdown 导出（PDF/EPUB/DOCX）、桌面自动化（防睡眠/点击器）等模块。

- :simple-github: [Source](https://github.com/xiongjia/playground)

**Pipeline**: Collection(automation/backup/media/finance) → Rust CLI → Project

______________________________________________________________________

## AI & Skills

### mung

个人 AI Skills 管理器——在 Claude Code 和 Pi Agent 之间创建、管理和分发 AI agent skill。

- :simple-github: [Source](https://github.com/xiongjia/mung)

**Pipeline**: Collection(AI agent workflow) → TypeScript CLI → Project

______________________________________________________________________

## Health & Sports

### Running Otaku

![Running Otaku](../assets/running-otaku.webp) 用来同步展示自己 Garmin 手表的跑步数据。
基于 [@yihong0618](https://github.com/yihong0618) 的 [Running Page](https://github.com/yihong0618/running_page)。

- :simple-github: [Source](https://github.com/xiongjia/running_page)
- :material-web: [Demo](https://xiongjia.github.io/running_page/)
