---
title: E-Commerce Bench 笔记
tags: [reading, e-commerce-bench, notes]
categories: [reading]
hide: [navigation]
---

# E-Commerce Bench 笔记

## 笔记

### episodic vs continuing tasks（RL 任务二分作为基准设计坐标）

- **定义**: episodic 基准设一个终态目标、按最终交付物打分（SWE-bench 修 issue、OSWorld 操
  作真实 OS、GDPval 由专家给知识工作评分）——任务一结束评测即结束，测不出 agent 在动态环境
  中跟踪数百子任务依赖、从意外失败恢复、用累积历史优化后续行动的能力；continuing 基准无
  终态、按累积结果计分（交易组合、自我进化 agent、经营模拟），E-Commerce Bench 属于后者
- **出现章节**: part-0001、part-0002
- **关联**: continuing 情境会暴露长 horizon 特有的失败——失去连贯性、无法把经验变成更好的
  决策（part-0003 的核心观点），这正好是 AnchorRatio 要量的东西

### 确定性谈判内核 + two-layer supplier design（reproducible 的关键）

- **定义**: 供应商拆两层：Layer 1 内核用显式讨价还价策略决定每个价格/让步/接受-放弃（参数
  来自数据层，同 (supplier, SKU) 会话的随机流由 seed 固定）；Layer 2 NPC renderer（小型
  非推理 LLM）只把内核决定渲染成对话，接受价必须与内核报价差 ≤ ±0.005 才算数。防的是纯 LLM
  对手的双重问题：抽样让价格 run 间漂移 + 模型可被说服到地板以下（把基准变成 jailbreaking
  竞赛）
- **出现章节**: part-0003、part-0009、part-0013
- **关联**: 理念来自 TERMS-Bench 的 rule-based counterpart 设计（Zhang et al., 2026a），本文
  把它从 sampled regimes 扩到 data-grounded floors、重复跨供应商谈判；是对 Vending-Bench 系列
  「LLM 供应商」路线的直接反拨
- **延伸**: TERMS-Bench arXiv:2605.13909；Vending-Bench arXiv:2502.15840

### 三账户延迟结算（three-account deferred settlement）与营运资金

- **定义**: 钱在三个桶之间流动：bank（所有成本当日扣）、escrow（发货后毛额 × 0.98 入账、
  9 天后到期）、platform wallet（只有显式 withdraw 才回到 bank）。退货从所属 escrow 批次扣，
  永不触碰可花现金。含义：卖货盈利但钱留在 wallet 里仍可能死——连续 10 个早间负余额即破产
  （90 场里 2 场 GPT-5.5 第 17 天破产，当时还没有一分钱 revenue 结算）
- **出现章节**: part-0003、part-0008（结算 13 步）、part-0010（solvency 指标）
- **关联**: 早间结算先扣成本后认收入 → 每天 08:00 是偿付能力低点；销售按前一日 08:00 留存
  的库存与定价结算 → agent 控制的是一个滞后一天的系统
- **延伸**: 类比真实电商平台的资金延迟与账期风险（收货确认、担保交易）

### context management + persistent memory（harness 层公平化）

- **定义**: 统一 128,000-token 预算（本地 tokenizer 计量，所有模型同一标准）；超过 120k 触发
  eviction，按「组」（一条 assistant 消息 + 其全部工具结果）从最旧开始清，目标释放 60k；
  system 提示、首个 user turn、最新两组永不清。持久记忆是环境里最多 20 条的笔记库，驱逐够
  不着，由 agent 自行增删改查——读回便宜（分钟）但贵（token），逼 agent 自己决定保存什么
  战略知识（历史成交价、可疑供应商）
- **出现章节**: part-0003（3.2）、part-0006（A.2 详细算法）、part-0004（eviction 与学习缺陷
  的关联）
- **关联**: 90 场共跑 1,495 次驱逐；traffic 越大丢得越多（Gemini 3.5 Flash 2,628 turns ≈ 19
  个窗口被丢，Claude Opus 4.7 432 turns ≈ 4 个）。被驱逐的工具结果带走「已赢得的低价」——
  论文把 eviction、memory 少用、episode 内无梯度列为压平跨半年学习趋势的三个机制

### 多维评测（multi-dimensional metrics）——主分数之外的六轴

- **定义**: 期末总资产（asset multiplier）只排主序；旁边六维各用**一个带方向的数**排序：
  negotiation = CSE+（closed honest deal 捕获 ZOPA 比例）；fraud avoidance = BadSpend%
  （流进欺诈供应商的采购金额占比，越低越好）；solvency = peak drawdown / peak total assets
  （归一化回撤，大生意同纪律不同绝对额）；efficiency = 利润/工具调用数（ratio of means）；
  execution = controllable return rate（自己定价在自然退货率之上加的点数）；learning =
  AnchorRatio（重复采购相对自身洗牌 null 的超付比）。雷达图显示 6/7 个代表模型至少在一轴上
  低于 18 模型 median
- **出现章节**: part-0003（§3.7）、part-0010（Appendix E 全部口径）、part-0004（结果）
- **关联**: 单轴排序会翻车——「最能赚钱的既不是最佳谈判者也不是最高效运营者」；
  F.8 统计 18 模型平均跨 7 轴排位跨度 10.2/18，153 对模型在 7 次转轴中有 311 次次序反转

### AnchorRatio / AnchorRegret 与长程学习缺陷（全文最有信息量的负结果）

- **定义**: 对同 (honest supplier, SKU) 多次成交的对，把每次成交价放进该对的 ZOPA 位置 π，
  第 2 笔以后对比「自己已赢得的最好价」算超付 AnchorRegret，再除一个把各对价格次序打乱的
  permutation null（B=400）得 AnchorRatio——1.0 = 与随机打乱无差别。结果：字段 median
  1.369，只有 Qwen3.8-Max-Preview（0.834）与 Gemini 3.5 Flash（0.918）优于随机；16/18 的
  下半年每场捕获的 surplus 少于上半年（Qwen3.8 是唯一 per-day 趋势为正、唯一超 2σ 改善者）
- **出现章节**: part-0003（3.5.5）、part-0004（4.3.6）、part-0010（E.6）
- **关联**: 机制上三者无法区分——eviction 毁掉记录、memory 几乎不用、episode 内没有梯度信号；
  与 anchoring bias（LLM 被自己的早期报价锚定，Lou & Sun 2026 / Takenami et al. 2025）
  一致；这也是「单次会话谈判技能 vs 全年累积学习」分离得最干净的一维
- **延伸**: Lou & Sun, Anchoring Bias in LLMs (2026)；Takenami et al., EMNLP 2025 Findings

### 欺诈谱系（5 scams）与「叙述是唯一事前信号」

- **定义**: 576 供应商里 152 个欺诈（每类目 ≥2 个，覆盖全产品线）。pre-deal 类（vip_fee /
  future_discount / fake_urgency，共 92 个）把保留价抬到约 1.5× 诚实地板，但仍在诚实报价
  区间内 → 只能靠叙事识破；post-deal 类（qty_bait / quality_downgrade，共 60 个）用诚实
  地板成交后短发（实付 60–70% 货量）或发次品（退货率 ≥0.40 或 2 倍自然率、cap 0.95，混合池
  稀释证据）。行为上欺诈内核让步率（0.79%–1.66%/轮）远低于诚实模板（3.94%–9.93%），这是
  谈判形状里唯一的统计信号；接受过早 = 放弃唯一的讨价还价侧线索
- **出现章节**: part-0003（3.5.4）、part-0009（D.5）、part-0012（三个骗局实录）
- **关联**: 大部分损失发生在成交后（defective lots 占欺诈损失的 53.4%）；重复复购最危险
  （与欺诈供应商的 1,141 笔成交里 943 笔在二次及以后）——欺诈识别本质是长程记忆 + 跨会话
  供应商画像任务

### ZOPA 与不完全信息讨价还价（经济学骨架）

- **定义**: 公开 reference price vj（agent 转售价锚）与供应商私有成本地板 cs_j（隐藏）之间的
  区间 = zone of possible agreement；一单成交在位置 π 上把 (vj − pz)·qz 分给 agent。会话按
  (supplier, SKU) 开启新内核实例但保留持久类型与保留价 → 跨会话推断保留值（Baarslag et al.
  2016）成为任务本身；「已赢得的最好价」是地板的上界且只会收紧，但 pre-deal 欺诈的地板是
  故意抬高的——锚定在错误对象上同样危险
- **出现章节**: part-0003（3.5）、part-0009（D.1 决策函数）、part-0010（E.1）
- **关联**: 让步速度是互惠的（kernel 的让步随 agent 让步速度收紧）→ 快速让步在模拟与现实
  谈判里同属劣势；接受开场报价即 0.50 分基线，CSE+ 高于它的部分才是真谈判技能
- **延伸**: Raiffa (1982)；Rubinstein (1982)；Chatterjee & Samuelson (1983)；Baarslag et al.
  2013/2014/2016

### 需求模型与自我蚕食（capacity saturation）

- **定义**: SKU 日需求 = 类目基数 × 6 个乘子（价格响应、周末、促销、季节、当日事件、声誉）
  再被两个容量项（类目天花板、店铺天花板，Michaelis-Menten 形式 κ/(κ+D)）截断，最后受架上
  库存约束。四种弹性族里 quadratic 关于 reference 对称 → **过度打折反而丢需求**；容量项可
  能主导一切（某配饰 SKU 促销周六的复合期望 128.2 件被截到 9 件，类目项单杀 7.5×）——堆同质
  SKU 是互相蚕食而非叠加销量
- **出现章节**: part-0003（3.4.3）、part-0008（C.2 公式）
- **关联**: 定价是高杠杆操作但调用占比仅 0.66%（9/18 模型全年平均 \<3 次改价），季节/促销/声誉
  在底下动需求而货架价不动 → 执行维度的核心浪费

### 系统性信息不对称与「可读性泄漏」

- **定义**: agent 看得到目录与自身行为结果，看不到决定行为价值的参数：成本地板（0.17–0.90 ×
  reference）、弹性族、自然退货率、店型容量上限都要靠工具动作去发现，且每个发现都被定价
  （分钟 / 现金 / 不可逆损失）。论文自曝两处泄漏供读者核验：20/60 类目的退货话术低估数值带
  （占 25.5% SKU）；supplier 邮箱后缀按诚实/欺诈分组可排序 → 理论上不发一条消息就能筛掉欺诈
  供应商（§F.3 是否被模型利用未下结论）
- **出现章节**: part-0003（3.6.2）、part-0007（B.5）、part-0008（Table 7）
- **关联**: 每个隐藏参数的学习速度不同——地板可用成交价上界逼近、自然退货率买过才可见、
  弹性全年不可分（四个未打印因子乘在同一观测上）→ 一年奖励的是「分配探索」而非「耗尽探索」

## 重要参考

- 论文原文（HTML 版）: https://arxiv.org/html/2608.30730v1
- 论文 abs 页（作者/投稿信息）: https://arxiv.org/abs/2608.30730
- TERMS-Bench（Zhang et al., 2026a，内核设计出处）: https://arxiv.org/abs/2605.13909
- Vending-Bench（Backlund & Petersson, 2025）: https://arxiv.org/abs/2502.15840
- MerchantBench（Shi et al., 2026）: https://arxiv.org/abs/2607.28956
- RetailBench（Zhang et al., 2026c）: https://arxiv.org/abs/2603.16453
- YC-Bench（He et al., 2026）: https://arxiv.org/abs/2604.01212

## 待查线索

- **作者与机构**：提取文本缺标题页，作者列表取自 arXiv abs 页；文中「our own Qwen3.8-Max-
  Preview」与作者中的 Dayiheng Liu 提示与 Qwen/阿里相关，机构与署名顺序待与 arXiv 页面核对
- **模型时效性**：被评 18 个模型（GPT-5.6 Sol、Fable5、Claude Opus 4.7/4.8、Qwen3.8-Max 等）
  与 2026-08 的版本状态绑定，阅读时点（2026-09）能力已可能变化；引用榜单数字前建议回到
  当时报告
- **样本量与排名噪声**：每模型仅 5 episode、90 场里 10 场破产被并进均值；BadSpend% 的
  episode 间 std 对 15/18 模型超过均值本身——单轴排序的稳定性值得警惕
- **邮件泄漏是否被利用**：B.5 指出 supplier_search 的邮箱后缀可按诚实/欺诈分组；论文只在
  §F.3 提示 contact 阶段会显示效果，未给出结论——可回看 §F.3 细表判断是否有模型 exploit
- **AnchorRatio 假设**：null 假设各对周期难度相同（地板/批发价确为 SKU 常量，开场报价每周期
  重抽且未存档）；per-unit 口径不反映现金后果；fraud 对按构造排除——这些边界决定指标能说
  什么、不能说什么
- **「话术低估退货带」的动机**：B.5 泄漏 1 看起来是真实平台的「残差失真」被刻意保留以模拟
  现实误导信息——值得对照 real-world 平台标注质量问题评估其合理性
- **efficiency 维度的盲区**：经济体内不向调用/token 收费，efficiency 是部署成本代理而非
  模拟内成本；结合 BFCL 式美元成本/延迟报告（Patil et al., 2025）才是完整画像
