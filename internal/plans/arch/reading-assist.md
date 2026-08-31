---
title: Reading Assistant 阅读助手（AI 读书摘要 + 自检归档）
created: 2026-08-31
archived: 2026-09-01
status: completed
tags: [reading, skill, ai-archive]
---

# Reading Assistant 阅读助手

## 一句话

建一个**阅读助手 skill**（`.pi/skills/reading-assist/SKILL.md`）+ **独立读取队列文件**
`internal/plans/reading-items.md`（机器可读条目 + 完成/失败记录），本 plan 只保留开发设计
与任务：AI 按读取队列条目取原材料（网络文章 URL / 本地 pdf·epub 文件名），
产出 `docs/notes/reading/<slug>/` 章节摘要 + `notes.md` 阅读笔记，跑完自动自检
（≤ 10 轮 review，查敏感信息 / 逻辑完整性 / 格式），mdformat + CI 通过。支持
`poe reading-assist` **手动触发**（无 cron / bot 自动执行 —— 分析质量需要用户人工
调整笔记）；无条目或原材料不可用时直接放弃，成功后标记条目并保留产出供用户修改，
由用户自行决定提交。

## Goal

- **低门槛读书**：看到想精读的书/文章，开一个 Reading Items 条目即可让 AI 帮做章节级摘要
- **结构化沉淀**：每个阅读项一个目录（`index.md` 入口 + `notes.md` 笔记 + `ch-XX`
  章节摘要），公开页面只含摘要与短摘录，**书籍原文永不落地**
- **质量门禁**：skill 独立运行，产出后自检修复，最多 10 轮；最终 `poe fmt` +
  仓库 CI 全绿
- **语言策略**：原版书概念/专业名词保留英文原词不翻译（摘要正文默认中文，对齐
  research 文档约定）

## 背景与现状

- 现状缺口：`internal/plans/reading-list.md` 是长期愿望清单（列了任务但没有结构化的
  阅读笔记产出流水线）；想读的书直接在收藏夹 `collection/reading.md`，读完没有
  统一归档区
- 借鉴：`english-scraps` 计划 + `enu-organize` skill 的「inbox → AI 整理 → 归档 →
  自检」模式已验证；阅读助手复用同一模式：**队列表文件（Reading Items，独立于本计划）
  → skill 执行 → 归档到 docs/notes/reading/ → 自检**
- 本计划定位：**开发计划**（设计 + 任务 + 试点记录），读取队列独立在
  `internal/plans/reading-items.md`（条目 + 完成/失败记录）；与愿望清单 `reading-list.md`
  分工：后者长期滚动收新书，开读时条目迁入读取队列

## 设计定稿

### 1. 内容结构与命名

```text
docs/notes/reading/
├── index.md                  # 阅读总览：按类型分区（开发/技术书籍、小说、文章、论文），
│                             #   状态（reading / organized（整理完成））标注
├── <slug>/                   # 每项一目录，英文 kebab-case（如 ddia）
│   ├── index.md              # 书目入口：出处（Douban / URL / DOI）+ 全书主线
│   │                         #   + 笔记/章节/人物/故事线入口
│   ├── ch-0001.md            # 书籍章节摘要（序号零填充：ch-0001、ch-0002…）
│   ├── part-0001.md          # 网络长文拆段（part-0002、part-0003…）
│   ├── characters.md         # 人物
│   ├── storyline.md          # 故事线
│   └── notes.md              # 阅读笔记（全书主线放 index.md）
```

- **文件名规则（强制）**：文件名/目录名只允许**小写字母（a-z）+ 数字（0-9）+ 中线（-）**，
  即 `[a-z0-9-]`，禁止大写、下划线、空格、中文等其它字符 —— 目录 slug 与文件均按此
  命名；章节序号零填充（`ch-0001`、`part-0001`）；详细信息（章节名、中文书名）一律写进
  frontmatter `title`，不体现在文件名
- slug：kebab-case 英文短名；中文书名放页面 title
- 每页 frontmatter 必含 `title` / `tags` / `categories`（`categories: [reading]`，
  tags 带 slug），mdformat 兼容，页面间用相对链接
- **类型与分类**：类型支持 `book`（开发/技术等非虚构）/ `novel`（小说/叙事）/ `article`
  （文章）/ `paper`（论文）；`reading/index.md` 总览按类型分区维护（开发书籍 / 小说 /
  文章 / 论文）；小说/叙事类条目额外产出 `characters.md`（人物列表，人物名保留原文）与
  `storyline.md`（故事线/时间线，可用 mermaid timeline / flowchart），按需关联出现章节
- 与 `collection/reading.md`（Book Shelf 收藏夹）区分：收藏 = 想读清单；本区 = 整理完成的
  笔记归档（阅读进度由你另行标注）

### 2. 页面模板

**ch-XX 章节摘要**（书籍章节 / 网络文章 part 同名模板，part 多一行 `原文链接`）：

```markdown
---
title: ch-0001 理解基础（ddia）
tags: [reading, ddia, chapter]
categories: [reading]
---

# ch-0001 理解基础

- **原书章节**: 第 1 章 Understanding the Basics
- **阅读日期**: 2026-08-31
- **输入来源**: 网络文章 URL / 本地 pdf·epub（文件名）

## 摘要
简短易读的连贯总结（**不硬性限句数/长度**；中文正文，原版书概念/术语保留英文原词）；
结构 / 流程类内容可用 mermaid 框图 / 流程图辅助理解（repo 已装 mermaid2，构建期渲染）。

## 要点归纳
- **要点 1**
- **要点 2**

## 术语 / 概念
- **term**（英文原词）— 一句话解释（跨章节概念进 notes.md，不重复维护）

## 原句摘录（书籍必选；网络文章省略）
> 重要段落摘录，单条 ≤ 10 行。书籍不做全文引用/本地文件引用。

## 疑问 / 待查
- 遗留问题
```

**notes.md（阅读笔记）**（全书主线放 index.md）：

```markdown
---
title: ddia 笔记
tags: [reading, ddia, notes]
categories: [reading]
---

# ddia 笔记

## 笔记
### 概念名（英文原词）
- **定义**: …
- **出现章节**: ch-0001、ch-0003
- **关联**: 与另一概念的关系（相对链接）
- **延伸**: 相关参考文章 / 论文（外链允许）

## 重要参考
- 值得回看的文章 / 链接（仅网络资源可外链）

## 待查线索
- 全书写完仍想深入的点
```

**人物 / 故事线**：小说类条目额外产出两页 —— `characters.md`
（人物列表：人物名保留原文，表格「人物（原文名）/ 身份 / 关系 / 主要出现章节」+ 可选
mermaid 关系简图）；`storyline.md`（故事线：mermaid timeline / flowchart 呈现主线脉络 +
分幕/关键转折点与对应章节）。

**条目 index.md（书目入口）**：

```markdown
---
title: Designing Data-Intensive Applications
tags: [reading, ddia]
categories: [reading]
---

# Designing Data-Intensive Applications

- **类型**: book（article / paper / novel）
- **状态**: reading（organized 整理完成）
- **作者**: Martin Kleppmann
- **出处**: Douban 条目 / URL / DOI（书籍只给书目信息，不给本地文件）
- **开始整理**: 2026-08-31
- **整理完成**: （AI 自动补）
- **读完日期**: （用户读完时手工补注）

## 全书主线
简短易读的总体概括，**用简洁 list 列要点**（不硬性限句数）：讲什么、主线如何展开；
可用 mermaid 图辅助。

## 笔记
- [阅读笔记](./notes.md)

## 章节
- [ch-0001 理解基础](./ch-0001.md)

## 人物 / 故事线
- [人物列表](./characters.md)
- [故事线](./storyline.md)
```

### 3. 原材料输入模式

| 模式         | 说明                                                                                                                                                                           | 用途                   |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------- |
| `web`        | 直接抓取 URL，每篇一个 `source-01.html…`（代理优先 `$READING_PROXY`，回退 `$https_proxy`；**浏览器 UA + 克制式重试 ≤3 次（2s/4s 退避，防反爬）**）；系列文章=多个 URL 空格分隔 | 在线教程 / 文章 / 系列 |
| `local-file` | 用户给**本地 pdf/epub 文件名/路径**（放 git-ignored 的 `external/` 下任意位置，推荐 `external/book/`），AI 本机读取提取（**主模式**）；分卷=多个文件空格分隔                   | 本地书籍 / 分卷        |

**内容边界（强制）**：

- **输入只有两种**：`URL` 或 **本地 pdf/epub 文件名**（不做聊天粘贴原文）；
  **一个条目可含多个源**（空格分隔）：article/paper=系列多 URL（每篇一个 part 页，
  跨篇概念进 notes.md/series 主线进 index.md），book/novel=分卷多文件（每卷一个
  part 页）；任一源不可用 → 整条放弃
- 本地读取允许：AI 在本机直接读用户给的 pdf/epub 提取文本（读取 ≠ 上传）；文件本身
  **永不 git 提交 / 上传**，只留在用户本地（放 git-ignored 的 `external/` 下任意位置，
  推荐 `external/book/`；原材料支持三种写法：`{projectRoot}/external/…` 显式路径
  （占位符替换为仓库根，不受目录约定限制）、相对路径（脚本按 仓库根 → `external/` →
  `external/book/` 顺序查找，`external/book/x.pdf` / `book/x.pdf` / `x.pdf` 均可）、
  绝对路径直接用）
- 提取（**uv 预装、跨主机**）：epub = 标准库 `zipfile`（toc/spine 拆章节），零依赖；
  pdf = **pymupdf**（自带二进制 wheel，首选）→ 兜底 **pypdf**（纯 Python）；执行走
  `uv run --with pymupdf --with pypdf python …`（uv 首次联网拉取并缓存，之后离线可用，
  Linux/macOS 均无需 apt/brew）；两者不可导入 / 文件损坏 → 无法解析 → 该条**直接放弃**；
  章节文本存本地缓存 `$READING_CACHE_DIR/<slug>/`（默认系统临时目录，不落仓库；
  `.env` 每机可配 `READING_CACHE_DIR`），**运行后保留**（阅读中可再解压 pdf/epub、
  调整笔记；手动清理）
- **章节拆分（降级）**：能按书目录（epub toc/spine、pdf 目录/书签）拆章节 → 逐章
  `ch-0001…`；**无法拆分**（扫描版/无目录 PDF）→ 降级按页/卷分组为 `part-0001…`
  （或单文件「全书笔记」），不因无章节结构放弃；只有文件损坏/无法解析才放弃
- **代理（每机不同）**：`.env`（git-ignored，各机器各自配，`shared/env.py` 加载）新增
  `READING_PROXY`，专供阅读助手抓 URL；优先级 `READING_PROXY` → `$https_proxy` /
  `$http_proxy` → 默认本地代理 `http://127.0.0.1:1095`
- `reading/<slug>/` 只含摘要 + 短摘录，不引用本地文件（source 只写书目出处）
- 敏感信息（API key、本地 password、个人信息）一律剔除/打码，绝不进公开页

### 4. Plan-skill 接合（特殊 reading 计划）

队列独立于本计划：`internal/plans/reading-items.md` 是**机器可读条目文件**（`## Reading Items`
区段 + 模板注释 + `## 记录（Log）` 完成/失败分区），skill 与 `poe reading-assist` 从这里
取原材料与输出位置、追加完成/失败记录；本 plan 不再承载条目或运行记录。

- **状态流转**（整理进度，非读完）：`not-started` → `reading`（整理中：手动 `read`
  开始/中断时可停留在 reading 待继续，自动 `run` 亦同）→ `organized`（整理完成：AI
  自动完成时置，同时追加「完成」记录并更新总览表；**不代表用户读完**——读完由 `done`
  在总览标注）
- 运行结果（完成 / 失败 / 放弃）只写回 `internal/plans/reading-items.md` 的记录分区；
  `reading-list.md` 仍为愿望清单，开新书时迁条目到队列。

### 5. Skill 规格（`.pi/skills/reading-assist/SKILL.md`）

- 命名 `reading-assist`，description 简短，动作词表与完整流程在正文（同
  `enu-organize` 模式，避免常驻 context）
- **动作**（英文触发词）：
  - `read <slug|标题>` — 主流程：读 `internal/plans/reading-items.md` 的 Reading Items →
    按输入模式取原材料 → 建 `<slug>/` 结构（index → 各 ch/part → notes；小说/叙事类
    加 characters + storyline；无章节结构时按页/卷降级 part 分组）→ 自检 review →
    mdformat → 汇报（条目状态 → `reading`，完成后 → `organized`（整理完成）+ 追加
    「完成」记录）
  - `ask <slug> <问题>` — 答疑 / 修改摘要 / 追加手动 notes（建议稿，尊重已有内容）
  - `done <slug>` — 用户读完标注：总览条目标注「读完」（整理状态保持 `organized`）
- **独立运行**：一次 `read` 跑完全流程，不依赖逐步指挥
- **输出要求**：frontmatter 齐全、相对链接、mdformat（`poe fmt`）

### 6. 自检与 Review（≤ 10 轮）

`read` 产出后强制自检循环（用 `review_loop` 工具 `maxIterations: 10`，或按
review-loop 协议串行手动跑；每轮 fresh context）：

1. **敏感信息**：API key / 本地 password / 个人信息 → 必须清零
1. **逻辑与完整性**：摘要符合逻辑、无缺失章节；每章有摘要 + 要点；概念有定义与出处
1. **一致性**：术语英文原词前后一致；slug / 链接 / 命名对得上
1. **格式与 CI**：frontmatter 齐全、mdformat 通过、MkDocs 构建通过（含 mermaid 图渲染，
   `poe build-drafts`；若改动 nav/插件再跑 `poe test` 与生产 `poe build`）

- mermaid 图（尤其 `timeline`）以构建期渲染为准：插件不支持该语法 → 用 flowchart 兜底
- must-fix → 修复 → fresh-eyes 重查；最多 10 轮；同一问题连续 2 轮出现 → 停下请用户介入
- 可配合 `code-review` skill：内容维度交给它，本 skill 补 reading 特定项

### 7. 与现有体系衔接

- `mkdocs.yml` nav 新增 `Reading: notes/reading/index.md`
- `reading-list.md`：保留为愿望清单
- `collection/reading.md`：Book Shelf 不动；想读的书可从收藏夹开读
- 技术深读仍可选落 `docs/notes/research/topics/`；`reading/` 聚焦章节式阅读笔记

### 8. 命令触发（手动，无自动调度）

- **命令触发**：`poe reading-assist <子命令> [slug]`（脚本 `scripts/reading_assist.py`，snake_case；
  poe cmd = `uv run --with pymupdf --with pypdf python scripts/reading_assist.py`，
  提取工具由 uv 预装、跨主机可用；子命令 `list` / `cache` / `read` / `run`）：

  - `list` — 列出 Reading Items 与状态
  - `cache [slug]` — **第一步：取原材料**。抓取 URL / 校验本地文件，提取并写入本地缓存
    `$READING_CACHE_DIR/<slug>/`（不做 AI；可重复跑，已缓存则复用）
  - `read [slug]` — **第二步：AI 分析**。读缓存源 → 调本地 `pi -p --mode json`（同
    `scripts/update_health_summary.py` 的 run_pi 做法）→ pi 按 SKILL.md 流程执行
    （提取/读缓存 → 写 `reading/<slug>/` → 自检 ≤10 轮）→ **归档队列**
    （条目状态 → `organized`（整理完成）、追加「完成」记录）→ 脚本收尾 `poe fmt`
  - `run [slug]` — `cache` + `read` 两步合一（向后兼容）
  - `--dry-run` — 只打印提示词与选中条目，不调 AI（read/run 支持）

- **放弃分支（满足任一 → 静默退出、零产出页面、不建 PR；无条目时不记录，
  针对已有条目的放弃会追加一行「放弃」记录到队列 Log）**：

  - 读取队列 **没有 Reading Items 条目**（静默退出不记录）
  - 有条目但**本地文件不存在**（路径失效）
  - **pdf/epub 无法解析**（pymupdf/pypdf 不可导入或文件损坏）
  - **URL 不可访问**（抓取失败）

- **无自动调度 / 无 bot 任务**（已取消）：`git_bot.py` 不再注册 reading-assist，
  mkdocs.yml `extra.bot.cron` 无 daily-reading-assist —— 分析质量需要人工调整笔记，
  因此**纯手动**：用户 `poe reading-assist run` 产出后自行修改、自行提交，不自动 PR

- **代理**：URL 抓取走 `.env` 的 `READING_PROXY`（各机器不同），未设回退 `$https_proxy` /
  默认本地代理 `http://127.0.0.1:1095`

- **审阅节奏**：手动 run → 产出后人工调整 `docs/notes/reading/<slug>/` → 满意后自行提交

## Tasks

### 搭建

- [x] 建 `docs/notes/reading/` 目录 + `reading/index.md` 总览（类型分类 + 状态 + 说明），
  在 `mkdocs.yml` nav 注册 `Reading`
- [x] 建 `.pi/skills/reading-assist/SKILL.md`：触发词（read / ask / done）+ 输入模式 +
  生成流程（读 plan → 取原材料 → 建结构 → 模板写出）+ 内容边界 + 自检 ≤ 10 轮 +
  mdformat / CI 要求
- [x] 本 plan 按「Reading Items」条目格式写清楚（slug / 类型 / 出处 / 状态 / 原材料 /
  输出），作第一个待执行条目的模板
- [x] 建 `scripts/reading_assist.py` + poe task `reading-assist`（list / cache / read /
  run [slug] / --dry-run；解析读取队列 Reading Items → 提示词调本地 pi → 写页面 →
  收尾 `poe fmt`；无条目静默退出）
- [x] ~~`scripts/git_bot.py` 注册内置任务 `reading-assist`（cmd + commit 文案），
  `poe bot run reading-assist --handoff` 可手动触发~~（2026-09-01 取消：目的改为手工，
  git_bot.py 已还原，不注册 bot 任务）
- [x] 明确提取工具依赖（uv 预装、跨主机）：epub=标准库零依赖；pdf=pymupdf →
  pypdf；poe/bot cmd 用 `uv run --with pymupdf --with pypdf python …`；SKILL/README
  写明「uv 首次联网拉取并缓存，Linux/macOS 无需系统包」，不可导入时该条放弃
- [x] `.env.example` 增加 `READING_PROXY` 说明（git-ignored，每机各自配，经
  `shared/env.py` 加载；阅读助手抓 URL 专用代理，回退既有 $https_proxy）
- [x] `internal/commands.md` / poe 帮助文案登记 `poe reading-assist` 用法（list / run /
  --dry-run + 环境变量 READING_PROXY）
- [x] 本地缓存改由 `$READING_CACHE_DIR` 控制（原名 `$READING_TMP_DIR`，后改名；默认
  系统临时目录，不落仓库；`.env` 每机可配），**运行后保留**（阅读中可再解压 pdf/epub）
- [x] ~~mkdocs.yml `extra.bot.cron` 加 `daily-reading-assist`（`0 4 * * *` 凌晨 4 点，
  handoff: true；无条目/源不可用时不产 PR）~~（2026-09-01 取消：无自动调度，已从
  mkdocs.yml 删除；改为手工执行）

### 生成流水线

- [x] skill `read` 主流程验证：读 Reading Items →（web 抓取 或 读本地 pdf/epub 文件）→ 建
  `reading/<slug>/`（index / ch / part / notes）→ 自检 → 汇报（试点条目 twelve-factor 已产出）
- [x] 自检循环验证：敏感信息 / 逻辑完整性 / 一致性 / 格式四项跑通；产出后 mdformat +
  构建全绿（摩擦点：首轮漏 `\*\*` 转义粗体 → 已修，并补入 SKILL 自检项）
- [x] ~~`ask` 验证：答疑 / 修改建议稿 / 追加手动 notes，尊重已有内容不覆盖（留真实阅读后交互）~~（2026-08-31 确认不需要，取消）
- [x] `done` 语义验证：自动 run 完成即整理完成 —— 状态 → organized + 总览表 + plan 条目同步
  （手动 `done` 命令未单独实测）
- [x] 输出后全部产出 `poe fmt` 格式化，生产构建通过；改动 nav 时确认生产页面可点击
- [x] 验证 `poe reading-assist list` / `--dry-run`（无条目时正确走放弃分支，退出码 0 零产出）
- [x] ~~验证 `poe bot run reading-assist <slug> --handoff` 走通 handoff → draft PR → CI gate~~
  （2026-09-01 取消：目的改为手工，无 bot/PR 流程）
- [x] 验证放弃分支：无条目 / 文件缺失 / URL 不可访问 → 静默退出零产出（单元测试覆盖文件缺失与 URL 不可达）
- [x] 验证 `uv run --with pymupdf --with pypdf …` 在另一台 Linux 主机可用（或 uv 缓存离线可用）
  （2026-08-31 确认：Linux 主机由用户后续自行验证）
- [x] ~~验证章节拆分降级：无目录结构 PDF → 按页/卷分组 part，不放弃；损坏文件 → 放弃~~（2026-08-31 确认不需要，取消）
- [x] 验证状态流转：not-started → organized 一次到位（自动 run 实测）；手动 read 中断 →
  reading 中间态未实测
- [x] ~~验证 mermaid `timeline` 构建期渲染（不支持则 storyline 用 flowchart 兜底；需小说类试点）~~（2026-08-31 确认不需要，取消）
- [x] 验证成功后 plan 条目归档（`mark_organized` 单元测试只改目标条目）且改动 mdformat 兼容、CI 通过

### 试点验收标准（达到 a+b+c+d+e 即方向明确）

- **a) 流程**：完整跑通一条真实阅读（web 文章 或 本地 pdf/epub 文件），一次 `read`
  产出全套结构，用户无需手改超过 2 处
- **b) 边界**：产出页无本地文件引用、无敏感信息；书籍项只有摘要 + 短摘录
- **c) CI**：产出 commit 前 `poe fmt` / 构建（及必要时 `poe test`）全绿
- **d) 流程（手工）**：`poe reading-assist cache` / `read` / `run` 手动打通；无条目/
  文件缺失/解析失败/URL 不可访问 → 零产出放弃；成功后标记条目 + 保留产出，由用户
  人工调整后自行提交（原「自动调度 + bot 推 PR」验收项已随取消，2026-09-01）
- **e) 分类**：`reading/index.md` 按类型分区（开发 / 小说 / 文章 / 论文）正确展示；类型
  (book / novel / article / paper) 标注入条目
- 附：自检 ≥ 1 次真正抓出并修复问题（验证 review 不是走过场）

### 试点结果（2026-08-31 · twelve-factor 文章）

- **a) 流程** ✅：一次 `poe reading-assist run twelve-factor` 产出全套结构
  （index.md + 12×ch + notes.md），内容用户侧 0 处手改（仅机器修正转义粗体）
- **b) 边界** ✅：产出页无本地文件引用、无敏感信息；文章类外链出处
- **c) CI** ✅：mdformat / ruff / pytest（718 通过）/ build-drafts 全绿
- **d) 流程（手工）** ✅：`cache`（book 提取 18 章 / article 预抓取）/ `read` / `run` /
  放弃分支 / 条目标记 / 记录刷新均可用；自动调度与 `--handoff` 已取消改手工（2026-09-01）；
  Linux 主机由用户后续自行验证
- **e) 分类** ✅：总览「## 📄 文章」分区自动更新，条目类型 article
- 摩擦点：① 首跑 pi 内 curl 无超时挂死 → 已改**脚本预抓取** + curl `-m 20`；
  ② 自检漏 `\*\*` 转义粗体 → 人工修复，已补入 SKILL 自检项

### 收尾

- [x] 手工模式验证完成（2026-09-01）：`cache` / `read` / `run` 均可用（book 本地
  pdf 预提取章节、article URL 预抓取、复杂度/空文本放弃、条目标记 + 完成/失败记录
  刷新、产出保留供人工调整）；目的从自动执行改为**手工执行**（无 cron / bot / PR）
- [x] 实际用 1 本真实阅读验证节奏（试点 twelve-factor 文章），摩擦点已记录（见试点结果）
- [x] 按试点调整：章节粒度（是否允许数章合并一页）、降级分组粒度、摘录上限、状态字段维护位置
  （2026-08-31 用户复盘反馈：已过 2 篇试点文章（twelve-factor、json-intro），现规则维持现状，无需调整）
- [x] 完成后本 plan 条目/任务勾选到位；`reading-list.md` 无迁入条目（试点直接建档）

## Reading Items（已移至独立文件）

> 阅读条目队列（含模板注释 + 完成/失败记录）已独立到
> **`internal/plans/reading-items.md`**，与本开发计划分开，避免条目/运行记录与开发任务混淆。
> 新增条目、修改状态、查看完成/失败记录 → `internal/plans/reading-items.md`；
> 操作步骤见 `internal/commands.md` → Reading →「新增阅读项」。

## Notes / 开放问题

- **命名已定**：目录 `docs/notes/reading/`、skill `.pi/skills/reading-assist/`、
  队列文件 `internal/plans/reading-items.md`（Reading Items + 完成/失败记录），本文件为开发计划
- **语言**：原版书术语/概念英文原词不翻译（需求点 6）；摘要正文默认中文，是否允许
  全英文摘要试点后定
- **状态字段**：`reading` / `organized`（整理进度）只维护 `reading/index.md` 总览表，条目
  index.md frontmatter 不再重复放（避免双份漂移）——试点确认
- **书籍不落地**：本地 pdf/epub 永不进库（需求点 4），摘录单条 ≤ 10 行控制体量
- **自检上限 10 轮**：用 review-loop 协议（fresh context 每轮）；与 `code-review`
  skill 配合，本 skill 侧重 reading 特定维度
- **与 reading-list.md 分工**：愿望清单收新书 → 开读迁入 Reading Items → 读完（或整理
  完成后）归档到 reading/，避免两个清单重复维护同一本书的状态
- **摘要句数**：不硬性限制句数/长度（简短易读）；摘要/要点用**简洁 list**，避免整段长文
- **表达形式**：`notes` / `index` / 章节摘要均可辅以 **list + mermaid**（flowchart / timeline）
- **小说 / 叙事类**：增 `characters.md`（人物列表，人物名保留原文）+ `storyline.md`
  （故事线）；`notes.md` 侧重主题/意象/伏笔等叙事线索
- **命令与手动流程**：`scripts/reading_assist.py`（poe reading-assist）**手动触发**；
  无 git_bot 任务 / 无 cron 自动调度（已取消，见第 8 节）—— 分析质量需人工调整笔记；
  无条目/源不可用 → 静默放弃（零产出）；成功 → 标记条目 + 保留产出，由用户自行提交
- **代理**：抓 URL 用 `.env` 的 `READING_PROXY`（每机不同，`shared/env.py` 加载）；
  回退既有 `$https_proxy` / 默认本地代理
- **降级与支持**：无目录结构 PDF → part/卷分组降级；mermaid `timeline` 以构建期渲染为准，
  不支持则 flowchart 兜底
- **状态流转**：`not-started → reading → organized`（整理进度，非读完；手动可停在
  reading 继续，自动 run 一次到位）
