---
title: 阅读计划（定期维护清单）
created: 2026-08-05
tags: [reading, learning]
---

# 阅读计划（定期维护清单）

## Goal

一个长期维护的阅读清单：定期往 Tasks 里添加阅读/学习任务，完成后勾选。
涵盖项目源码理解、书籍/课程阅读、技术文章精读等。完成后可随时新增任务。

## Tasks

- [ ] **理解 CloudFlare-ImgBed**（https://github.com/isMixKu/CloudFlare-ImgBed）

  - 自托管图床/文件托管方案：Docker 与 serverless（Cloudflare Workers）两种部署形态
  - 多存储后端：Telegram、Discord、Cloudflare R2、S3 兼容存储、Hugging Face、WebDAV
  - 功能面：文件管理、认证、目录组织、内容审核、RESTful API、WebDAV
  - 阅读官方文档/README（中文版），弄清架构与部署方式
  - 可选动手：本地 Docker 起一个实例试用

- [ ] **阅读 Python for GIS: Spatial Intelligence**（https://pythonclcoding.gumroad.com/l/Python-For-GIS-Spatial-Intelligence）

  - PythonCLcoding 出品的 Python GIS 课程/电子书（Gumroad）
  - 目标：掌握用 Python 做空间数据分析的基本流程（geopandas / shapely / rasterio 等）
  - 阅读笔记（中文）可发布到 `docs/notes/research/topics/gis/`

- [ ] **理解本站 Mermaid 逐级加载兜底逻辑**（CDN → 本地 → Material unpkg）

  - 目标：完全搞懂从「页面 HTML」到「SVG 渲染」的整条链路，以及三级兜底各自什么时候触发、为什么能互相接住
  - 代码入口（按依赖顺序读）：
    1. `plugins/mermaid_assets.py` —— `on_pre_build` 构建期下载本地副本（`.mermaid-version` 锁版本）；`on_post_page` 注入 `defer` + CDN src + `onerror` 本地兜底 + `preconnect`
    1. `mermaid2` 插件（`.venv/.../site-packages/mermaid2/plugin.py`）—— 把 \`\`\`mermaid 代码块转成 `<pre class="mermaid">`，并注入 `<script src>` 与 `window.mermaidConfig`（后者在 Material 9.7.7 里是死代码）
    1. Material 9.7.7 bundle（`bundle.*.min.js` 里 `mountMermaid`/`as()`）—— `typeof mermaid == "undefined"` 时才动态拉 unpkg mermaid@11；否则用 `mermaid.initialize({startOnLoad:false, themeCSS…})` + `mermaid.render()` 渲染进 shadow DOM
  - 关键理解点：
    - `defer` 保证脚本在 DOMContentLoaded 前执行 → Material 检查时 `window.mermaid` 已存在 → unpkg 回退不触发（避免重复下载）
    - `onerror` 的 `this.src` 用的是 mermaid2 注入时的**页面相对路径**，任意嵌套深度都能正确回退
    - 三级兜底：npmmirror CDN（中国区快）→ GitHub Pages 本地文件 → Material unpkg@11
    - 边界情况：CDN 挂了但 onerror 迟迟不触发、`defer` 脚本换 src 后的时序语义、`MERMAID_CDN_URL=""` 关闭 CDN 的行为
    - 验证方法（Chrome DevTools）：Network 面板 → 勾选 Offline → 刷新，确认只下载一个 mermaid 脚本且图正常渲染；恢复在线确认 CDN 主加载路径 + 只下一次包
  - 可产出：一篇 `docs/notes/research/` 下的中文笔记（站点性能优化系列）

## Notes

- 本 plan 为长期滚动清单：完成的任务打勾保留，新任务直接追加到 Tasks 末尾
- 任务粒度建议：一次一个主题（一个 repo / 一本书 / 一门课），可在子项中拆小
- 阅读类任务的产出物（笔记）落在 `docs/notes/research/` 或对应 topic 目录

## References

- [CloudFlare-ImgBed](https://github.com/isMixKu/CloudFlare-ImgBed)
- [Python For GIS: Spatial Intelligence (Gumroad)](https://pythonclcoding.gumroad.com/l/Python-For-GIS-Spatial-Intelligence)
- [Mermaid Assets Hook](../../plugins/mermaid_assets.py)
- [mermaid2 plugin.py](../../.venv/lib/python3.13/site-packages/mermaid2/plugin.py)
- [Material bundle (mermaid 集成)](../../.venv/lib/python3.13/site-packages/material/templates/assets/javascripts/bundle.d7400e89.min.js)（文件名带构建 hash，升级 Material 后以 `bundle.*.min.js` 为准）
- [Research 索引](../../docs/notes/research/index.md)
