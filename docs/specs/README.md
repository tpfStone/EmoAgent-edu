# Specs 文档索引

本目录保存 EmoAgent-edu 运行时模块规格与后续改造目标。当前文档口径以“在线快路径 + 后台准路径”为准：模块接口可以保留完整实验能力，但 `/chat` 不再每轮阻塞式跑完整 F1-F4 双候选 critic 链路。

## 模块状态总览

| 模块 | 文档 | 当前状态 | 关联代码 | 主要测试 / 证据入口 |
| --- | --- | --- | --- | --- |
| F1 安全门 | [f1-safety-gate.md](f1-safety-gate.md) | `/chat` 默认使用本地分类器；`/api/safety/classifier/evaluate` 为生产接口；LLM 版 `/api/safety/evaluate` 保留兼容 | `app/services/f1_safety_classifier.py`, `app/services/classifier_safety_gate_service.py`, `app/services/safety_gate_service.py` | `tests/test_services/test_safety_gate_service.py`, `exp/README.md` |
| F2 情境分析 | [f2-scenario-analysis.md](f2-scenario-analysis.md) | LLM 输出 scenario、CASEL lookup、`support_mode`、`emotion_intensity`、`help_seeking` 和 `secondary_safety` | `app/services/scenario_service.py`, `app/schemas/scenario.py` | `tests/test_services/test_scenario_service.py`, `exp/README.md` |
| F3 多取向生成器 | [f3-multi-orientation-generator.md](f3-multi-orientation-generator.md) | 模块接口保留 c1/c2 双取向；`/chat` 首轮按 F2 路由只生成一个候选并流式返回；PsyQA support card 已接入 | `app/services/generator_service.py`, `app/services/f3_support_service.py` | `tests/test_services/test_generator_service.py`, `tests/test_services/test_f3_support_service.py`, `exp/runs/f3_support_probe/` |
| F4 pointwise critic | [f4-critic-epitome.md](f4-critic-epitome.md) | 模块接口可同步调用；`/chat` 中改为后台任务，写入 session guidance，`/api/critic/guidance/{session_id}` 可只读观测状态 | `app/services/critic_service.py`, `app/services/orchestrator_service.py`, `app/schemas/critic.py` | `tests/test_services/test_critic_service.py`, `tests/test_handlers/test_critic_handler.py`, `exp/runs/f3_route_f4_probe/` |
| F4 pairwise 目标 | [f4-pairwise-selection.md](f4-pairwise-selection.md) | 离线工具链和实验包存在；不是 runtime 默认；人工一致性不足，暂不解锁 DPO | `app/services/critic_pairwise.py`, `exp/f4_pairwise_model_runner.py`, `exp/f4_human_model_agreement.py` | `exp/runs/f4_eval_package/`, `exp/runs/f4_pairwise_model_probe/` |
| F6 memory/RAG | 暂无独立 spec | 应用侧接口已预留；默认关闭；当前不注入 `/chat` prompt，后续需独立 gate | `app/services/memory_rag_service.py`, `app/handlers/memory_handler.py` | `GET /api/memory/status`, `DELETE /api/memory`, `tests/test_services/test_memory_rag_service.py` |
| F9 信度校验 | [f9-reliability-guide.md](f9-reliability-guide.md) | 历史 F9 作为追溯材料；当前主 gate 转为 pairwise 人工 A/B 和 critic-human agreement | `docs/corpus/f9/`, `exp/f4_eval_package_builder.py` | `docs/corpus/f9/README.md`, `exp/README.md` |
| Exp 集成地图 | [exp-integration-map.md](exp-integration-map.md) | `exp` 纳入完整体系，但实验脚本不进入 `/chat` 在线阻塞路径 | `exp/artifacts.manifest.json`, `exp/README.md` | `tests/test_exp/test_exp_integration_manifest.py` |

## 当前 `/chat` 运行时主链路

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

后续轮次不再每次调用 F1/F2/F4，目的是降低延迟并让对话自然延续。F4 guidance 如果还没生成完成，不等待、不阻塞。研究或诊断侧可通过 `GET /api/critic/guidance/{session_id}` 查看 `missing`、`pending`、`ready` 或 `failed` 状态；该接口不改变 `/chat` 行为。

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

- 改 `/chat` 编排顺序、schema、SSE 事件或 prompt 时，同步更新本文件和对应模块 spec。
- F4 pointwise 文档描述后台 critic 当前行为；F4 pairwise 文档描述目标主线和迁移条件。
- 新实验结果优先写入 `../../exp/README.md`，再摘要同步到对应 spec。
- 历史 F9/corpus 文档只做追溯，不能覆盖当前 `exp/` 结论。
