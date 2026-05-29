# Specs 文档索引

本目录保存 EmoAgent-edu 运行时模块规格与后续改造目标。文档用于标准开发、测试与验收，不面向特定工具或实现者。

## 模块状态总览

| 模块 | 文档 | 当前状态 | 关联代码 | 主要测试 | 后续 plan / 证据入口 |
|---|---|---|---|---|---|
| F1 安全门 | [f1-safety-gate.md](f1-safety-gate.md) | 已接入 `/api/safety/evaluate` 与 `/chat` 前置短路；异常按 yellow 兜底 | `app/services/safety_gate_service.py`, `app/services/orchestrator_service.py` | `tests/test_services/test_safety_gate_service.py`, `tests/test_handlers/test_safety_handler.py`, `tests/test_services/test_orchestrator_service.py` | `../issues/2026-05-20-f1-f4-development-issues.md` |
| F2 情境分析 | [f2-scenario-analysis.md](f2-scenario-analysis.md) | 已接入 `/api/scenario/evaluate` 与 `/chat`；情境到 CASEL 映射由代码表生成 | `app/services/scenario_service.py`, `app/services/orchestrator_service.py` | `tests/test_services/test_scenario_service.py`, `tests/test_handlers/test_scenario_handler.py` | `../corpus/` |
| F3 多取向生成器 | [f3-multi-orientation-generator.md](f3-multi-orientation-generator.md) | 已接入 `/api/generator/generate` 与 `/chat`；固定两取向并发生成，RAG 入口尚未接入 `/chat` | `app/services/generator_service.py`, `app/services/orchestrator_service.py` | `tests/test_services/test_generator_service.py`, `tests/test_handlers/test_generator_handler.py` | `../corpus/f9/plans/f3-generator-fix-plan.md`, `../issues/2026-05-22-f3-prompt-iteration-issues.md` |
| F4 pointwise critic | [f4-critic-epitome.md](f4-critic-epitome.md) | 当前 `/chat` 默认择优器；使用 EPITOME/CASEL pointwise、median、boundary 过滤和 `weighted_total` | `app/services/critic_service.py`, `app/services/orchestrator_service.py`, `app/schemas/critic.py` | `tests/test_services/test_critic_service.py`, `tests/test_handlers/test_critic_handler.py` | `../corpus/f9/plans/f4-critic-fix-plan.md`, `../corpus/f9/README.md` |
| F4 pairwise 目标 | [f4-pairwise-selection.md](f4-pairwise-selection.md) | 离线工具链已存在；不是 runtime 默认，Phase A rerun 结论为 `inconclusive` | `app/services/critic_pairwise.py`, `scripts/corpus/f9_pairwise_*.py` | `tests/test_services/test_critic_pairwise.py`, `tests/test_corpus/test_f9_pairwise_*.py` | `../corpus/f9/pairwise-selection-pilot/f4-pairwise-selection-pilot-plan.md`, `../corpus/f9/pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md` |
| F9 信度校验 | [f9-reliability-guide.md](f9-reliability-guide.md) | 主 gate 转为 pairwise 人工 A/B 一致性；pointwise 正式人工 F9 暂停，旧主包单次 PASS 但稳定性复跑失败 | `scripts/corpus/f9_sampling.py`, `scripts/corpus/f9_reliability.py`, `scripts/corpus/f9_validation.py`, `scripts/corpus/f9_fixed_candidate_rescore.py`, `scripts/corpus/f9_pairwise_*.py` | `tests/test_corpus/test_f9_*.py` | `../corpus/f9/README.md`, `../corpus/f9/pointwise-diagnostics/execution-summary.md` |

## 运行时主链路

当前 `/chat` 仍按以下顺序运行：

1. F1 `SafetyGateService` 判定 green/yellow/red；yellow/red 直接返回转介话术。
2. F2 `ScenarioService` 只在 green 后运行，输出情境和 `activated_casel`。
3. F3 `GeneratorService` 生成 `情感共情型` 与 `认知共情型` 两条候选。
4. F4 `CriticService` 使用 pointwise 分数和 boundary 过滤择优。

`CriticPairwiseService` 当前用于 F9/pairwise 离线试点，不参与 `/chat` 默认响应。

## 当前改造主线

F4 的运行时事实和目标方向要分开读：

- `f4-critic-epitome.md` 描述当前 `/chat` 默认行为：pointwise EPITOME/CASEL 打分、`weighted_total` 择优和历史兼容 `preference_pair`。
- `f4-pairwise-selection.md` 描述目标主线：用成对偏好判断替代 pointwise 作为择优和 DPO 偏好对来源。
- `f9-reliability-guide.md` 的主 gate 应转为 pairwise 人工 A/B 一致性；pointwise weighted kappa 只保留为诊断证据。
- 在 pairwise rerun 通过预设 gate 前，不切换 `/chat` runtime，不把旧 pointwise 偏好对放入 DPO。

## 维护规则

- 改运行时代码、schema、prompt 或验收口径时，同步更新对应模块规格。
- F4 pointwise 文档描述当前 `/chat` 默认行为；F4 pairwise 文档描述目标主线和迁移条件。
- F9 相关计划、run 产物和诊断记录以 `../corpus/f9/README.md` 为入口。
