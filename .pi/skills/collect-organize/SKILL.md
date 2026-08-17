---
name: collect-organize
description: "Collection Scraps: collect, organize & append to collection pages or plans list. Trigger words and full workflow in the body."
---

# Collection Scraps（collect-organize）

把日常收集的碎片从 `collection/scraps/inbox.md` 整理并追加到对应位置：

- **资源型**（link / book / note）→ `collection/<domain>.md` 收藏页
- **行动型**（todo / idea / misc）→ `collection/scraps/plans.md` 可见计划清单

路径相对 `docs/notes/collection/`；`inbox.md` 相对 `scraps/` 目录。

| 触发词       | 动作                                   |
| ------------ | -------------------------------------- |
| `add <内容>` | 追加一条到 inbox（资源类，需 arch）    |
| `arch`       | 批量整理 inbox：分类 → 去重 → 路由追加 |

> 动作用英文：`add` / `arch`。
> `todo` / `idea` 不用 skill，直接 `poe collect-todo` / `poe collect-idea` 写到 plans.md。

## 1. 记录（add \<内容>）

1. 追加一行 `YYYY-MM-DD <内容>` 到 `inbox.md`（今天日期自动补；多行内容折叠为一行）
1. 文件不存在时先建 frontmatter（`draft: true` + `title: Collection Scraps Inbox` + 格式说明注释）
1. 完成后简短确认（如「已记：A neat CLI tool for X」），不啰嗦

## 2. 归档（arch）— 7 步

触发条件（满足任一即可）：inbox 行数 ≥ 15 条 / 距离上次整理 ≥ 2 周 / 用户主动。

1. 读取 inbox 全部条目
1. 逐条判定 `type`（见下）和 `domain`（见下），无法判定 → `type: misc` + `domain: uncategorized`
1. **去重**：
   - 有 URL → 在目标页面中搜索该 URL，存在则跳过
   - 无 URL → 在目标页面中模糊匹配标题关键词，存在则跳过
1. **路由追加**（按 type 分流）：
   - `link` / `book` / `note` → 追加到 `collection/<domain>.md`
   - `todo` / `idea` / `misc` → 追加到 `collection/scraps/plans.md`
1. **清理 inbox**：删除已处理条目（不保留、不建处理日志）
1. 更新 `collection/index.md` 的「上次整理：YYYY-MM-DD」
1. 汇报：本次追加 N 条（按目标 + 按 type 分组）+ **存疑项清单**，只请用户确认这些

### type 判定

| type   | 判定                         | 示例                              | 路由目标      |
| ------ | ---------------------------- | --------------------------------- | ------------- |
| `link` | URL / 工具推荐 / GitHub 仓库 | 「yt-dlp — YouTube 下载器」       | `<domain>.md` |
| `book` | 想读或读过的书               | 《Designing Data-Intensive Apps》 | `<domain>.md` |
| `note` | 阅读笔记 / 文章摘要          | 某篇文章的核心观点                | `<domain>.md` |
| `todo` | 待办事项 / 计划              | 「研究一下 XX 的源码」            | `plans.md`    |
| `idea` | 想法 / 灵感 / 项目构思       | 「用 XX 技术做一个 YY 工具」      | `plans.md`    |
| `misc` | 无法判定的兜底，加备注       | —                                 | `plans.md`    |

### domain 判定

从现有 `collection/` 目录的页面名匹配（`dev-tools` / `ai` / `database` / `media` /
`monitor` / `frontend` / `languages` / `game-dev` / `maps` / `emoji`）。

- 用 tags + 内容判断：包含 AI 关键词 → `ai`，包含 SQL/DB → `database`，包含 CLI/tool → `dev-tools`
- 仅对 `link` / `book` / `note` 类型生效；`todo` / `idea` / `misc` 类型全进 `plans.md`，不匹配 domain

### 去重规则

- **主 key**：URL（在目标页面全文搜索 `https?://` 链接行）
- **次 key**：标题关键词模糊匹配
- **范围**：只搜索目标页面（`<domain>.md` 或 `plans.md`）

### 追加格式：资源型（link / book / note → `<domain>.md`）

| type   | 格式                                 | 位置                                  |
| ------ | ------------------------------------ | ------------------------------------- |
| `link` | `- [<title>](<url>) — <description>` | 主列表末尾                            |
| `book` | `- 📖 <title> — <author>`            | `### 📚 Reading` 小节（不存在则新建） |
| `note` | `- 📝 <title> — <summary>`           | `### 📝 Notes` 小节（不存在则新建）   |

### 追加格式：行动型（todo / idea / misc → `plans.md`）

| type   | 格式                       | 位置                                |
| ------ | -------------------------- | ----------------------------------- |
| `todo` | `- <date> <task>`          | `### 📋 TODOs` 小节（不存在则新建） |
| `idea` | `- 💡 <title> — <context>` | `### 💡 Ideas` 小节（不存在则新建） |
| `misc` | `- <content>`              | `### 📦 Misc` 小节（不存在则新建）  |

**追加规则**：

- 如果目标小节已存在，在新一行追加到该小节下
- 如果不存在，在文件末尾创建新小节，小节之间空一行
- 不修改已有内容（不重排、不编辑）

### 追加示例

给 `collection/dev-tools.md` 追加 link：

```markdown
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Feature-rich YouTube downloader
```

给 `collection/scraps/plans.md` 追加 todo（在 `### 📋 TODOs` 小节下）：

```markdown
- 2026-08-18 看下这个视频 https://www.youtube.com/watch?v=1VzSmQ6QLCw
```

## 约束

- **并发**：整理前检查 `collection/index.md`「上次整理」，若当天已整理过，先提醒
  「今天已整理过，确定再整？」
- **纠错**：整理产出是**建议稿**，只列存疑项；尊重已有内容（不覆盖、不「纠正」）
- **来源**：来源未知标「未知来源」，**绝不编造**
- **归档即清理**：处理后条目直接从 inbox 删除
- **无日期兜底**：inbox 里没日期的行记为整理当日，汇报时列出确认
- **追加不重排**：追加后不重新排序、不整理已有内容；保持原有手工编辑顺序
- **plans.md 可随意删除**：TODO 做完或放弃后直接删行，不需要归档
