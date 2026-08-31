---
title: Hands-On Data Visualization 笔记
tags: [reading, hands-on-data-visualization, notes]
categories: [reading]
hide: [navigation]
---

# Hands-On Data Visualization 笔记

## 笔记

### 数据可视化工作流（problem → question → find data → visualize）

- **定义**: 全书贯穿的核心方法论——**先定义问题 / 讲什么故事（problem）→ 提出并
  质询问题（question）→ 找到可靠数据（find data）→ 可视化（visualize）**。注意这是
  对全书的提炼，非书中逐字引文：书中对应 Ch 1「sketch out your data story」（起稿
  故事、先想清楚问题再选工具）、Ch 3「Find and Question Your Data」（找数据并
  质询其代表性与立场）、Ch 6–13（拖拽工具 / 代码模板可视化）

- **出现章节**: ch-0001（总纲）、ch-0002（story 起稿 → 选工具）、ch-0004（find &
  question data）、ch-0006–ch-0013（visualize）、ch-0016（tell-show-why 收束）

- **关联**: 与 [data story（数据故事）](#data-story%E6%95%B0%E6%8D%AE%E6%95%85%E4%BA%8B) 一脉相承——工作流是
  过程，data story 是主线；question/find data 环节见 ch-0004（Find and Question
  Your Data）；可视化的诚实性由 [wrong / misleading / truthful](#wrong--misleading--truthful%E7%9C%9F%E4%BC%AA%E4%B8%89%E5%88%86%E6%B3%95) 把关

- **延伸**: 实际工作中问题常被跳过（工具先行）——作者强调「先讲清楚故事再选工具」；
  这是全书给读者的核心建议：**工具永远排在问题之后**，四步的顺序不可颠倒

- **定义**: 可视化的核心叙事主线——把读者注意力引向数据中有意义的模式与洞见，
  "让读者看见森林，而不是罗列每一棵树"

- **出现章节**: ch-0002（四张纸起稿）、ch-0016（storyboard 充实并收束全书）

- **关联**: 与 [storyboard（故事板）](#storyboard) 是同一主线上的两个工具；
  选工具（ch-0002）与判断真伪（ch-0015）都以"讲什么故事"为前提

- **延伸**: 全书从 Introduction 到 Ch 15 的主线；Cole Nussbaumer Knaflic《Storytelling
  with Data》

### storyboard（故事板）

- **定义**: 用格子草图组织"问题 → 数据 → 洞察 → 可视化 → 为什么重要"的叙事序列
- **出现章节**: ch-0002（纸面起稿）、ch-0016（用真实数据填满格子、编排顺序）
- **关联**: 承载 data story 的过程工具；ch-0016 的 tell—show—why 三步是填充故事板的
  叙事节奏

### Easy Tools / Power Tools

- **定义**: 本书对可视化工具的基本二分——Easy Tools 图形界面、拖拽即用（Google Sheets、
  Datawrapper、Tableau Public）；Power Tools 为可定制、可自托管的代码模板（Chart.js、
  Highcharts、Leaflet）
- **出现章节**: ch-0002（选型十要素与推荐表）、ch-0007/ch-0008（拖拽出图）、
  ch-0011/ch-0012/ch-0013（代码模板）
- **关联**: 升级路径是全书结构——Part 1–2 用 Easy Tools，Part 3 用 Power Tools；
  选择依据见 [选型十要素](#ten-factors)
- **延伸**: 开源工具"不随第三方平台条款变动"是选 Power Tools 的核心动机（ch-0011）

### 选型十要素（Ten Factors）

- **定义**: 选工具时权衡的 10 个因素：Easy-to-learn、Free or Affordable、Powerful、
  Supported、Portable、Secure and Private、Collaborative、Cross-Platform、
  Open-Source、Accessible（视障友好）
- **出现章节**: ch-0002
- **关联**: "易学"被作者列在首位；决策本质是 trade-off（如易学 vs 强大）

### interactive vs static visualization

- **定义**: 交互式可视化（可 hover/筛选/缩放/分享）vs 静态图（JPG/PNG/PDF/GIF）；
  本书主线是交互式并嵌入网页
- **出现章节**: ch-0001（定义）、ch-0007（交互图表）、ch-0010（iframe 嵌入）、
  ch-0016（交付格式选择）
- **关联**: 嵌入机制见 [iframe](#iframe)

### iframe

- **定义**: 在网页中嵌入另一网页的 HTML 标签；工具平台的 embed code 本质是一段含
  iframe 的 HTML
- **出现章节**: ch-0010（获取与粘贴）、ch-0011（GitHub Pages 转 iframe）、ch-0017
  （iframe 排错）
- **关联**: 交互式可视化发布到自有网站的桥梁；响应式容器是小屏适配关键

### normalize（归一化）

- **定义**: 把绝对数换算成可比口径（人均、百分比、统一单位、constant dollars），
  做到"苹果对苹果"的比较
- **出现章节**: ch-0001（收入案例）、ch-0006（方法）、ch-0008/ch-0013（choropleth
  必须归一化）
- **关联**: 与"做有意义的比较"（ch-0006）同一议题；不归一化是 choropleth 常见错误

### choropleth map（分区设色图）

- **定义**: 用彩色多边形表示区域数值的地图；关键在归一化数据 + 合理的颜色分级间隔
- **出现章节**: ch-0001（分级影响印象）、ch-0008（设计原则与工具）、ch-0013
  （pivot 出多边形）、ch-0015（分类方式可被用来误导）
- **关联**: 数据来自归一化；分级（class intervals）选择是"诚实 vs 误导"的分水岭

### GeoJSON 与地理空间数据

- **定义**: 基于 JSON 的开放标准矢量格式；坐标顺序为 longitude, latitude（经度在前）
- **出现章节**: ch-0013（Leaflet 消费）、ch-0014（格式与工具链：geojson.io、
  Mapshaper、Map Warper、US Census Geocoder）
- **关联**: raster/vector 之分；KML/GPX/Shapefile 等格式转 GeoJSON 的工作流

### wrong / misleading / truthful（真伪三分法）

- **定义**: 可视化判定框架——wrong 违反硬规则（柱状图基线非零、饼图超 100%）；
  misleading 合规但有意误导（对数刻度、截断基线、双纵轴、拉宽纵横比）；truthful
  准确且合规，且可能同时存在多个"真实"画法
- **出现章节**: ch-0001（两张地图案例）、ch-0015（系统展开）
- **关联**: 识别谎言是"讲真故事"的前提；ch-0016 承接为正面叙事方法

### bias（偏差）

- **定义**: 不公平地偏向某一观点；四类数据偏差（sampling / cognitive / algorithmic /
  intergroup）+ 四类空间偏差（map area / projection / disputed territory / exclusion）
- **出现章节**: ch-0006（比较中的偏差）、ch-0015（系统分类）
- **关联**: 采样偏差详见 ch-0006；认知偏差中的 framing（5% 死亡率 vs 95% 存活率）
  与 ch-0009 疫苗表格呼应；算法偏差（司法再犯预测）是数据伦理议题

### open-source license（开源许可证）

- **定义**: 规定代码使用/分发/商用权限；MIT 宽松可商用，部分库（如 Highcharts）仅限
  非商业免费
- **出现章节**: ch-0011（GitHub 与许可证概念）、ch-0012（Chart.js vs Highcharts）
- **关联**: 商用项目选 Chart.js（MIT）而非 Highcharts

## 重要参考

- **HandsOnDataViz.org** — 本书开放获取网页版（CC BY-NC-ND 4.0），含全部模板与数据：
  <https://handsondataviz.org/>
- **Chart.js** 官方文档与 Samples、**Highcharts** Demos / API Reference — 模板定制与
  排错（ch-0012）
- **Leaflet** 官方教程 — 地图模板灵感（ch-0013）
- **geojson.io / Mapshaper / Map Warper** — 地理空间数据转换工具（ch-0014）
- **ColorBrewer** — 色盲友好的地图配色方案（ch-0008 提及方向）
- **Datawrapper Academy** — 图表/地图设计规则的可视化讲解（ch-0007 引用 Lisa Charlotte
  Rost 的文章）
- **Catherine D'Ignazio & Lauren Klein, Data Feminism**（MIT Press, 2020）— 数据中立性
  批判（ch-0004）<https://data-feminism.mitpress.mit.edu/>
- **Alberto Cairo, How Charts Lie**（W. W. Norton, 2019）— 图表说谎机制（ch-0001、ch-0015）
- **Mark Monmonier, How to Lie with Maps**（Univ. of Chicago Press）— 地图说谎机制（ch-0015）
- **Charles Wheelan, Naked Statistics** 与 **David Spiegelhalter, The Art of Statistics** —
  统计入门（ch-0005 前言、ch-0006 推荐）
- **Jonathan Schwabish, Better Data Visualizations** — 表格与可视化设计（ch-0009）

## 待查线索

- **D3.js**：作者明确表示本书不覆盖 D3 等高级库（Preface）——如需深度定制可自学
- **Bookdown 写作工作流**（附录 B，本 PDF 未收录）：Bookdown + GitHub + Zotero
- **choropleth 分级方法**（等距/分位数/自然间断）的数学细节与工具默认行为
- **COMPAS 再犯预测算法的种族偏差**（ch-0015 提及）可作数据伦理专题深挖
- **中国数据可视化工具链**：天地图、民政部行政区划数据等本地化替代（ch-0014 待查）
- **CSS 响应式 iframe 容器**的通用写法（ch-0010 延伸）
