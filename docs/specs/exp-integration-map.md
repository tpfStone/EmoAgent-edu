# Exp Integration Map

本文记录 `exp/` 资产与运行时的边界。当前阶段的原则是：`exp` 是完整体系的一部分，但不是在线同步路径的一部分；只把已通过工程边界的能力放入 `/chat`，把 pairwise、DPO、F6/RAG 留在后置 gate。

机器可读清单见 [`../../exp/artifacts.manifest.json`](../../exp/artifacts.manifest.json)。

## Tier Definitions

| Tier | Meaning | Runtime Rule |
| --- | --- | --- |
| `runtime` | 已稳定并直接服务 `/chat` 或生产模块接口 | 可由 `app/` 调用 |
| `runtime_reference` | 运行时读取的稳定参考数据或策略证据 | `app/` 只读产物，不 import 实验脚本 |
| `background` | 在线响应之后或请求外执行的质量链路 | 不阻塞学生端返回 |
| `offline` | 训练、probe、复现、评估和报告脚本 | 不进入 runtime |
| `archive` | 历史证据与追溯材料 | 不覆盖当前 `exp` 结论 |

## 当前已实现的 runtime 事实

| 资产/能力 | 当前位置 | 集成状态 | 说明 |
| --- | --- | --- | --- |
| F1 local safety classifier | `app/services/f1_safety_classifier.py`、`exp/models/f1_safety_gate/` | runtime | 模型从 HuggingFace 本地恢复；不提交 GitHub。 |
| F2 scenario/support routing | `app/services/scenario_service.py` | runtime | 输出 `support_mode` 和 `secondary_safety`。 |
| F3 single routed generation | `app/services/generator_service.py` | runtime | 首轮按 F2 `support_mode` 生成一个候选并流式返回。 |
| F3 support-card enrichment | `app/services/f3_support_service.py`、`exp/data/psyqa_labelled.json` | runtime_reference | 完整数据不随仓库发布；缺失时 enrichment 为空或通用化，系统仍可运行。 |
| F4 pointwise critic | `app/services/critic_service.py` | background diagnostics | 首轮回复后异步运行，写 Redis guidance；不阻塞学生回复。 |
| F4 guidance status | `GET /api/critic/guidance/{session_id}` | diagnostics | 研究/诊断侧只读查看 `missing`、`pending`、`ready`、`failed`，并在 `ready` 时读取后台 `scores`；不改变 `/chat` 行为。 |
| Follow-up F1 safety gate | `app/services/orchestrator_service.py` | runtime | 后续轮次仍先过 F1；不再每轮同步跑完整 F2/F4。 |

## Asset Matrix

| Asset | Tier | Runtime Entry | Integration Notes |
| --- | --- | --- | --- |
| `exp/data/psyqa_labelled.json` | `runtime_reference` | `app/services/f3_support_service.py` | 公开仓库不包含完整数据。存在时只提供策略先验和短 support card，不把 PsyQA 原始回复整段放入 RAG。 |
| `exp/models/f1_safety_gate/manual-A-pattern-v1/` | `runtime` | `app/services/f1_safety_classifier.py` | F1 本地安全门产物，本地下载，不提交 GitHub；生产建议 `F1_SAFETY_REQUIRED=true`。 |
| `exp/f1_*.py` | `offline` | None | 训练、关键词、阈值和 benchmark 脚本，只负责生成或验证 F1 产物。 |
| `app/services/f3_support_service.py` | `runtime_reference` | `app/services/generator_service.py` | 这是 F3 support 的运行时边界；对应 probe 仍在 `exp/`。 |
| `exp/f3_*.py` | `offline` | None | 验证 c1/c2 取向、support card、route + F4 假设，不进入 `/chat`。 |
| `app/services/critic_service.py` | `background` | `app/services/orchestrator_service.py` | F4 pointwise critic 在首轮返回后后台运行，写 session guidance。 |
| `exp/f4_*.py` | `offline` | None | pairwise package、model judge、人机一致性分析，只作为离线评估和后续 DPO 准备。 |
| `docs/corpus/f9/` | `archive` | None | 历史信度校验材料，只做追溯，不能替代当前 `exp` 结论。 |

## 仍是离线或后置 gate

| 资产/能力 | 当前状态 | 不进入 runtime 的原因 |
| --- | --- | --- |
| F4 pairwise selector | offline/future | 最近一次 pairwise rerun 仍为 `inconclusive`，有效交集不足且 stable winner 出现 `c1` 偏斜；需要新的有效样本、人工 A/B 和稳定性 gate。 |
| DPO export | future | 不能从 pointwise tiebreak、orientation default 或 unverified pairwise 直接导出训练样本。 |
| F9 reliability | offline evidence | 用于评估 critic/human 一致性，不直接改变 `/chat`。 |
| F6 memory/RAG prompt injection | default-off/future | 需要隐私隔离、敏感内容过滤、清除链路和质量 smoke gate。 |
| `exp/runs/` 原始产物 | local/offline | 体积较大，主要用于本地复现和审计，不提交 GitHub。 |

## 数据发布边界

- 公开仓库不包含完整 `exp/data/psyqa_labelled.json`，也不跟踪 `exp/data/*.json` sample 导出。
- 复现者需要自行把完整 labelled data 放到 `exp/data/psyqa_labelled.json`。
- 文件缺失时，F3 strategy priors/support cards 为空或退回通用策略；默认路径、代码设计和 API 不变。

## Complete System Paths

### Online Fast Path

```text
First turn:
F1 local classifier
-> F2 scenario/support routing and secondary safety
-> F3 one routed candidate with optional PsyQA support reference
-> stream student-facing response
-> schedule background F4

Follow-up turns:
F1 local classifier
-> recent Redis history
-> optional completed F4 guidance
-> lightweight follow-up generation
-> stream student-facing response
```

Allowed `exp` inputs:

- `exp/models/f1_safety_gate/manual-A-pattern-v1/`
- local `exp/data/psyqa_labelled.json`
- conclusions summarized in `exp/README.md` and module specs

Not allowed in the blocking path:

- `exp/*.py` experiment scripts
- `exp/f3_route_f4_probe.py`
- `exp/f4_pairwise_model_runner.py`
- F3 c1/c2 full synchronous generation plus F4 selection
- DPO and pairwise training workflows
- large raw `exp/runs/` artifacts

### Background Quality Path

```text
student response finished
-> F4 pointwise critic
-> write Redis session guidance
-> later follow-up prompt may inject completed guidance
```

Research and diagnostics can inspect background F4 state through:

```text
GET /api/critic/guidance/{session_id}
```

This endpoint reports `missing`, `pending`, `ready`, or `failed`; `ready` responses also include background F4 `scores` for the research console. It is not part of the student-facing blocking path: `ready` may be used by the next follow-up prompt, while `pending` and `failed` never block the student response.

Future background-only extensions can include batch critic, review queues, pairwise human A/B exports, and DPO candidate packaging. Those jobs should be triggered by scripts or workers, not by the blocking `/chat` request.

### Disabled F6 Memory/RAG Path

`F6_MEMORY_ENABLE=false` is the default production posture. The memory/RAG service and `/api/memory/*` endpoints may exist, but the current `/chat` orchestrator does not read them and does not inject memory snippets into first-turn or follow-up prompts.

Current rule: 不注入 `/chat` prompt. Before F6/RAG moves beyond observe-only mode, it must pass a separate gate for user isolation, sensitive-content handling, deletion, and quality regression. Until then, F6/RAG must not replace PsyQA support cards and must not inject into `/chat` prompt by default.

### Offline Reproduction Path

```text
PsyQA labeling
-> F1 keyword/model experiments
-> F3 support and route probes
-> F4 pairwise package and model agreement
-> reports in exp/README.md and docs/corpus/
```

This path is allowed to require `requirements-exp.txt`, API keys, local model files, local `exp/data/psyqa_labelled.json`, and large ignored `exp/runs/` outputs.

## Maintenance Rules

- New experiment assets must be added to `exp/artifacts.manifest.json` before they are referenced from runtime docs.
- Runtime code under `app/` must not import `exp/*.py`; it may only read configured stable files such as local `exp/data/psyqa_labelled.json` or downloaded model artifacts.
- If an offline result changes runtime behavior, update the relevant module spec first, then update this map and `exp/README.md`.
- Pairwise, DPO, long-term RAG, and full multi-agent validation should enter through background jobs or offline scripts until latency, safety, and evaluation criteria are explicit.
