# F9 Pairwise Selection Pilot

本目录保存 F4 pairwise preference-pair 离线试点，状态为 **Phase A.2 rerun inconclusive，Phase A.3 IRI rerun 待执行**。当前不能进入 Phase B，不能把 `/chat` 运行时切到 pairwise，也不能把本轮 pairwise stable 输出进入 DPO。

## 当前结论

- Phase A.1 smoke 跑通工具链，但不能证明 pairwise 优于 pointwise。
- Phase A.2 rerun 主集完成候选生成、pairwise judge、pointwise baseline 和人工 A/B 对齐评估。
- 当前 `comparison_intersection_pairs=7`，低于计划下限 `12`；`critic_human_agreement=0.429`，`agreement_delta_vs_pointwise=0.000`。
- stable pairwise winner 明显偏向 `c1` 候选槽位，详见 `reports/phase-a-rerun/f9_pairwise_c1_collapse_diagnostic.md`。
- 当前执行入口是 `phase-a-rerun-plan.md` 的 Phase A.3：先做候选槽位化防污染，再基于 `情感共情型` / `认知共情型` 生成新候选和均衡冻结输入包。

## 时间线

| 阶段 | 主文档 | 状态 | 结论 |
|---|---|---|---|
| Phase A.1 工具链与 smoke | `phase-a-implementation-plan.md` | 已完成 | 工具链跑通；smoke 不足以判断 pairwise 优劣。 |
| Phase A.2 rerun | `phase-a-rerun-plan.md` | 已完成 | eval 结论为 `inconclusive`；不进入 Phase B。 |
| Phase A.3 IRI rerun | `phase-a-rerun-plan.md` | 待执行 | 先做候选槽位化防污染、F3 新取向小样本验证和均衡冻结输入包，再 rerun。 |

## 目录结构

| 路径 | 用途 |
|---|---|
| `f4-pairwise-selection-pilot-plan.md` | 大轮 pairwise 试验方案和 smoke 记录。 |
| `phase-a-implementation-plan.md` | Phase A.1 工具链落地计划、验收流程和 smoke 结果。 |
| `phase-a-rerun-plan.md` | Phase A.2 结果归档与 Phase A.3 IRI rerun 当前执行计划。 |
| `inputs/` | pair package 和候选输入包。 |
| `annotations/` | 人工 A/B 标注表。人工标注时只看 `user_text`、`c1_text`、`c2_text`。 |
| `runs/` | pairwise judge、pointwise baseline 和 sidecar 运行产物。 |
| `reports/` | smoke、Phase A.2 rerun、`c1` 候选槽位塌缩和 F3 model sidecar 报告。 |

下一步应先处理候选质量、人工 tie 流失、pairwise 不稳定、`c1` 候选槽位偏斜和冻结输入包设计，再执行 Phase A.3 rerun。
