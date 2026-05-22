# Orchestrator MVP 实现后人工验收项

> 日期：2026-05-21

首版 `/chat` 编排层实现不阻塞在人工语料验证上；但在声明 MVP 验收通过前，应执行这里列出的 45 条语料人工验收。

## 什么时候执行

- 不作为编排层代码开发的前置阻塞项。
- 在技术验收通过后立即执行：测试、迁移、单条 `/chat` smoke、基础落库抽查通过后。
- 在 MVP 对外标记为“验收通过”前完成。

## MVP 人工验收项

- 用 `docs/corpus/emoedu-corpus-45-samples.json` 跑 F2，并记录情境分类准确情况。
- 用 45 条语料逐条跑 `/chat`。
- 人工检查回复合理性，并抽查 `turns`、`candidates`、`preference_pairs` 的落库情况。
- 执行清单见：`docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-manual-acceptance.md`。

## 为什么没有阻塞代码实现

- roadmap 将这些列为验证和验收工作。
- 它们依赖编排层已经可运行，因此应放在实现完成后执行。
- 它们不是 post-MVP 功能开发，也不是 F9；它们属于 MVP 人工质量验收。

## 与 F9 / post-MVP 的边界

- 45 条 `/chat` 人工验收：检查 MVP 链路稳定性、回复质量和落库完整性，应现在执行。
- F9 信度校验：比较人工 EPITOME/CASEL 标注与 F4 critic 分数的一致性，属于 MVP 之后的可靠性研究。

## F4 judge prompt 回滚标记

- MVP 阶段将 EPITOME 和 CASEL 评分保留在同一次 judge 调用中，以降低延迟和成本。
- 如果后续 F9 信度校验显示 EPITOME/CASEL 评分不稳定，则将 CASEL 拆成第二次 judge 调用，并比较一致性。
