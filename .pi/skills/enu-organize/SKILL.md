---
name: enu-organize
description: "English Scraps: collect, organize & review English learning scraps. Trigger words and full workflow in the body."
---

# English Scraps（enu-organize）

把日常英语碎片（生词 / 语法 / 难句 / 搭配）从 `scraps/inbox.md` 整理归档到
`scraps/archive/` 下的按周文件（如 `scraps/archive/2026-w33.md`）。所有路径在
`docs/notes/research/topics/english/scraps/` 下。

| 触发词         | 动作                     |
| -------------- | ------------------------ |
| `add <内容>`   | 追加一条到 inbox         |
| `arch`         | 批量整理归档（8 步流程） |
| `quiz [范围]`  | 出 5–10 题复习并批改     |
| `review <tag>` | 筛出该 tag 的卡片        |

> 本 skill 即 enu 系列，动作用英文：`add` / `arch` / `quiz` / `review`。

## 1. 记录（add \<内容>）

1. 追加一行 `YYYY-MM-DD <内容>` 到 `inbox.md`（今天日期自动补；多行内容折叠为一行）
1. 文件不存在时先建 frontmatter（`draft: true` + `title: English Scraps Inbox` + 格式说明注释）
1. 完成后简短确认（如「已记：cumbersome」），不啰嗦

## 2. 归档（arch）— 8 步

触发条件（满足任一即可）：inbox 行数 ≥ 15 条 / 距离上次整理 ≥ 2 周 / 用户主动。

1. 读取 inbox 全部条目
1. 逐条判定 `type`（见下），无法判定 → `misc` + 备注
1. **去重**：key = `type:关键词`（规范化：小写、空格变连字符），在
   `scraps/archive/*.md`（所有周文件）搜索 `### <关键词>`：
   - 存在 → 在原条目下追加「新语境」「新来源」（保留原 `status`，不覆盖）
   - 不存在 → 在目标周文件末尾新建条目，`status: new`
1. 按模板补全（word 查 IPA / 词性 / 词典义（中文含义 + **英英释义**）/ 例句；难句做
   结构拆解；语法点给规则 + 例句 + 易错点；搭配给含义 + 例句 + 替换；可顺手补「记忆」
   ——词根/词源/助记，见模板注释）
1. 写入归档：按条目 `date` 所在 ISO 周确定周文件 `scraps/archive/<YYYY-www>.md`
   （如 `2026-w33`；周数按条目日期算，不是今天：macOS 用
   `date -j -f "%Y-%m-%d" <date> +%G-W%V | tr 'A-Z' 'a-z'`，GNU 用
   `date -d <date> +%G-W%V | tr 'A-Z' 'a-z'`，输出即小写 `2026-w33`）：
   - 文件不存在 → 新建（frontmatter：`hide: navigation` + `title: English Scraps Archive <周>` + `tags: [english, archive]` + `categories: [dev]`）
   - 条目追加到文件末尾，不维护文件内索引；周文件天然小，无旧版 5000 行拆分规则
   - 一次归档跨多周时，各条目按各自日期落进对应周文件
1. **归档后删除**：从 inbox 删除已处理条目（不保留、不建处理日志）
1. 更新 `scraps/index.md` 的「上次整理：YYYY-MM-DD」，并把新周行追加到
   `scraps/archive/index.md` 的「归档列表」（一行/周，已有周不重复、不计数；
   手动整理后也应更新）
1. 汇报：本次归档 N 条（按 type 分组）+ **存疑项清单**（misc / 来源未知 / 疑似重复 /
   释义不确定），只请用户确认这些

### type 判定

| type           | 判定                                                              |
| -------------- | ----------------------------------------------------------------- |
| `word`         | 单个词或复合词（词典有独立词条），如 cumbersome, state-of-the-art |
| `phrasal-verb` | 动词 + 介词/副词组合（整体含义≠字面叠加），如 come up with        |
| `collocation`  | 名词/形容词习惯搭配，如 heavy rain                                |
| `idiom`        | 固定习语（含义不可拆分），如 by and large                         |
| `grammar`      | 时态/语态/从句/虚拟语气等规则，如 would have done                 |
| `sentence`     | 完整句子需结构拆解                                                |
| `misc`         | 无法判定，加备注                                                  |

### 去重规则

- key = `type:关键词`（带 type 防跨类型撞名，如 `phrasal-verb:come-up-with`）
- 关键词规范化：小写、空格变连字符
- 拼写变体（state of the art / state-of-the-art、colour/color）：判定同一表达时
  合并建卡，卡片里记录别名
- 只搜 `scraps/archive/` 下的所有周文件（跨周查重），不搜其他目录
- 同词不同词性默认合并（多「含义」条目），想拆开用户手动拆
- 与 HK 主题词汇（`hollow-knight/` 各页）不强制互查；记得见过可加
  `related: hollow-knight/...` 引用，不合并

### 条目模板

```markdown
### cumbersome

- **type**: word
- **date**: 2026-08-08
- **source**: 技术文档（Kubernetes 官方文档）｜未知来源（可含 URL）
- **status**: new
- **tags**: [technical, adjective]（固定词表：technical / informal / formal / adjective / verb / idiom…）
- **发音**: /ˈkʌmbəsəm/
- **含义**: 笨重的；繁琐的
- **英义**: difficult to handle or deal with because of complexity or size
- **记忆**: 词根 cumber-（阻碍）+ -some → 阻碍多多的；简单词可不写
- **语境**: 指代码实现难以维护
- **原句**: The implementation is cumbersome to maintain.
- **造句**: ...
- **同义/反义**: unwieldy / handy
```

- `###` 标题：word/phrasal-verb/collocation/idiom/grammar = 关键词本身；
  sentence = 截断加省略号（去重 key 仍用完整句首词串）
- `英义`（英英释义）适用 word / phrasal-verb / collocation / idiom，**必填**；
  grammar / sentence 不强制（grammar 给规则，sentence 给翻译）
- `记忆`（词根/词源/助记法）**选填**：对记忆有帮助才写；特别简单的单词/词组
  （如 cat、run、by the way）不用写
- 其余字段按 type 选填：grammar 用 规则/例句/易错点；sentence 用 结构拆解/翻译/
  难点/仿写；搭配类用 含义/例句/替换/易混/对比

## 3. 出题（quiz [范围]）

1. 范围缺省 = 最近一次整理涉及的所有周文件；可选：`<tag>` / `最近 N 条` / `全部`
1. 出 5–10 题（英译中 / 中译英 / 填空 / 选词，从范围内卡片出）
1. 用户作答后批改，指出错误并给出正确表达

## 4. 复习（review <tag>）

1. 先扫 `scraps/archive/*.md`（所有周文件）现有 tags，给出可选项
1. 筛出该 tag 的卡片列表（标题 + 一句话提示），供用户浏览回忆

## 约束

- **并发**：整理前检查 `scraps/index.md`「上次整理」，若当天已整理过，先提醒
  「今天已整理过，确定再整？」
- **纠错**：整理产出是**建议稿**，只列存疑项；尊重 archive 周文件已有内容（用户手改过
  的不覆盖、不「纠正」）；改 type 时同步改 `###` 标题
- **来源**：来源未知标「未知来源」，**绝不编造**
- **归档即清理**：处理后条目直接从 inbox 删除
- **无日期兜底**：inbox 里没日期的行记为整理当日，汇报时列出确认
