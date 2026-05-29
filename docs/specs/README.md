# Specs 文档索引

本目录保存 EmoAgent-edu 运行时模块规格与后续改造目标。文档用于标准开发、测试与验收，不面向特定工具或实现者。

## 模块状态总览

| 模块 | 文档 | 当前状态 | 关联代码 | 主要测试 | 后续 plan / 证据入口 |
|---|---|---|---|---|---|
| F1 安全门 | [f1-safety-gate.md](f1-safety-gate.md) | 已接入 `/api/safety/evaluate` 与 `/chat` 前置短路；异常按 yellow 兜底 | `app/services/safety_gate_service.py`, `app/services/orchestrator_service.py` | `tests/test_services/test_safety_gate_service.py`, `tests/test_handlers/test_safety_handler.py`, `tests/test_services/test_orchestrator_service.py` | `../issues/2026-05-20-f1-f4-development-issues.md` |
| F2 情境分析 | [f2-scenario-analysis.md](f2-scenario-analysis.md) | 已接入 `/api/scenario/evaluate` 与 `/chat`；情境到 CASEL 映射由代码表生成 | `app/services/scenario_service.py`, `app/services/orchestrator_service.py` | `tests/test_services/test_scenario_service.py`, `tests/test_handlers/test_scenario_handler.py` | `../corpus/` |
| F3 多取向生成器 | [f3-multi-orientation-generator.md](f3-multi-orientation-generator.md) | 已接入 `/api/generator/generate` 与 `/chat`；固定两取向并发生成，RAG 入口尚未接入 `/chat` | `app/services/generator_service.py`, `app/services/orchestrator_service.py` | `tests/test_services/test_generator_service.py`, `tests/test_handlers/test_generator_handler.py` | `../corpus/f9/plans/f3-generator-fix-plan.md`, `../issues/2026-05-22-f3-prompt-iteration-issues.md` |
| F4 pointwise critic | [f4-critic-epitome.md](f4-critic-epitome.md) | 当前 `/chat` 默认择优器；使用 EPITOME/CASEL pointwise、median、boundary 过滤和 `weighted_total` | `app/services/critic_service.py`, `app/services/orchestrator_service.py`, `app/schemas/critic.py` | `tests/test_services/test_critic_service.py`, `tests/test_handlers/test_critic_handler.py` | `../corpus/f9/plans/f4-critic-fix-plan.md`, `../corpus/f9/README.md` |
| F4 pairwise 目标 | [f4-pairwise-selection.md](f4-pairwise-selection.md) | 离线工具链已存在；已显式接入 `activated_casel` CASEL 比较 rubric；不是 runtime 默认，Phase A rerun 结论为 `inconclusive` | `app/services/critic_pairwise.py`, `scripts/corpus/f9_pairwise_*.py` | `tests/test_services/test_critic_pairwise.py`, `tests/test_corpus/test_f9_pairwise_*.py` | `../corpus/f9/pairwise-selection-pilot/f4-pairwise-selection-pilot-plan.md`, `../corpus/f9/pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md` |
| F9 信度校验 | [f9-reliability-guide.md](f9-reliability-guide.md) | 主 gate 转为 pairwise 人工 A/B 一致性；pointwise 正式人工 F9 暂停，旧主包单次 PASS 但稳定性复跑失败 | `scripts/corpus/f9_sampling.py`, `scripts/corpus/f9_reliability.py`, `scripts/corpus/f9_validation.py`, `scripts/corpus/f9_fixed_candidate_rescore.py`, `scripts/corpus/f9_pairwise_*.py` | `tests/test_corpus/test_f9_*.py` | `../corpus/f9/README.md`, `../corpus/f9/pointwise-diagnostics/execution-summary.md` |

## 运行时主链路

当前 `/chat` 仍按以下顺序运行：

1. F1 `SafetyGateService` 判定 green/yellow/red；yellow/red 直接返回转介话术。
2. F2 `ScenarioService` 只在 green 后运行，输出情境和 `activated_casel`。
3. F3 `GeneratorService` 生成 `情感共情型` 与 `认知共情型` 两条候选。
4. F4 `CriticService` 使用 pointwise 分数和 boundary 过滤择优。

`CriticPairwiseService` 当前用于 F9/pairwise 离线试点，不参与 `/chat` 默认响应；离线 prompt 已把 F2 的 `activated_casel` 转为显式 CASEL A/B/tie 比较维度。

## 端到端技术路线表

| 阶段 | 输入 | 处理方式 | 输出 | 输出去向/作用 |
|---|---|---|---|---|
| F1 安全门 | 用户当前消息 + 历史窗口 | LLM 低温风险分级，代码侧填充固定转介动作 | `risk_level=green/yellow/red`、`block_generation`、`referral_message` | `green` 进入 F2；`yellow/red` 直接短路返回转介话术，不进入生成 |
| F2 情境分析 | F1 放行后的用户当前消息 + 历史窗口 | LLM 低温四分类得到 `scenario`，再由 `SCENARIO_CASEL_MAP` 查表生成 `activated_casel` | `scenario`、`scenario_confidence`、`activated_casel`、`rationale` | `scenario` 给 F3 作情境上下文；`activated_casel` 给 F4 限定 CASEL 维度；同时进入 `/chat` 元数据、日志和离线分析 |
| F3 双取向生成 | 用户消息 + 历史 + `scenario` + 可选 `rag_examples` | 同一底座 LLM 用两套取向 prompt 并发生成 | `c1=情感共情型`、`c2=认知共情型` 两条候选 | 候选列表进入 F4 当前 pointwise critic 择优；候选也可进入后续 F9/pairwise 输入包 |
| F4 pointwise critic（当前 runtime） | 用户上下文 + `activated_casel` + F3 候选 | 对每条候选做 EPITOME/CASEL pointwise 打分、boundary 过滤和 `weighted_total` argmax | `best_candidate_id`、`scores`、历史兼容 `preference_pair` | 当前 `/chat` 默认用 `best_candidate_id` 选最终回复；分数和偏好对只作兼容与诊断，不作为新的 DPO 主来源 |
| F4 pairwise / F9（离线目标线） | 冻结候选对 + 人工 A/B + `activated_casel_json` / CASEL trace | 离线 pairwise judge、pointwise baseline 和人工一致性评估 | agreement report、pairwise summary、go/no-go conclusion | 验证 pairwise 是否可迁移为后续主线；当前不是 `/chat` 默认 runtime，Phase A rerun 仍为 `inconclusive` |
| F6/F7/F8 后续项 | 通过 gate 后的语料、偏好对或新增取向配置 | RAG 检索、DPO 训练、第三取向生成等后续实验 | 检索参考、训练数据或新增候选 | 当前不属于 F1-F4 主链路；需在对应 gate 通过后再接入运行时或训练流程 |

## RAG / 外部知识库说明

当前 `/chat` 主链路不需要外部知识库。F3 schema 预留了 `rag_examples`，但 `/chat` 暂未接入 F6 RAG，当前为空数组。RAG 是后续增强项，用于给生成器提供相似情境参考，不是 F2 分类或当前 F1-F4 运行的必要依赖。

## 当前改造主线

F4 的运行时事实和目标方向要分开读：

- `f4-critic-epitome.md` 描述当前 `/chat` 默认行为：pointwise EPITOME/CASEL 打分、`weighted_total` 择优和历史兼容 `preference_pair`。
- `f4-pairwise-selection.md` 描述目标主线：用成对偏好判断替代 pointwise 作为择优和 DPO 偏好对来源；CASEL 在该线中是显式比较维度和审计 trace，不是加权总分项。
- `f9-reliability-guide.md` 的主 gate 应转为 pairwise 人工 A/B 一致性；pointwise weighted kappa 只保留为诊断证据。
- 在 pairwise rerun 通过预设 gate 前，不切换 `/chat` runtime，不把旧 pointwise 偏好对放入 DPO。

## 维护规则

- 改运行时代码、schema、prompt 或验收口径时，同步更新对应模块规格。
- F4 pointwise 文档描述当前 `/chat` 默认行为；F4 pairwise 文档描述目标主线和迁移条件。
- F9 相关计划、run 产物和诊断记录以 `../corpus/f9/README.md` 为入口。
