---
title: E-Commerce Bench（整理完成）
tags: [reading, e-commerce-bench, paper]
categories: [reading]
hide: [navigation]
---

# E-Commerce Bench: Evaluating LLM Agents on Long-Horizon Autonomous Business Operation

- **类型**: paper（论文）
- **状态**: organized（整理完成）
- **作者**: Wei Fan、Xinjie Shen、Xudong Guo、Jianhong Tu、Yang Su、Yinger Zhang、Lianghao Deng、Fengyu Wang、Baohua Dong、Yangqiu Song、Dayiheng Liu（arXiv 作者列表；提取文本无标题页，机构待确认）
- **出处**: arXiv preprint <https://arxiv.org/html/2608.30730v1>（arXiv:2608.30730v1 [cs.LG] / cs.CL，2026-08-31 投稿 v1）
- **整理完成日期**: 2026-09-05
- **读完日期**: （由用户读完后再手工补注）

## 全文主线（核心论点）

- **任务设定**：给 agent 一个模拟中国电商平台商家账户与 ¥100,000 本金，运营完整的 2026 年
  ——用 18 个工具做市场调研、与供应商谈判进货、定价上架（最多 4 个店铺并行）、发货、
  吸收退货、管理现金流，期末总资产最大化；任务属于 RL 里 **continuing task**（无终态、
  累积得分），与一次性 episodic benchmark 相对
- **确定性双边经济（可复现性核心）**：客户侧需求由固定公式决定（价格弹性 × 周末 × 季节 ×
  促销 × 事件 × 声誉，再经容量截断）；供应商侧每个定价/让步/接受-放弃决定都由**确定性
  谈判内核**给出，LLM 只把决定渲染成对话 —— 两边的抽样噪声都被消除，**结果差异完全归因
  于 agent 策略而非运气**（只有渲染措辞在 run 间变化）
- **真实数据层**：基于淘宝 & 天猫日志校准：6,886 个商品、60 个类目、576 个供应商（424 诚实与
  152 欺诈，跑五种骗局）、12 种店型；一整年 10 场不可避市场事件与 8 场可选促销持续搅动需求；
  关键参数（成本地板、真实需求）隐藏 → 系统性信息不对称
- **评测方法**：18 个模型（8 闭源与 10 开源）× 5 episode = 90 场；主分数（年末总资产倍数）
  之外再量六个维度：谈判质量（CSE+）、反欺诈（BadSpend%）、现金流与偿付（Drawdown/Peak）、
  运营效率（¥/tool call）、运营执行（可控退货率）、长程学习（AnchorRatio）
- **核心结果**：**没有一个模型七项全强**。GPT-5.6 Sol 盈利第一（约 14 倍本金）却反欺诈排名
  第 16、工具效率低于 Fable5；Claude Opus 4.7 谈判与反欺诈双第一但盈利中游；开源第一为作者
  自家 Qwen3.8-Max-Preview（4.2 倍，学习维度第 1）；4 个模型部分 episode 破产（90 场中 10 场）；
  **8,647 次同品同供应商重复采购中 16/18 个模型无压价趋势** → 长程经验学习是当前 agent 的
  最大短板
- **方法论贡献**：确定性内核控制证明可消除复杂多边交互中的评估噪声；多维诊断证明单靠一个
  总资产数字会掩盖失败模式 —— 为 push agent 评测走向更长 horizon 提供 blueprint

## 阅读笔记

- [笔记（跨部分概念 / 重要参考 / 存疑与待查线索）](./notes.md)

## 章节

素材为本地 pdf（`2608.30730v1.pdf`）经脚本按页分组预提取为 13 个文件
（source-01…13.txt，拆分点落在正文与表格之间，与论文章节大致对齐），每文件一页：

| 页码      | 论文范围（大致）                       | 摘要                                                          |
| --------- | -------------------------------------- | ------------------------------------------------------------- |
| part-0001 | Abstract + §1 Introduction             | [摘要与引言：一年期电商运营基准](./part-0001.md)              |
| part-0002 | Table 1 + §2 Related Work              | [相关工作与定位：continuing 任务谱系](./part-0002.md)         |
| part-0003 | §3 E-Commerce Bench（主体）            | [基准设计：四层架构与确定性经济](./part-0003.md)              |
| part-0004 | Table 2 + §4 Experimental Results      | [实验结果：18 模型的多维画像](./part-0004.md)                 |
| part-0005 | §5 Conclusion + References             | [结论与参考文献](./part-0005.md)                              |
| part-0006 | Table 3 + Appendix A                   | [工具集与 agent harness：18 工具与上下文管理](./part-0006.md) |
| part-0007 | Appendix B                             | [数据层：类目、店型、日历与供应商](./part-0007.md)            |
| part-0008 | Table 7 + Appendix C                   | [经济引擎：13 步结算与需求/退货/成本公式](./part-0008.md)     |
| part-0009 | Appendix D                             | [确定性谈判内核：决策函数与骗局目录](./part-0009.md)          |
| part-0010 | Appendix E                             | [评测指标定义：六个维度与统计口径](./part-0010.md)            |
| part-0011 | Table 10 + Appendix F                  | [每维度结果导览与模型/实验设置](./part-0011.md)               |
| part-0012 | Appendix G                             | [失败案例研究：骗局实录与一次破产](./part-0012.md)            |
| part-0013 | Table 18 + Appendix H（含部分 F 表格） | [失败模式规则表与提示词设计](./part-0013.md)                  |
