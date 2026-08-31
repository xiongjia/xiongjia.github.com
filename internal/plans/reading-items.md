# 阅读队列（Reading Queue）

> 机器可读的阅读条目队列 + 完成/失败记录 —— **独立于开发计划**
> `internal/plans/arch/reading-assist.md`。`poe reading-assist list/run` 与
> `.pi/skills/reading-assist/SKILL.md` 的 `read` 动作从这里取原材料与输出位置；
> 完成/失败的运行结果也记录在本文件（不加进开发计划）。
> 新增条目、修改状态、追加记录都在本文件操作；开发计划只保留设计与任务。

- **本地文件**: book/novel 的 pdf/epub 放 `external/` 下任意位置（推荐 `external/book/`，
  git-ignored 永不提交）；原材料三种写法都行：`{projectRoot}/external/book/x.pdf`
  （显式，推荐，不受目录约定限制）、相对路径 `external/book/x.pdf` / `book/x.pdf` /
  `x.pdf`（脚本按 仓库根 → `external/` → `external/book/` 顺序查找）、绝对路径直接用
- **多个源（系列）**: 原材料支持**空格分隔多个源** —— 文章/论文系列=多个 URL
  （每篇一个 `part-000N` 页，跨篇概念进 notes.md）；书籍分卷=多个本地文件
  （每个文件一卷 → `part-000N`）。任一源不可用 → 该条目放弃
- **状态语义**: `not-started` → `reading` → `organized`（整理完成，**不代表读完**；
  读完由用户在 `docs/notes/reading/index.md` 总览标注）

<!-- 模板（新增条目时把本块复制到其上方，取消注释并按格式填写；模板块本身保持注释）
### <slug> — <标题>
- **slug**: <kebab-case，仅 [a-z0-9-]>
- **类型**: book | novel | article | paper
- **出处**: Douban 条目 / URL / DOI（书籍只给书目信息）
- **状态**: not-started | reading | organized（整理完成）
- **原材料**: book/novel=本地 pdf/epub 路径，推荐 `{projectRoot}/external/book/<文件名>`（git-ignored，永不提交）；article/paper=URL（系列多篇用空格分隔多个 URL）
- **输出**: docs/notes/reading/<slug>/
-->

<!-- 示例（未启用）：book 书籍本地文件（复制启用时取消注释并把本块放回 `## Reading Items` 下方）
### ddia — Designing Data-Intensive Applications（数据密集型应用系统设计）
- **slug**: ddia
- **类型**: book
- **出处**: Douban / https://book.douban.com/subject/30329536/
- **状态**: not-started
- **原材料**: {projectRoot}/external/book/ddia.epub（文件放 external/ 下，git-ignored 永不提交）
- **输出**: docs/notes/reading/ddia/
-->

<!-- 示例（未启用）：novel 小说本地文件（会额外产出 characters.md + storyline.md）
### three-body — 三体（The Three-Body Problem）
- **slug**: three-body
- **类型**: novel
- **出处**: Douban / https://book.douban.com/subject/2567698/
- **状态**: not-started
- **原材料**: {projectRoot}/external/book/three-body.epub
- **输出**: docs/notes/reading/three-body/
-->

<!-- 示例（未启用）：article 网络文章（原材料=URL，脚本预抓取）
### kv-learned-index — The Case for Learned Index Structures
- **slug**: kv-learned-index
- **类型**: article
- **出处**: https://dl.acm.org/doi/10.1145/3183713.3196909
- **状态**: not-started
- **原材料**: https://dl.acm.org/doi/10.1145/3183713.3196909
- **输出**: docs/notes/reading/kv-learned-index/
-->

<!-- 示例（未启用）：article 系列文章（多个网址空格分隔，脚本逐个预抓取，每篇一个 part 页）
### sys-design-series — 某系统设计系列文章
- **slug**: sys-design-series
- **类型**: article
- **出处**: https://example.com/series（系列主页）
- **状态**: not-started
- **原材料**: https://example.com/series/1 https://example.com/series/2 https://example.com/series/3
- **输出**: docs/notes/reading/sys-design-series/
-->

## Reading Items

> 当前无正式条目。开读新书/文章时按上方模板新增一条；新增后状态初始化为
> `not-started`。处理分两步：`poe reading-assist cache <slug>`（取原材料/提取到
> 本地缓存，不做 AI）→ `poe reading-assist read <slug>`（AI 分析产页面）；
> `poe reading-assist run <slug>` 两步合一。不带 slug 时默认取第一个未开始条目。
> 条目解析规则：`## Reading Items` 区段内的 `### <slug>` 块即一条，任何时刻只有
> 这一个区块被解析为条目；「记录」区段不会被解析。

### Hands-On Data Visualization

- **slug**: hands-on-data-visualization
- **类型**: book
- **出处**: Douban https://book.douban.com/subject/35527900/
- **状态**: organized
- **原材料**: {projectRoot}/external/books/HandsOnDataViz.pdf
- **输出**: docs/notes/reading/hands-on-data-visualization/

## 记录（Log）

### 完成（Organized）

> `poe reading-assist run` 成功产出并归档的条目。脚本自动写入并**按条目刷新**：
> 同一 slug 已有记录则更新为最近一次，不叠加增长。

### hands-on-data-visualization — Hands-On Data Visualization

- **完成时间**: 2026-08-31
- **结果**: organized（整理完成）
- **产出**: docs/notes/reading/hands-on-data-visualization/（index.md + ch-0001…ch-0017 + notes.md）
- **备注**: 本地 pdf（HandsOnDataViz.pdf，443 页）经 pymupdf 按书签拆分 17 章 + Preface；
  内容只含摘要与短摘录，无全文引用

### 失败 / 放弃（Failed / Aborted）

> 运行中途失败（pi 错误 / 未产出 index / mdformat 失败）或原材料不可用被放弃的条目。
> 脚本自动写入并**按条目刷新**为最近一次（同 slug 不叠加）；「无条目」的静默退出不记录。

（暂无）

- 2026-08-31 → hands-on-data-visualization（pages written but entry not marked organized）
