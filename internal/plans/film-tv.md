---
title: Film & TV Archive (Douban Sync)
created: 2026-09-27
tags: [mkdocs, archive, douban, sync, media, r2]
---

# Film & TV Archive (Douban Sync)

## Goal

把豆瓣上的影视记录（**看过 / 在看**，不含「想看」）同步归档到本站，产出浏览页与统计：

- 数据：豆瓣收藏列表（状态 / 打分 / 短评 / 标记日期 / 标签）+ 条目页元数据（上映年、类型、
  地区、语言、片长、导演/演员/编剧、集数）+ **封面候选**（默认 1 张主海报，多条候选按需补抓，
  用户可自选主封面）
- 存储：**按观看年分文件的 yml**（**实测 4292 条 = 看过 4292 + 在看 0**，约 250 条/年 ——
  4292 ÷ 17 年，机器字段与人工字段按块分离）
- 展示：`index` / `movies` / `tv` / `people` 四个页面，**存储按年、展示不按年**（默认「从近到老」
  连续列表 + 日历/年月选择器 + 筛选/排序）
- 统计：总量与年度/类型/地区分布、**导演/演员榜单**（重点指标）
- 封面：本地 WebP → R2 独立目录（`data/film-tv/`，目录可配置）

条目数**阶段 0 已回填**：看过 **4292**、在看 **0**（2026-09-27 全量列表走查：翻页得 4292 个唯一
id = 页面总数，0 重复；`type=movie` 3092 + `type=tv` 1200 = 4292）。原「约 8000」是含「想看」的
估数，本计划不含想看；封面预算据此校准：首刷默认 1 张 ≈ **0.3GB**，补到 3 张 ≈ **0.9GB**
（实测 72KB/张 @ WebP q80 / 长边 800）。**账号调用面收窄**（降封号风险）：列表走查匿名（账号零
调用）、封面默认取自条目页主海报（零额外请求），详见 design §1.1/§5。

内容中文、代码英文；站点为公开 GitHub Pages，**评分、短评与个人影评默认全部公开**（单条可用
`user.hidden` / `user.hidden_comment` 关闭）。

## 范围与非目标

**范围**

- 豆瓣列表里的**全部影视条目**（电影 / 剧集 / 综艺 / 动漫 / 纪录片），不做类型过滤：
  `type: movie|tv`（豆瓣条目大类）+ `category`（与 type **正交**，用于统计）
  - `category: feature | series | variety | anime | documentary | other`
    （feature=电影长片，series=剧集，variety=综艺，anime=动漫，documentary=纪录片；认不出落 other）
  - 映射约定：电影 → `feature` / `documentary` / `anime`；剧集 → `series`；综艺 → `variety`
- 短评（`douban_comment`）有就记录；**不归档长评正文**
- 同步**完全由用户手工触发**（`poe sync-film-tv`），**不做定时任务**（不装 launchd / cron）
- 首次全量由用户**手动分批**推进（`--limit N`，建议 300 条/批，`--limit` 计的是**详情抓取条数**），
  列表先一次全量落

**非目标**

- 豆瓣社交数据（广播 / 关注 / 小组）、在线播放 / 资源索引
- 「想看」列表（`wish`）：不归档、无 `wish.yml`
- 自动登录（豆瓣登录页有滑块验证，只能 Cookie）
- 多用户 / 服务化
- **一条目一个 `.md`**（条目合并进年份数据文件，也不生成「年份页面」）
- 长评正文归档、Excel 等导出格式

## 关键设计（已搬到 design 文档）

`## 关键设计（已定）` 整章已搬进 [`film-tv-design.md`](../film-tv-design.md)（长期设计文档），
并按**阶段 0 spike 实测**做了修正。此处只保留结论指针与偏差清单，避免两份长期重复、漂移：

- 数据模型 / 存储与展示解耦 / 增量同步 / 登录与 Cookie / 封面与 R2 / 判定规则 → design 文档 §2–§6
- **实测修正（与本章原稿不同，详见 design §7）**：
  1. 列表页**已不再提供短评** → 指纹改为列表可得字段（`title/user_rating/marked_at/status/type/tags/comment(仅在看)`），
     看过的短评/标签只能从条目页取；`--refresh-details [N]`（**已确认加入**）批量补抓
  1. 条目数**实测 4292（看过）/ 0（在看）**，不是约 8000；封面预算：首刷 1 张 ≈ **0.3GB**，
     补到 3 张 ≈ **0.9GB**
  1. **封面路径按豆瓣 id**（`covers/<douban_id>/NN.webp`，2026-09-27 改；`slug` 只留给 `?id=` 分享
     链接）—— 不再需要 slug 撞名升级/退化判定
  1. **账号调用面收窄**：列表走查改用**匿名 session**（实测条目数据与登录态逐字段一致）；
     封面默认只取条目页 `#mainpic` 1 张（零额外请求）；多候选改按需；条目页/相册页仍需
     登录态（匿名 302 `sec.douban.com`）
  1. 登录闸门用 `/mine/`（`/people/` 恒 404、匿名 `/mine/` 403）
  1. 列表 `deleted` 行 = 条目被豆瓣删除 → 直接写 `meta.missing_since`
  1. 列表按 `?type=movie|tv` 两遍走（页数相同，顺带拿到 `type`）；`category` 由 genre 判定
     （综艺实测可能落在 `type=movie`）
  1. `seasons` / `episode_progress` 实测不可得 → 恒 `null`
  1. YAML 写回用 PyYAML + 自定义 dumper + `user:` 块原文拼接（**不需要 ruamel**）

## Tasks

- [x] **阶段 0：技术验证（spike，先行）** —— ✅ **全部完成（2026-09-27）**，结论见
  [`film-tv-design.md`](../film-tv-design.md) §1（实测：4292 条 / 在看 0；列表页已无短评；
  `deleted` 行；`/mine/` 闸门；封面 72KB/张 → 0.9GB）

  - [x] 列表页解析：`/people/<id>/{collect,do}?start=N` 分页、每页条数（`mode=list` 30 条）、
    结束标志（超末页返回 200 + 0 条）；`type` 由列表 tab 定、`category` 由条目页 genre 定；
    抽 10 条核对（9/10 一致，1 条是已删除条目）；**总量交叉验证 ✅**：翻页得 4292 唯一 id =
    页面总数 4292，0 重复，且 `type=movie` 3092 + `type=tv` 1200 = 4292
  - [x] 条目页字段提取规格：info 块、`credits`（导演/主演/编剧）、片长、首播、地区/语言、
    `douban_score` / `douban_score_count`、集数；10 条样本覆盖率已记录（design §1.3）
  - [x] 相册页 `photos?type=R`：30 张/页、`共N张`、默认「按喜欢排序」、`m`/`l` 两种尺寸
  - [x] CDP 取 cookie 打通：`shared/douban_auth.py` + `scripts/film_tv_login.py`
    （`poe film-tv-login`），已用扫码登录实测跑通并落盘 0600；失败分支（端口非浏览器、超时、
    取不到 cookie、`--manual` 兜底）已实现
  - [x] YAML 写回验证：PyYAML + 自定义 dumper + `user:` 块原文拼接；已验证保键顺序、
    `user:` 块逐字节不变、粘性字段保留、无变化不落盘、只改动的机器行产生 diff
  - [x] **依赖决策**：`websocket-client` 进主依赖（`shared/douban_auth.py` 内懒加载）；
    **`ruamel.yaml` 不需要**；`pyproject.toml` + `uv.lock` 已更新
  - [x] **结论落文档**：字段规格 / `type`+`category` 判定规则 / 失败模式 → `internal/film-tv-design.md`

- [x] **阶段 1：登录 + 同步（数据落地）** —— ✅ 完成

  - [x] `scripts/film_tv_login.py` + `poe film-tv-login`（CDP attach/拉起、取 cookie、`--check`、
    `--manual` 兜底、`--browser edge|chrome|auto`、`--cdp-port`、`--user-data-dir`）
    —— spike 阶段已实现并实测（保留在阶段 1 复核：失败分支细节 / 文档）
  - [x] `scripts/sync_film_tv.py` + `poe sync-film-tv`（列表 -> 增量短路 -> 详情队列 -> 合并写回；
    `--limit N`（默认 50，0 = 不限）、`--pages M`、`--full`、`--prune`、`--covers N`、`--only <slug>`、
    `--refresh-details [N]`、`--dry-run`）；**列表匿名走查 + 被挑战时自动回退账号会话**；
    骨架记录先落（每行一条），详情批次再补
  - [x] 年份文件写入：`movies-<年>.yml` / `tv-<年>.yml`，稳定排序（观看日期倒序 + id）、
    粘性字段保留、`user:` 块逐字节保留、原子替换、空文件清理、文件头 `generated_at`
  - [x] `docs/notes/film-tv/data/taxonomy.yml`（地区别名 → 规范短名 + `category` 归类规则 +
    统一 `rules_version`）与 `regions` / `category` 归一化
  - [x] 增量状态与详情缓存：`.cache/film-tv/state/`（详情 JSON、封面 photo_id→key 映射、失败列表），
    可断点续跑；每 50 条详情/每 200 行列表 flush 一次
  - [x] 封面下载：**默认只存 1 张（条目页 `#mainpic` 主海报，零额外账号请求）**；
    `--covers N > 1` 才抓相册页拓候选；跳过已存在、WebP 转换用**封面专用参数**
    （`extra.film_tv.cover_max_dimension` 默认 800 / `cover_quality` 默认 80；**不复用**全局
    `optimize_images`）；CDN 请求带 `Referer`（否则 418 防盗链）
  - [x] 会话分流：列表走查用**匿名 session**（账号零调用，实测数据一致），详情/相册用账号
    session；匿名被 `sec.douban.com` 挑战时自动回退带 cookie 并告警（首刷全量会触发）
  - [x] `scripts/film_tv_check.py` + `poe film-tv-check`：键格式与 slug 校验（不查本地文件存在）、
    `watched_at` 与年份一致、`slug` 全局唯一、`hidden` / `hidden_comment` 未泄漏到页面/JSON、
    `meta.machine_hash` 与机器字段一致（手改告警）、`meta.taxonomy_version` 过期清单、
    `base_url` 与 `remote_prefix` 一致、无日期条目待补清单（分「待补详情 / 已下架被跳过 / 需手填
    `user.watched_at`」三类）、未抓详情计数；
    支持 `--only <slug>` / `--since <date>` 只校验刚补的一批；`--check-remote` 才查 R2 上的文件存在 /
    孤儿封面（**缺 rclone/R2 凭据时跳过并提示，不报错、不误报孤儿**）；`--data-quality` 输出固定
    格式报告并落 `.cache/film-tv/reports/`
  - [x] `shared/bucket.py` 扩展 + 配套单测（`name` / `find_mapping` / `pick_mapping` / 按名
    `base_url` 覆写；`--mapping` 进 upload / sync / check；`bucket-sync --local-prefix`）
  - [x] 单测：解析（HTML fixture × 6，含 `item last` / 未评分 / 已删除 / 在看短评）、增量指纹、
    YAML 保序合并、粘性字段、路径安全、taxonomy 与 `category` 判定、重试/反爬分支、封面转换、
    bucket 配置一致性与 `--mapping` 选路（`tests/test_film_tv_*.py` + `tests/test_sync_film_tv.py`）

- [x] **阶段 2：页面（存储/展示解耦）** —— ✅ 完成（首屏与标签筛选后来按开发者要求改成
  按月翻页 + 去掉标签筛选，见 design §3）

  - [x] `docs/notes/film-tv/index.md` / `movies.md` / `tv.md`（导航已挂这 3 个页面；
    `people.md` 到阶段 3 创建时再加）

  - [x] `shared/macros/film_tv_macros.py`（+ `shared/macros/loader.py`，因为 mkdocs-macros 只接受一个
    本地 `module_name`）：构建期渲染容器 / 统计 / 提示，**不写 `docs/`**（无构建副作用）

  - [x] 生成分片与月份索引（`docs/notes/film-tv/assets/`）：`scripts/film_tv_derive.py` +
    `poe film-tv-derive`（连 `stats.yml` / `people.yml` 一起出）；确定性输出、内容不变不落盘、
    剔除 `hidden`（`hidden_comment` 去掉 `comment` 字段）、`count`/`first_date`/`last_date` 自检、
    过期分片自动删除；**派生文件一律全量重算**，不做局部 patch

  - [x] 同步尾部接入：`run_derive_hook()` 在每次同步（含 `--only`）结尾调用
    `scripts/film_tv_derive.py`（缺失时跳过并提示）

  - [x] 默认「从近到老」连续列表 + 月时间轴分隔；首屏 60 条，滚动/按钮续片

  - [x] 日历（自研月份格 → 观看月区间）/ 年份跳转；排序 4 种 + 筛选（`type` / `category` /
    地区 / 上映年代 / 我的评分下限 / 我的标签 / 搜索 / 月份区间）

  - [x] 条目卡片/弹窗（封面 + 元数据 + 豆瓣短评 + `user.review`），缺封面降级、`loading="lazy"`、
    `?id=<slug>` 深链

  - [x] 封面路径：derive 把完整 `base_url + key` 写进 JSON（运行时 fetch 拿不到构建期改写），
    换 bucket 域名需重跑 derive（design §3 已记）

  - [x] `mkdocs.yml` nav（Film & TV 分组：index / movies / tv）、Notes 首页 mermaid 导航图、
    `docs/notes/collection/media.md` 引流入口

  - [x] `exclude_docs` 新增一行（`mkdocs.yml` 现有 `exclude_docs: |` 块里追加）：

    ```yaml
    exclude_docs: |
      notes/health/_summary.md
      notes/film-tv/data/        # 原始 yml 不发布（~2–4MB）；宏仍可从磁盘读取（同 _summary.md 先例）
    ```

    `docs/notes/film-tv/assets/*.json` **不排除**（前端要 fetch）；归档页是否排除出搜索

  - [x] **构建实测（60 条样本基线）**：`mkdocs build` 6.6s；单页 HTML 47–53KB（前端渲染，
    **不随条目数增长**）；分片 ≈ 750B/条 → 4292 条约 3.2MB；`site/` 35MB。**4292 条的真实基线
    留到阶段 4 全量后复测**（分片总量若明显偏大，可选后续改走 R2 拉取）

- [x] **阶段 3：统计与影人榜单** —— ✅ 完成（AI 总结的自动写入已接；「个人分 vs 大众分对比图」不做）

  - [x] `data/stats.yml`（总条目数、总时长、按年观影量、`type`/`category`/地区 top N、平均分
    （基于 `effective_rating`，同时记录“已评分 N/M”）、`data/people.yml`、分片/月份索引 全部由
    **同一个派生脚本** `scripts/film_tv_derive.py` + `poe film-tv-derive` 生成
    （覆盖：stats + people + JSON 分片；**同步结束后自动调用**），并打印**哪些派生文件变化**
    （`write stats.yml` / `0 file(s) to write`）
  - [x] `data/people.yml`（影人聚合：`roles`（`director`/`actor`/`writer` 列表，榜单按角色筛）、
    `works`（去重条目数）、`ratings` / `avg_rating`、`first_year` / `last_year` = **观看年份**，
    不是上映年；另有 `douban_id` / `douban_url`）
    注：`works` 是**不分角色**的总数（一个人既是导演又是演员时两个榜显示同一数字）—— 暂不做按角色分别计数
  - [x] 影人目录 `data/person-ids.yml`（`personage id → 显示名`，同步追加维护）+ 影人榜带
    `douban_id` / `douban_url`；名字显示规则 `person_name_style`（原文名来自 `#celebrities`，零额外请求）
  - [x] 派生文件（`stats.yml` / `people.yml` / 分片）**确定性生成 + 内容不变不落盘**：不写任何
    时间戳/hash（比计划更严）、`sort_keys=True` + 固定分隔符、浮点统一 `round(x, 2)` ——
    实测重复运行 `0 file(s) to write`
    **过期检测**由 `poe film-tv-check` 承担（`derived-stale`：`index.json` / 分片条数与年份 yml
    不一致就报错并提示重跑 derive），代替计划里的 `source_hash`
  - [x] `people.md` 榜单页：导演 / 演员 / 编剧三个视角，Top 50；人名链接回归档（`?person=`）
    （平均分榜（作品 ≥ 3）按开发者要求**不做**）
  - [x] `index.md` 统计卡片（归档条目 / 电影·剧集 / 平均分 / 总时长 + 可折叠的分类・年份・地区・类型
    分布 + 可折叠观影量图表；「已评分」与「影人数」两张卡按开发者要求去掉 —— 前者无信息量、
    后者受 casts 前 10 截断影响）＋ AI 观影总结（`poe update-film-tv-summary`）；总结内容
    写在区块标记 `<!-- ai-summary:begin -->…<!-- ai-summary:end -->` 内，**只重写块内、不碰手工正文**

- [ ] **阶段 4：全量补齐（仅剩开发者手动执行的操作）** —— 代码侧已全部就绪
  （页面「待补」状态、数据质量报告、分批 flush、进度输出都已实现）：

  - [x] 页面显示「待补」状态（卡片角标 + 首页 `film_tv_note()` 的「还有 N 条待补详情」）
  - [x] 数据质量报告固定格式：`poe film-tv-check --data-quality` 输出缺失字段比例、重复 slug、
    孤儿封面（`--check-remote`）、未抓详情计数，并落 `.cache/film-tv/reports/<ts>.json`
    （报告头部带 `taxonomy_version`）
  - [x] 分批与进度：每批结尾打印 `details N | covers M | failed F | …` 与
    **总进度** `progress: details 1234/4292 (28.7%) | pending 3058`；每 50 条 flush 一次
    yml + 状态
  - [x] **列表全量落盘 + 分批补详情**：`poe sync-film-tv --full --limit 0`
    → 反复 `poe sync-film-tv --limit 300` 直到 `progress: 待补 0`
    （条目数已回填：**4292**；步骤见 `internal/commands.md` 场景 1/3）
    —— ✅ **已完成（2026-09-29 03:06）**：详情 **4276/4293**、`pending 0`、`gone 19`
    （19 条已下架且无日期，只能跳过）；`poe film-tv-check` = **0 error**；
    夜间分批执行（`.cache/film-tv/run_rounds.sh`，本地工具，git-ignored），
    逐轮日志在 `.cache/film-tv/logs/round-*.log`
  - [x] **首次全量走查的截断修复（2026-09-27 实测暴露）**：首刷只落了 movie 2190 + tv 1200
    = **3390**，而页头是 3092 + 1200 = **4292** —— movie 第 73 页（`start=2190`）返回空页时
    走查当成「列表到底」静默结束（漏掉最老的 ≈900 部）；事后手工请求该页正常返回 30 条，
    确认是被限流的瞬时空页。已修：空页重试 + 按页头 `total` 校验，收不齐就中止（保留进度）；
    `--full` 游标写入 `state/walk.json` 支持断点续走；`film-tv-check` 新增 `walk-total`
    完整性自检与 `local-orphan`（`--dedupe-covers` 清理）。**仍需开发者跑一次
    `poe sync-film-tv --full` 把缺少的骨架补回来**，否则按 3390 条的统计/影人榜/AI 总结都是偏的
  - [ ] **（开发者手动）封面分批上传 R2**：`poe film-tv-upload-covers [--limit N] [--confirm]`
    （上传目标 `<remote_prefix>/covers/`，与 key `covers/<douban_id>/NN.webp` 对齐）
    → `poe film-tv-check --check-remote` 校对；**上传后本地只保留近几年副本**（全量只存 R2）

- [x] **收尾**（仅剩阶段 4 的两项开发者手动操作，见上）

  - [x] `internal/film-tv-design.md`（长期设计文档；含「字段 → 归属 → 是否公开」表）。
    `## 关键设计` 整章已搬迁，计划只留 Goal / 范围 / Tasks / 验收 / 风险 / References
  - [x] `internal/commands.md` 增加命令与例行操作说明；`AGENTS.md` DEV tips 增补命令
  - [x] `internal/bucket-design.md` 记录新 mapping 与 `name` 覆写能力（含 `--mapping` / `--local-prefix`）

## 验收标准

- 增量同步：第二次运行只新增/变更的条目，请求数在个位数到十几；重复运行**不产生 diff**
- 写回：`user:` 块逐字节不变；`slug` / `covers` 不因重跑而改变；`--dry-run` 不落盘、不迁移
- 数据：年份文件只含「观看年」对应条目（**例外**：无 `marked_at` / `user.watched_at` 的条目住
  `*-undated.yml`）；`slug` 全局唯一；`regions` 是规范短名；`category` 全部取自 enum
  （无中文/自造值）
- 统计：`regions` 为多值的合拍片**在每个地区各计一次**（所以各地区计数之和可能大于条目数，
  这与“条目总数”是两个口径）
- 隐私：`hidden` 条目与 `hidden_comment` 的短评**既不在页面、也不在生成的 JSON**
- 页面：`movies.md` / `tv.md` 首屏加载可接受（最近 N 条），筛选/日历可用，缺封面降级正常
- 分片：`index.json` 与所有 `shard-*.json` 自检字段一致（不缺片、条数与 yml 对齐、hidden 已剔除）；
  故意删一片时页面**报错提示**而不是静默少显示
- 封面（**阶段 4 完成后**）：R2 上每条目目录含 1–3 张 WebP，站点构建后图片可出图
  （`poe server-bucket` 验证）
- CI：新增单测全绿，`poe fmt` / `poe lint-py` / `poe test` 通过；网络与浏览器相关逻辑不进 CI
- 无凭据泄露：仓库与 CI 中不存在 cookie、R2 密钥；日志输出掩码

## 风险与对策

- **豆瓣改版**导致解析失效：选择器集中在一处 + HTML fixture 回归测试；失败即中止并提示，不硬刷
- **风控 / 封号风险（已主动降低）**：**账号 cookie 只用于非带不可的请求**——列表走查匿名（账号
  零调用）、封面默认取条目页主海报（零额外请求）、相册候选按需抓；详情 2s / 封面 0.5s（**账号
  调用面 = 详情请求数**）；手工触发、分批推进（`--limit`）；详情缓存命中不重抓；`429/503` 按指数
  退避重试（上限 2 次），仍失败或遇验证码/403 立即中止（不硬刷）
- **Cookie 月级失效**：`--check` 启动校验 + attach 自动续期 + 失败时弹登录页人工登一次
- **数据体积**：yml 进 git（**实测待阶段 4 回填**；按 design 的一行 ≈ 0.5KB × 4292 估算约 2MB）；
  封面只进 R2：**实测 72KB/张**（q80 / 长边 800）→ 首刷 1 张/条目 ≈ **0.3GB**，补到 3 张 ≈ **0.9GB**
- **人工内容被覆盖**：同步只写机器块（`slug`/`covers` 粘性）；`meta.machine_hash` 检测机器字段被
  手改并告警，`film-tv-check` 校验 `user:` 块完整
- **只改短评不会被列表短路发现（spike 新发现）**：看过的短评只在条目页可得 → 靠 `--only <slug>`
  或待定的 `--refresh-details [N]` 补抓；已在 design §4/§7 记明
- **4292 条渲染与构建时长**：首屏 N 条 + 按需加载；阶段 2 实测构建时长，必要时把归档页排除出搜索

## Notes

- 范围说明：本计划**只覆盖影视**（豆瓣影视记录）。书 / 游戏归档（曾在仓库计划里提过）**不在本
  计划范围内**，如以后要做另行开计划
- 本计划取代了已删除的旧计划 `mkdocs-media-archive.md`；提交时 commit message 需注明
  `superseded by film-tv`，避免后人误判为误删（该文件在 git 历史中仍可查）；本计划文件名不带
  `-archive` 后缀，是为了避开与 `internal/plans/arch/` 归档目录的混淆
- 执行顺序（已确认）：**阶段 0 的全部验证项先行**（7 项）→ ✅ **已全部完成（2026-09-27）**，
  结论见 `internal/film-tv-design.md`；阶段 1 待开发者确认后开工
- **阶段 0 待确认项（不阻塞阶段 1 主体）**：
  1. 是否新增 `--refresh-details [N]`（绕过指纹短路，批量重抳最近 N 条详情）—— 用于「在豆瓣
     改了几条短评」；否则只能逐条 `--only <slug>`
  1. `category` 优先级序列（design §6：documentary > variety > anime > series/feature > other）
     —— 例如「动画剧集」会落 `anime` 而不是 `series`
  1. `credits.casts` 只存前 N 位（默认 10）
- 可后定（不阻塞开工）：分片条数（200 vs 500）、日历组件自研还是复用 moment 的 calendar、
  HTML fixture 来源与更新方式、是否要 golden file 测试、`user.review` 长文升级路径、
  `internal/commands.md` 是否加一页「归档运维」runbook
- 不做：定时任务/自动化同步、长评正文归档、想看列表、一条目一个 md、Excel 导出
- 存储位置：`.cache/film-tv/{state,browser-profile,reports}/` 与 `docs/assets/bucket/film-tv/`
  已被 `.gitignore` 覆盖（已核验）；分片/索引（`docs/notes/film-tv/assets/*.json`）是**提交进 git**
  的生成物，同样**不需要新增忽略规则**
- **文档冻结点**：✅ 阶段 0 完成后 spike 结论已回填 `internal/film-tv-design.md`，本计划只更新
  Tasks 勾选与验收数据（`## 关键设计` 整章已搬进 design）
- **阶段 0 产物**（本次提交）：`shared/douban_auth.py`、`scripts/film_tv_login.py`、`poe film-tv-login`、
  `internal/film-tv-design.md`、`.env.example` + `pyproject.toml`（`websocket-client`）；spike 临时脚本
  与原始 HTML 在 `.cache/film-tv/spike/`（git-ignored，不提交；fixture 到阶段 1 再挑进 `tests/`）

## References

- [Plan Index](./plan-index.md)
- [Bucket design](../bucket-design.md)
- [Health summary design](../health-summary-design.md)（yml 数据 + 宏 + 统计的既有范式）
- [Collection: Media](../../docs/notes/collection/media.md)
- [mkdocs.yml](../../mkdocs.yml)
