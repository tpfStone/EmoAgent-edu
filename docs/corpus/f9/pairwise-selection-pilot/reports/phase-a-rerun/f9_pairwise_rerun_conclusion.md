# F9 Pairwise Phase A Rerun 整理结论

日期：2026-05-28

## 人工标注整理

- 已复查人工 A/B 行数：24。
- 已按 note 补齐缺失的 `human_preference`、`human_tie`、`human_invalid`、`human_issue_type`、`annotator_id`。
- 最终人工偏好：`c1=7`、`c2=8`、`tie=9`、`invalid=0`。
- 提示词/格式残留样本：`sample-1`、`sample-23`；两行均保留 `human_boundary_winner=c1`。

按场景拆分：

| scenario | c1 | c2 | tie |
|---|---:|---:|---:|
| 亲子摩擦 | 2 | 2 | 4 |
| 同伴关系 | 1 | 4 | 3 |
| 学业压力 | 4 | 2 | 2 |

## Eval 结果

| Metric | Value |
|---|---:|
| total_pairs | 24 |
| human_valid_pairs | 15 |
| pairwise_valid_pairs_all | 9 |
| comparison_intersection_pairs | 7 |
| pairwise_matches | 3 |
| critic_human_agreement | 0.429 |
| pointwise_matches | 3 |
| pointwise_human_agreement | 0.429 |
| agreement_delta_vs_pointwise | 0.000 |
| human_tie_rate | 0.375 |

严格按 go/no-go 口径：`comparison_intersection_pairs=7`，低于 Phase A rerun 计划里的 `12` 下限，所以本轮正式结论是 `inconclusive`。它不能证明 pairwise 优于 pointwise，也不能推进到 Phase B 运行时受控集成。

诊断性解读：即便只看这 7 个交集样本，pairwise 也没有优于 pointwise（`delta=0.000`），两者都是 `3/7`。这不是继续沿用当前 pairwise 设置的正向信号。

## 样本流失

- 人工 tie/invalid 流失：9 行。
- human-valid 后 pairwise unstable/invalid 流失：6 行。
- pairwise-valid 后 pointwise invalid/nonformal 流失：2 行。

最大流失来自人工 tie 和 pairwise 不稳定。pointwise baseline 本身已按正式 `pointwise_sample_count=3` 完成，但 pointwise tie 仍从最终交集里移除了 2 行。

## 诊断发现

- Pairwise stable 输出明显偏斜：本轮所有 stable pairwise winner 都是 `c1`，而 human-valid 偏好接近平衡（`c1=7`、`c2=8`）。由于 Phase A.2 输入包里 `c1` 始终是旧 `共情型` 候选，这更像是对旧 `共情型` 候选的强偏好，或者输入包设计无法区分取向偏好和候选槽位。
- `c1` 偏斜专项诊断见 `docs/corpus/f9/pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_c1_collapse_diagnostic.md`。
- 人工 note 反复指出两条候选过于相似或质量都低：`取向不分化`、`模板化`、`语义重复`、`复述原文`。
- 多个求助型用户 turn 没有得到足够可执行的回应，尤其是用户问“该怎么说”“要不要告诉家长”的行；note 中集中出现 `未回应求助`、`问题重复`、`答非所问;分类不适配`。
- 候选清理仍不够干净：2 行仍有提示词/格式残留，和 rerun 输入质量门槛不一致。

## 可用结论

本轮可以给出可执行判断，但不能给出正式的模型优劣证明：

1. 不进入 Phase B，不把 `/chat` 切到 pairwise。
2. 不建议在当前设置上直接扩样本，因为问题不是单纯分母不够。
3. 先修 F3 候选生成和冻结输入包设计，再 rerun。

建议优先修复：

- 基于当前 IRI 取向复核面向具体求助 turn 的回应质量，覆盖用户问“怎么说”“下一步怎么做”的场景。
- 收紧 F3 清洗，入包前移除括号里的 prompt 检查、元说明和其他格式残留。
- 降低模板化共情表达，尤其是重复的“憋屈”“那股...”类句式。
- 后续冻结输入包中随机或均衡 `c1/c2` 对应的取向，避免分析时无法区分候选槽位和取向风格。
- 完成上述修复后再 rerun，目标至少拿到 12 个 comparison-intersection 样本，最好接近 20+。
