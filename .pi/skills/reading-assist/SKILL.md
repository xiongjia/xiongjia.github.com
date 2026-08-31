---
name: reading-assist
description: "Reading Assistant: read/ask/done on Reading Items entries — chapter summaries, notes, characters & storyline. Trigger words and full workflow in the body."
---

# Reading Assistant（reading-assist）

把 `internal/plans/reading-items.md`（独立读取队列文件）的 `## Reading Items` 条目（slug /
类型 / 状态 / 原材料 / 输出）按流程处理，产出 `docs/notes/reading/<slug>/`
章节式阅读笔记；运行结果（完成 / 失败 / 放弃）追加到该文件的 `## 记录（Log）` 分区。
开发计划 `internal/plans/arch/reading-assist.md` 不承载条目与运行记录。

| 触发词              | 动作                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------- |
| `read <slug\|标题>` | 主流程：选条目 → 取原材料 → 建全套页面 → 自检 ≤ 10 轮 → mdformat → 汇报（条目 → organized（整理完成）） |
| `ask <slug> <问题>` | 阅读后答疑 / 修改摘要 / 追加手动笔记（建议稿，尊重已有内容）                                            |
| `done <slug>`       | 用户读完标注：总览条目标注「读完」（整理状态保持 organized）                                            |

> 动作用英文：`read` / `ask` / `done`。
> 手动触发走 `poe reading-assist`（`scripts/reading_assist.py`）；CLI 拆成两步：
> **`cache`**（取原材料：抓取 URL / 校验本地文件，提取并写入本地缓存，不做 AI）与
> **`read`**（AI 分析：读缓存源 → 写页面 → 自检 → 归档），`run` 为两步合一。
> 本 skill 即命令/手动执行的同一套流程规格。

## 输入模式（原材料只有两种）

| 模式         | 说明                                                                                                                                                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `web`        | 文章/教程/论文：**脚本预抓取**到 `$READING_CACHE_DIR/<slug>/source.html`（默认系统临时目录；`curl -S -L -m 20` **带浏览器 UA + 克制式重试 ≤3 次（2s/4s 退避，防反爬）**，代理回退链 `$READING_PROXY` → `$https_proxy` → `http://127.0.0.1:1095`），AI 只读本地文本，不需要联网 |
| `local-file` | 书籍/小说：用户给**本地 pdf/epub 文件名/路径**（写 `{projectRoot}/external/…` 显式路径，或相对路径；文件放 git-ignored 的 `external/`，永不提交）。多个文件（分卷）空格分隔，每卷一个 part 页                                                                                  |

- **不做聊天粘贴原文**；本地 pdf/epub 只在用户本地设备上
- 提取：epub = 标准库 `zipfile`（toc/spine 拆章节）；pdf = `pymupdf`（首选）或 `pypdf`；
  工具不可用 / 文件损坏 → 该条**放弃**（零产出）
- 提取出的章节文本放本地缓存 `$READING_CACHE_DIR/<slug>/`（默认系统临时目录，`.env` 每机可配），**运行后保留**，方便阅读中修改笔记/再解压 pdf·epub（需要时手动删除该目录）

## 内容边界（强制）

- `reading/<slug>/` 只含摘要 + 短摘录（单条 ≤ 10 行）；**不引用本地文件**，source 只写书目出处
- 网络文章可外链；书籍不做全文引用/本地文件引用
- 敏感信息（API key、本地 password、个人信息）一律剔除/打码，绝不进公开页
- 文件名/目录名只允许 `[a-z0-9-]`（小写字母 + 数字 + 中线），详情写 frontmatter `title`
- 每页 frontmatter 必含 `title` / `tags` / `categories`；页面间用相对链接
- **表达形式**：摘要 / 要点用**简洁 list**（避免整段长文）；`notes`、`index`、章节摘要均可
  辅以 **list + mermaid**（flowchart / timeline）表达
- **mermaid 约束**：**全书主线默认用简洁 list，不用 mermaid**；mermaid 仅限流程/时间线确有
  分支关系且\*\*节点文案简短（每个节点 ≤ 10 字，细节放节点外的 list）\*\*时使用 ——
  长文案节点（如整句章节说明）会渲染拥挤看不清，禁止

## 主流程（read）— 8 步

1. 读 `internal/plans/reading-items.md` 的 `## Reading Items`，确定条目
1. 按输入模式取原材料：
   - `web`：脚本已预抓取 `$READING_CACHE_DIR/<slug>/source-01.html…`（每篇一个文件，curl -S -L -m 20 带超时 + 浏览器 UA + 重试 ≤3 次），直接读本地文本；系列文章=多个文件，**每篇一个 `part-000N` 页**，跨篇概念进 notes.md；若仍需联网抓取，curl 一律带 `-m 20`（避免挂死）
   - `local-file`：从本地文件提取章节文本到 `$READING_CACHE_DIR/<slug>/`（epub=zipfile、
     pdf=pymupdf/pypdf），按书目录（epub toc/spine、pdf 书签）拆章节；无目录结构 →
     按页/卷分组降级 `part-0001…`
1. 建 `docs/notes/reading/<slug>/`：
   - `index.md`（书目入口：出处 + 全书主线 + 笔记入口在最前 + 章节入口）
   - 章节逐章 `ch-0001.md`…；网络长文拆段 `part-0001.md`…
   - `notes.md`（阅读笔记）
   - 小说/叙事类另加 `characters.md`（人物名保留原文）+ `storyline.md`（mermaid timeline /
     flowchart 呈现）
1. 按模板写出（见下「页面模板」）
1. 更新 `docs/notes/reading/index.md` 总览（按类型分区：开发/技术书籍、小说、文章、论文）
1. 更新 `internal/plans/reading-items.md` 条目：状态 → `reading` → 完成后 →
   `organized`（整理完成）并追加「完成」记录；失败/放弃时在「失败 / 放弃」分区追加一条
1. 自检循环（≤ 10 轮，见下「自检与 Review」）
1. 汇报：产出清单（各页 + 条数）+ 存疑项，只请用户确认存疑项

## 页面模板

**`ch-0001.md`（章节摘要；part 同名，多一行《原文链接》）**：

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
简短易读的连贯总结（不硬性限句数/长度；中文正文，原版书概念/术语保留英文原词）；
结构/流程类内容可用 mermaid 框图/流程图辅助理解（构建期渲染）；节点文案必须简短（≤ 10 字），
细节放节点外的 list，禁止长句节点。

## 要点归纳
- **要点 1**

## 术语 / 概念
- **term**（英文原词）— 一句话解释（跨章节概念进 notes.md）

## 原句摘录（书籍必选；网络文章省略）
> 重要段落摘录，单条 ≤ 10 行。书籍不做全文引用/本地文件引用。

## 疑问 / 待查
- 遗留问题（全书读完能解决的就进 notes.md）
```

**`notes.md`（笔记）**：

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

**`characters.md`（人物）**：人物名保留原文（原版书英文原名，可括号附通用译名）；表格
「人物（原文名）/ 身份 / 关系 / 章节」+ 可选 mermaid 关系简图。

**`storyline.md`（故事线）**：mermaid timeline / flowchart 呈现主线脉络 + 分幕/转折点与
对应章节（插件不支持 timeline 时用 flowchart 兜底）。

**`index.md`（书目入口）**：类型 / 状态（reading ↔ organized 整理完成）/ 作者 / 出处
（Douban 条目或 URL 或 DOI，书籍只给书目信息）+ 全书主线 + **整理完成日期**
（读完日期由用户手工补注）→ **阅读笔记（在章节前）** → 章节 → 人物 / 故事线入口，
全部相对链接。

- 所有阅读子页 frontmatter 加 `hide: [navigation]`（对齐 knowledge 页面）；侧栏由 TOC +
  「← 返回 Reading」（回总览）构成。

## 自检与 Review（≤ 10 轮）

`read` 产出后强制自检循环（用 `review_loop` 工具 `maxIterations: 10`，或按 review-loop
协议串行手动跑；每轮 fresh context）：

1. **敏感信息**：API key / 本地 password / 个人信息 → 必须清零
1. **逻辑与完整性**：摘要符合逻辑、无缺失章节；每章有摘要 + 要点；概念有定义与出处
1. **一致性**：术语英文原词前后一致；slug / 链接 / 命名对得上
1. **格式与 CI**：frontmatter 齐全、mdformat 通过、MkDocs 构建通过（含 mermaid 图渲染；
   改动 nav/插件时再跑 `poe test` 与生产构建）；**无 `\*\*` 等转义残留**（转义星号会
   渲染成字面星号）

- must-fix → 修复 → fresh-eyes 重查；最多 10 轮；同一问题连续 2 轮出现 → 停下请用户介入
- 可配合 `code-review` skill：内容维度交给它，本 skill 补 reading 特定项
- 产出完成后全部经 `poe fmt`（mdformat），保证 CI（pytest / ruff / format / build）通过

## 约束

- **独立运行**：一次 `read` 跑完全流程，不依赖逐步指挥（`poe reading-assist run` 手动触发）
- **不 push / 不 commit**：AI 绝不执行 `git push` / `git commit`；无自动调度/自动 PR——
  产出后由用户人工调整笔记，自行决定何时提交
- **放弃分支**：无条目 / 本地文件缺失 / 无法解析 / URL 不可访问 → 静默退出零产出（不建页、
  不改条目、无 diff 无 PR）
- **纠错**：产出是建议稿，只列存疑项；尊重已有内容（用户手改过的不覆盖、不「纠正」）
- **语言**：原版书概念/术语/人物名保留英文原词不翻译；摘要正文默认中文
- **代理**：抓 URL 用 `$READING_PROXY`（`.env` 每机配，`shared/env.py` 加载），未设回退
  `$https_proxy` / 默认本地代理 `http://127.0.0.1:1095`
- **提取工具**：由 uv 预装（`uv run --with pymupdf --with pypdf …`），Linux/macOS 无需
  系统包；缺失时该条放弃
