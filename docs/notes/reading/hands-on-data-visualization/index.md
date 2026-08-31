---
title: Hands-On Data Visualization（整理完成）
tags: [reading, hands-on-data-visualization, dataviz]
categories: [reading]
hide: [navigation]
---

# Hands-On Data Visualization

- **类型**: book（开发 / 技术书籍）
- **状态**: organized（整理完成）
- **作者**: Jack Dougherty、Ilya Ilyankou
- **出处**: Douban <https://book.douban.com/subject/35527900/>（O'Reilly Media，2021-05-04，ISBN 9781492086000）
- **整理完成日期**: 2026-08-31
- **读完日期**: （由用户读完后再手工补注）

## 全书主线

从零开始、不要求任何编程经验的**交互式数据可视化入门书**：先讲「用数据讲故事」的理念
与选型，再强化电子表格与数据获取/清洗等基础技能，然后用拖拽工具（Google Sheets、
Datawrapper、Tableau Public）做出交互式图表、地图与表格，接着升级到用 GitHub 编辑并
托管开源代码模板（Chart.js、Highcharts、Leaflet），最后回归全书的中心命题——**讲真实且
有意义的数据故事**，识别他人如何用可视化说谎、以及如何在自己的作品中减少偏差。

全书分为四部分（Introduction 之后按 15 章 + 附录组织）：

- **Part 1（ch-0001～ch-0006）**: 想清楚数据故事 → 十要素选工具 → 电子表格基本功 →
  找到并质询数据 → 清洗脏数据 → 做有意义的比较
- **Part 2（ch-0007～ch-0010）**: 用拖拽工具分别产出图表、地图、表格，并学会用
  iframe / embed code 把它们嵌入自己的网站
- **Part 3（ch-0011～ch-0014）**: 进入 GitHub 编辑开源代码模板（Chart.js、Highcharts、
  Leaflet），并掌握 GeoJSON 等地理空间数据的转换工具
- **Part 4（ch-0015～ch-0017）**: 区分「错误 / 误导 / 真实」的可视化，识别数据与空间偏差，
  用 storyboard 把可视化组织成叙事，附常见问题排查附录

## 阅读笔记

- [笔记（跨章节概念 / 术语 / 重要参考 / 待查线索）](./notes.md)

## 章节

| 页码    | 原书章节                                | 摘要                                        |
| ------- | --------------------------------------- | ------------------------------------------- |
| ch-0001 | Introduction: Why Data Visualization?   | [为什么做数据可视化](./ch-0001.md)          |
| ch-0002 | Ch 1 Choose Tools to Tell Your Story    | [选工具讲你的故事](./ch-0002.md)            |
| ch-0003 | Ch 2 Strengthen Your Spreadsheet Skills | [强化电子表格技能](./ch-0003.md)            |
| ch-0004 | Ch 3 Find and Question Your Data        | [找到并质询你的数据](./ch-0004.md)          |
| ch-0005 | Ch 4 Clean Up Messy Data                | [清洗脏数据](./ch-0005.md)                  |
| ch-0006 | Ch 5 Make Meaningful Comparisons        | [做有意义的比较](./ch-0006.md)              |
| ch-0007 | Ch 6 Chart Your Data                    | [图表化你的数据](./ch-0007.md)              |
| ch-0008 | Ch 7 Map Your Data                      | [地图化你的数据](./ch-0008.md)              |
| ch-0009 | Ch 8 Table Your Data                    | [表格化你的数据](./ch-0009.md)              |
| ch-0010 | Ch 9 Embed On the Web                   | [嵌入网页](./ch-0010.md)                    |
| ch-0011 | Ch 10 Edit and Host Code with GitHub    | [用 GitHub 编辑与托管代码](./ch-0011.md)    |
| ch-0012 | Ch 11 Chart.js and Highcharts Templates | [Chart.js 与 Highcharts 模板](./ch-0012.md) |
| ch-0013 | Ch 12 Leaflet Map Templates             | [Leaflet 地图模板](./ch-0013.md)            |
| ch-0014 | Ch 13 Transform Your Map Data           | [转换你的地图数据](./ch-0014.md)            |
| ch-0015 | Ch 14 Detect Lies and Reduce Bias       | [识别谎言、减少偏差](./ch-0015.md)          |
| ch-0016 | Ch 15 Tell and Show Your Data Story     | [讲述并展示你的数据故事](./ch-0016.md)      |
| ch-0017 | Appendix A Fix Common Problems          | [排查常见问题](./ch-0017.md)                |

> 页码对应本书 PDF 的章；ch-0001 为 Introduction，之后与原书章节号一一对应。Preface
> （读者对象、致谢、开放获取说明）未单独成页——作者与开放获取信息见上方元信息与
> [notes.md](./notes.md) 的重要参考。
