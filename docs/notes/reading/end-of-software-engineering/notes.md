---
title: The End of Software Engineering 笔记
tags: [reading, end-of-software-engineering, notes]
categories: [reading]
hide: [navigation]
---

# The End of Software Engineering 笔记

## 笔记

### 论文的三段式论证骨架

- **定义**: 核心论证链 = 传统范式复杂度不可持续（§2 第一性原理）→ agentic 范式必然
  且应消除「软件」这个中间环节（§3）→ Agentic Engineering 作为新学科 + 实证校准
  （§4–5）→ 路线图与行动建议（§6–7）。三大 central claims（First-Principles
  Necessity / Paradigm Shift Not Optimization / Emergent Discipline）贯穿其中
- **出现章节**: index、part-0001、part-0002、part-0008（结论首尾呼应）
- **关联**: 论证结构本身是「必要性 → 范式 → 学科」的递进，可用 [index.md](./index.md)
  的主线列表对照各段落

### Traditional Software S=(C, D, E) vs AI Agent A=(M, T, M, Π)

- **定义**: 两个形式化模型对照全文的轴心。传统系统里 D（决策规则集）相对执行**静态**、
  须人预先写全；agent 系统里决策逻辑由 LLM 在**运行时**生成，代码只是 transient
  artifact。本质差异 = 决策逻辑的载体从「代码」换成「模型推理过程」。注意论文自承
  定义粒度较粗（Π 规划机制、M 记忆子系统的行为细节未展开）
- **出现章节**: part-0002（Def 2.1 / 2.2）
- **关联**: 载体之变正是 §3「软件不再是必要中介」的形式化基础
- **延伸**: Wang et al. 综述 arXiv:2409.09030 有更细的 agent 分类学

### essential vs accidental complexity（Brooks）

- **定义**: 论文立论起点：五十年工程实践（语言、框架、测试）只系统性压低了 accidental
  complexity；essential complexity 无界——Proposition 2.1 给出 n 组件系统交互路径上界
  P(n) ∈ Θ(2^n)，而人类认知容量近似常数。这个 mismatch 被当作传统范式「结构性天花板」
  的证据
- **出现章节**: part-0001、part-0002
- **关联**: 天花板存在 → agentic 范式（容量随算力缩放）才成为「必然」（claim 1）；
  层级分解 / 模块化只降常数因子不改变渐近行为
- **延伸**: Brooks, The Mythical Man-Month (1975)

### Software 1.0 / 2.0 / 3.0（AaaS）与复杂度承担者

- **定义**: 三代交付形态 = complexity owner 逐级迁移：本地 license（用户承担安装/维护）
  → SaaS 订阅（vendor 承担基础设施/更新）→ AaaS 按结果付费（agent 承担理解/构建/运行）。
  规律：「最能吸收复杂度的一方吸收它，最不擅长管理的一方被解放」
- **出现章节**: part-0003
- **关联**: "AI →Software →Result"（AI 辅助开发）被论文判为卡在 SaaS 之前世界里的局部
  优化——人在关键路径、天花板未动、迭代延迟不减，三弱点正好是三代史要消除的东西
- **延伸**: Karpathy, Software 2.0 (2017) 是本文 Software 1.0/2.0 话语的出处之一

### Agent→Result：软件作为必要中间环节的消除

- **定义**: 新管线：人给意图 + 约束 → agent 自主规划 / 执行 / 验证 / 交付 → 人审计反馈。
  与 SaaS 消除 on-premise、云消除物理基础设施同构；论文称之为继 license→SaaS 后的
  **第三次范式转移**
- **出现章节**: part-0003、part-0004
- **关联**: 交付单元从 functioning software 变成 delivered outcomes；persist 的是 agent
  的 capability 而非中间制品（Hermes Agent 的 Skills 即该逻辑的实例化，见 part-0005）

### Agentic Engineering（学科定义与控制平面）

- **定义**: LangChain 2026-04 正式提出：multi-agent coordination model——AI agents 是带
  defined roles、shared memory、统一 observability 的 digital team members，驱动软件
  走完整交付管线。相对 AI coding agent（单会话 intent→code），它是更高抽象层的
  **control plane**（编排跨团队工作流、跨 agent 长期记忆、全生命周期 state/traceability）
- **出现章节**: part-0004、part-0006（Stage III）
- **关联**: 与 Wang et al. 的 perception/memory/action 三模块分类互为表里；Hermes Agent
  的自进化实现是生产侧佐证
- **延伸**: Kumar & Ramagopal, LangChain Blog (2026-04)；Wang et al., arXiv:2409.09030

### 人的角色重塑（intent architect / coordinator / auditor）

- **定义**: 代码生成技能 commoditize 后，人的差异化能力变为四类：intent articulation、
  architectural oversight、quality calibration、ethical governance。判断：协调 agent 群
  的生产力乘数将超过传统 10x engineer 基准；组织层推论是「小团队 orchestrator 取代
  大开发者团队」（§7.3）
- **出现章节**: part-0004、part-0007、part-0008
- **关联**: 与路线图四阶段的人设迁移一致：author/reviewer → intent architect + auditor
  → PM + architect + auditor → goal setter + ethics governor（part-0006）

### EvoClaw 落差（>80% → ≤38%）作为校准信号

- **定义**: isolated task 与 continuous software evolution（跨 commit、错误累积）之间的
  成绩断崖（12 模型 × 4 框架；图 2 为 82 → 38）；暴露 context drift / error propagation
  / technical debt awareness / verification fidelity 四缺陷。论文用它支撑「agentic
  engineering 今天真实且具变革性，但全自主仍需多年」的中间结论
- **出现章节**: part-0005、part-0007（研究者议程由此导出）
- **关联**: 四缺陷 ↔ §7.2 四个开放问题一一对应（long-context 管理、时间维度验证、
  alignment at scale、经济模型）
- **延伸**: Deng et al., EvoClaw, arXiv:2603.13428

### 四阶段路线图（Tool-Augmented → Self-Evolving）

- **定义**: Stage I Tool-Augmented (2023–25, Copilot/Claude Code) → Stage II
  Single-Task Autonomous (2025–27, Devin/OpenHands) → Stage III Multi-Agent Teams
  (2026–29, LangChain/MetaGPT) → Stage IV Self-Evolving Ecosystems (2028+, AGI
  assistants 前瞻)。Stage IV 里「software 与 agent 的区分彻底消解」——agent 即系统
- **出现章节**: part-0006、part-0007
- **关联**: 阶段时间窗口重叠说明演进是并行铺开而非串行切换；时间线为作者 2026 年的
  预测，非事实

## 重要参考

- 论文原文（HTML 版）: https://arxiv.org/html/2606.05608v1
- Agentic Engineering 定义原始出处（LangChain Blog, 2026-04）:
  https://www.langchain.com/blog/agentic-engineering-redefining-software-engineering
- Karpathy, Software 2.0 (2017): https://karpathy.medium.com/software-2-0-a64152b37c35
- Wang et al., Agents in Software Engineering（综述，arXiv:2409.09030）:
  https://arxiv.org/abs/2409.09030
- Hermes Agent（Nous Research）: https://github.com/NousResearch/hermes-agent

## 待查线索

- **数字核验**：论文的 benchmark 数字多转引自 [5][6][7]（Lingma 30.20%、EvoClaw
  > 80%→≤38%、93% 根因时间降幅等），直接引用前应回到 SWE-bench Verified 榜单与
  > EvoClaw/Hermes 原始 repo 核对（含 Hermes 的 star 数与当前能力）
- **Def 2.1/2.2 的粒度**：形式化定义较粗（Π、M 未展开），可对照 Wang et al. 综述的三
  模块分类与 Guo et al. 多智能体综述（arXiv:2402.01680）补全
- **2^n 上界的现实性**：P(n) ∈ Θ(2^n) 只证上界；真实软件依赖网络远未饱和，可与 Brooks
  原典及软件架构度量研究对照，评估「指数壁垒」论证的强度
- **EvoClaw 的公平性**：其「连续演化」设定（跨 commit、错误累积）是否对当前 agent 过于
  苛刻，值得单独读 arXiv:2603.13428 判断
- **立场的单向性**：论文论证「范式转移必然」，但对 agent 可靠性、成本、安全反例缺少
  定量反驳；可结合自己使用 AI coding agents 做长程任务的实际经验，检验
  human-in-the-loop 建议是否充分
- **AaaS 定价落地**：outcome-based 计费的风险分配与激励设计（§7.2）作者只点未展开，
  可延伸阅读按结果付费的既有实践（如众测/按单付费平台）做类比
