# Exp 集成边界图

本文记录 `exp/` 资产与运行时的边界。当前阶段的原则是：只把已通过工程边界的能力放入 `/chat`，把 pairwise、DPO、F6/RAG 留在后置 gate。

## Phase 2A 已完成事实

| 资产/能力 | 当前位置 | 运行时状态 | 说明 |
| --- | --- | --- | --- |
| F1 local safety classifier | `app/services/f1_safety_classifier.py`、`exp/models/f1_safety_gate/` | runtime | 模型从 HuggingFace 本地恢复；不提交 GitHub。 |
| F2 scenario/support routing | `app/services/scenario_service.py` | runtime | 输出 `support_mode` 和 `secondary_safety`。 |
| F3 single routed generation | `app/services/generator_service.py` | runtime | 首轮按 F2 `support_mode` 生成一个候选并流式返回。 |
| F3 support-card enrichment | `app/services/f3_support_service.py`、`exp/data/psyqa_labelled.json` | optional runtime reference | 完整数据不随仓库发布；缺失时 enrichment 为空或通用化，系统仍可运行。 |
| F4 pointwise critic | `app/services/critic_service.py` | background/runtime diagnostics | 首轮回复后异步运行，写 Redis guidance；不阻塞学生回复。 |
| F4 guidance injection | `app/services/orchestrator_service.py` | runtime when ready | 后续轮次只在 guidance 已完成时注入；pending/missing 不等待。 |

## 仍是离线或后置 gate

| 资产/能力 | 当前状态 | 不进入 runtime 的原因 |
| --- | --- | --- |
| F4 pairwise selector | offline/future | Phase A rerun 仍为 `inconclusive`；需要新的有效样本、人工 A/B 和稳定性 gate。 |
| DPO export | future | 不能从 pointwise tiebreak、orientation default 或 unverified pairwise 直接导出训练样本。 |
| F9 reliability | offline evidence | 用于评估 critic/human 一致性，不直接改变 `/chat`。 |
| F6 memory/RAG prompt injection | default-off/future | 需要隐私隔离、敏感内容过滤、清除链路和质量 smoke gate。 |
| `exp/runs/` 原始产物 | local/offline | 体积较大，主要用于本地复现和审计，不提交 GitHub。 |

## 数据发布边界

- 公开仓库不包含完整 `exp/data/psyqa_labelled.json`，也不跟踪 `exp/data/*.json` sample 导出。
- 复现者需要自行把完整 labelled data 放到 `exp/data/psyqa_labelled.json`。
- 文件缺失时，F3 strategy priors/support cards 为空或退回通用策略；默认路径、代码设计和 API 不变。

## 当前 `/chat` 口径

```text
first turn:
F1 local safety gate
-> F2 scenario/support routing + secondary safety
-> F3 one routed candidate streaming response
-> background F4 pointwise guidance

follow-up:
lightweight CBT-compatible generation
-> recent history
-> inject completed F4 guidance if present
-> streaming response
```

Pairwise、DPO、F6/RAG 均不得在 gate 通过前进入上述默认路径。
