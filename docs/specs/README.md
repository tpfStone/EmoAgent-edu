# Specs 索引与当前边界

本目录是实现契约层，负责说明当前代码行为、已完成的 Phase 2A runtime 边界，以及还未进入运行时的 Phase 2B gates。根 README 只保留运行入口；实验细节在 `../../exp/README.md`。

## 当前运行时

- `/chat` / `/chat/stream`：F1 本地安全门 -> F2 情境/支持模式/二次安全 -> F3 单候选流式返回 -> 后台 F4 guidance。
- 后续对话：轻量 CBT-compatible 生成，注入最近历史；只有后台 F4 guidance 已完成时才注入，不等待。
- F3 support-card enrichment：可选本地参考。默认路径仍是 `exp/data/psyqa_labelled.json`；公开仓库不提供该完整数据。
- F4 pointwise：模块接口和后台质量信号，不是在线阻塞 selector。
- F4 pairwise / F9 / DPO：离线或后置准入，未成为 `/chat` 默认路径。
- F6 memory/RAG：服务存在，但默认关闭；未通过 gate 前不注入学生 prompt。

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

## 维护规则

- 改 runtime 行为、schema、prompt 或默认开关时，同步更新对应 spec 和 `exp-integration-map.md`。
- 不把历史实验结果写成当前 `/chat` 行为；历史文件可保留，但入口文档必须标清 runtime/offline/future。
- 计划文件只放未完成 gate；已完成事实要同步回本目录。
