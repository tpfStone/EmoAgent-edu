# Exp Integration Map

本文件说明 `exp/` 如何融入完整体系，同时保护 `/chat` 在线路径不被实验链路拖慢。

## Integration Principle

`exp` 是完整体系的一部分，但不是在线同步路径的一部分。

运行时只允许读取稳定产物和稳定数据，例如 F1 模型目录与 PsyQA 标注数据。实验脚本、双候选 probe、pairwise judge、人机一致性分析和 DPO 准备流程保留在离线或后台路径中，不直接进入 `/chat` 阻塞链路。

## Tier Definitions

| Tier | Meaning | Runtime Rule |
| --- | --- | --- |
| `runtime` | 已稳定并直接服务 `/chat` 或生产模块接口 | 可由 `app/` 调用 |
| `runtime_reference` | 运行时读取的稳定参考数据或策略证据 | `app/` 只读产物，不 import 实验脚本 |
| `background` | 在线响应之后或请求外执行的质量链路 | 不阻塞学生端返回 |
| `offline` | 训练、probe、复现、评估和报告脚本 | 不进入 runtime |
| `archive` | 历史证据与追溯材料 | 不覆盖当前 `exp` 结论 |

机器可读清单见 [`../../exp/artifacts.manifest.json`](../../exp/artifacts.manifest.json)。

## Asset Matrix

| Asset | Tier | Runtime Entry | Integration Notes |
| --- | --- | --- | --- |
| `exp/data/psyqa_labelled.json` | `runtime_reference` | `app/services/f3_support_service.py` | 只提供策略先验和短 support card，不把 PsyQA 原始回复整段放入 RAG。 |
| `exp/models/f1_safety_gate/manual-A-pattern-v1/` | `runtime` | `app/services/f1_safety_classifier.py` | F1 本地安全门产物，本地下载，不提交 GitHub；生产建议 `F1_SAFETY_REQUIRED=true`。 |
| `exp/f1_*.py` | `offline` | None | 训练、关键词、阈值和 benchmark 脚本，只负责生成或验证 F1 产物。 |
| `app/services/f3_support_service.py` | `runtime_reference` | `app/services/generator_service.py` | 这是 F3 support 的运行时边界；对应 probe 仍在 `exp/`。 |
| `exp/f3_*.py` | `offline` | None | 验证 c1/c2 取向、support card、route + F4 假设，不进入 `/chat`。 |
| `app/services/critic_service.py` | `background` | `app/services/orchestrator_service.py` | F4 pointwise critic 在首轮返回后后台运行，写 session guidance。 |
| `exp/f4_*.py` | `offline` | None | pairwise package、model judge、人机一致性分析，只作为离线评估和后续 DPO 准备。 |
| `docs/corpus/f9/` | `archive` | None | 历史信度校验材料，只做追溯，不能替代当前 `exp` 结论。 |

## Complete System Paths

### Online Fast Path

```text
F1 local classifier
-> F2 scenario/support routing and secondary safety
-> F3 one routed candidate with PsyQA support reference
-> stream student-facing response
-> schedule background F4
```

Allowed `exp` inputs:

- `exp/models/f1_safety_gate/manual-A-pattern-v1/`
- `exp/data/psyqa_labelled.json`
- conclusions summarized in `exp/README.md` and module specs

Not allowed in the blocking path:

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

Future background-only extensions can include batch critic, review queues, pairwise human A/B exports, and DPO candidate packaging. Those jobs should be triggered by scripts or workers, not by the blocking `/chat` request.

Research and diagnostics can inspect background F4 state through:

```text
GET /api/critic/guidance/{session_id}
```

This endpoint reports `missing`, `pending`, `ready`, or `failed`. It is not part of the student-facing blocking path: `ready` may be used by the next follow-up prompt, while `pending` and `failed` never block the student response.

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

This path is allowed to require `requirements-exp.txt`, API keys, local model files, and large ignored `exp/runs/` outputs.

## Maintenance Rules

- New experiment assets must be added to `exp/artifacts.manifest.json` before they are referenced from runtime docs.
- Runtime code under `app/` must not import `exp/*.py`; it may only read configured stable files such as `exp/data/psyqa_labelled.json` or downloaded model artifacts.
- If an offline result changes runtime behavior, update the relevant module spec first, then update this map and `exp/README.md`.
- Pairwise, DPO, long-term RAG, and full multi-agent validation should enter through background jobs or offline scripts until latency, safety, and evaluation criteria are explicit.
