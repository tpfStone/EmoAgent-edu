# Specs 索引与当前边界

本目录是实现契约层，负责说明当前代码行为、已完成的 Phase 2A runtime 边界，以及还未进入运行时的 Phase 2B gates。根 README 只保留运行入口；实验细节在 `../../exp/README.md`。

## 当前运行时

- `/chat` / `/chat/stream`：F1 本地安全门 -> F2 情境/支持模式/二次安全 -> F3 单候选流式返回 -> 后台 F4 guidance。
- 后续对话：轻量 CBT-compatible 生成，注入最近历史；只有后台 F4 guidance 已完成时才注入，不等待。
- F3 support-card enrichment：可选本地参考。默认路径仍是 `exp/data/psyqa_labelled.json`；公开仓库不提供该完整数据。
- F4 pointwise：模块接口和后台质量信号，不是在线阻塞 selector。
- `GET /api/critic/guidance/{session_id}`：研究/诊断接口，只读查看后台 F4 guidance 的 `missing`、`pending`、`ready`、`failed` 状态，不改变 `/chat` 行为。
- F4 pairwise / F9 / DPO：离线或后置准入，未成为 `/chat` 默认路径。
- F6 memory/RAG：服务和接口可存在，但默认关闭；未通过 gate 前不注入学生 prompt。

## 规格入口

| 文件 | 状态 | 说明 |
| --- | --- | --- |
| `f1-safety-gate-codex-spec.md` | 2A completed | `/chat` 默认使用本地 classifier；yellow/red 短路生成。 |
| `f2-scenario-analysis-codex-spec.md` | 2A completed | 输出 scenario、CASEL、support_mode 和 secondary_safety。 |
| `f3-multi-orientation-generator-codex-spec.md` | 2A completed + offline retained | 生产单候选；双取向保留给实验和 pairwise。 |
| `f4-critic-epitome-codex-spec.md` | 2A completed + diagnostics | 后台 quality labels/session guidance；pointwise 不再做在线阻塞择优。 |
| `f4-pairwise-selection-codex-spec.md` | 2B target | pairwise 是离线目标主线，需 gate 后才能考虑 runtime/DPO。 |
| `f9-reliability-guide.md` | research gate | 人工/模型一致性与可靠性评估指南。 |
| `exp-integration-map.md` | current boundary | `exp` 资产如何分层进入 runtime/offline/default-off。 |

## 模块与证据入口

| 模块 | 当前状态 | 关联代码 | 主要测试 / 证据入口 |
| --- | --- | --- | --- |
| F1 安全门 | `/chat` 默认使用本地分类器；LLM 版 `/api/safety/evaluate` 保留兼容 | `app/services/f1_safety_classifier.py`, `app/services/classifier_safety_gate_service.py` | `tests/test_services/test_safety_gate_service.py`, `exp/README.md` |
| F2 情境分析 | LLM 输出 scenario、CASEL lookup、`support_mode` 和 `secondary_safety` | `app/services/scenario_service.py`, `app/schemas/scenario.py` | `tests/test_services/test_scenario_service.py`, `exp/README.md` |
| F3 生成器 | 模块接口保留 c1/c2；`/chat` 首轮按 F2 路由只生成一个候选 | `app/services/generator_service.py`, `app/services/f3_support_service.py` | `tests/test_services/test_generator_service.py`, `tests/test_services/test_f3_support_service.py` |
| F4 pointwise critic | 模块接口可同步调用；`/chat` 中改为后台任务，写 session guidance | `app/services/critic_service.py`, `app/services/orchestrator_service.py`, `app/schemas/critic.py` | `tests/test_services/test_critic_service.py`, `tests/test_handlers/test_critic_handler.py` |
| F4 pairwise 目标 | 离线工具链存在；不是 runtime 默认；人工一致性不足，暂不解锁 DPO | `app/services/critic_pairwise.py`, `exp/f4_pairwise_model_runner.py`, `exp/f4_human_model_agreement.py` | `exp/runs/f4_eval_package/`, `exp/runs/f4_pairwise_model_probe/` |
| F6 memory/RAG | 默认关闭；当前不注入 `/chat` prompt，后续需独立 gate | `app/services/memory_rag_service.py`, `app/handlers/memory_handler.py` | `tests/test_services/test_memory_rag_service.py`, `/api/memory/*` |
| F9 信度校验 | 历史 F9 作为追溯材料；当前主 gate 转为 pairwise 人工 A/B 和 critic-human agreement | `docs/corpus/f9/`, `exp/f4_eval_package_builder.py` | `docs/corpus/f9/README.md`, `exp/README.md` |
| Exp 集成地图 | `exp` 纳入完整体系，但实验脚本不进入 `/chat` 在线阻塞路径 | `exp/artifacts.manifest.json`, `exp/README.md` | `tests/test_exp/test_exp_integration_manifest.py` |

## 当前 `/chat` 路径

### 首次对话

```text
F1 ClassifierSafetyGateService
-> 若 yellow/red：直接返回转介
-> F2 ScenarioService
-> 若 secondary_safety yellow/red：直接返回转介
-> F3 GeneratorService.stream_one_text()
-> SSE 流式返回
-> 后台 F4 CriticService 写 session guidance
```

F3 的候选方向由 F2 决定：

- `emotion_first` 或 `emotion_intensity=high`：优先 `c1 情感共情型`。
- `solution_seeking`：优先 `c2 认知共情型`。
- 其他情况默认 `c2` 或 balanced 逻辑，具体以 `OrchestratorService._first_turn_candidate_id` 为准。

### 后续对话

```text
Redis 读取最近历史
-> 如后台 F4 guidance 已完成则读取
-> GeneratorService.stream_followup_text()
-> SSE 流式返回
```

后续轮次不再每次调用 F1/F2/F4，目的是降低延迟并让对话自然延续。F4 guidance 如果还没生成完成，不等待、不阻塞。

### 模块接口与实验链路

完整双候选和 critic 链路仍然保留在模块接口和 `exp/` 中：

- `/api/generator/generate` 可以生成 c1/c2 双候选。
- `/api/critic/evaluate` 可以同步评估候选。
- `exp/f3_support_probe.py`、`exp/f3_route_f4_probe.py`、`exp/f4_pairwise_model_runner.py` 用于继续做离线实验。

`exp` 资产的 runtime/background/offline/archive 分级记录在 [exp-integration-map.md](exp-integration-map.md) 和 `../../exp/artifacts.manifest.json`。维护原则是：`app/` 可以读取稳定数据和模型产物，但不能直接 import `exp/*.py` 实验脚本。

F6 memory/RAG 当前保持默认关闭和 observe-only 边界：即使 `app/services/memory_rag_service.py` 与 `/api/memory/*` 已存在，`/chat` 默认不从 memory/RAG 检索，也不把 memory snippet 注入 prompt。F6/RAG 的 prompt 注入必须等独立隐私、隔离、删除和质量 gate 通过后再另行接入。

## 当前改造主线

- 在线路径先保证交互速度、安全兜底和流式体验。
- 后台路径保留理论支撑：critic、pairwise、人工偏好和 DPO 数据准备。
- F1 已从 prompt 工程迁移为本地分类器；后续除非新增标注数据，否则先不继续优化。
- F3 已接入 PsyQA 策略先验和 support card；后续重点是产品侧语言体验和前端呈现。
- F4 不再作为在线强阻塞择优器；后续重点是后台质量标签、session guidance 和人工校准。

## 维护规则

- 改 runtime 行为、schema、prompt 或默认开关时，同步更新对应 spec 和 `exp-integration-map.md`。
- 不把历史实验结果写成当前 `/chat` 行为；历史文件可保留，但入口文档必须标清 runtime/offline/future。
- 计划文件只放未完成 gate；已完成事实要同步回本目录。
