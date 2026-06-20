# F9 Pairwise Pilot Evaluation

> **F9 当前边界**：本文件属于 F9、pointwise 或 pairwise 历史实验记录。Pointwise ER/IP/EX 仅作诊断和历史兼容；正式 DPO 与 runtime selector 仍依赖 pairwise/human A/B gate，Phase A rerun 当前为 `inconclusive`。

- total_pairs: 24
- human_valid_pairs: 15
- critic_valid_pairs: 7
- pairwise_matches: 3
- critic_human_agreement: 0.429
- pointwise_valid_pairs: 7
- pointwise_matches: 3
- pointwise_human_agreement: 0.429
- agreement_delta_vs_pointwise: 0.000
- comparison_intersection_pairs: 7
- pairwise_valid_pairs_all: 9
- pointwise_valid_pairs_all: 13
- attrition_human_tie_or_invalid: 9
- attrition_pairwise_unstable_or_invalid: 6
- attrition_pointwise_invalid_or_nonformal: 2
- human_tie_rate: 0.375

## 样本流失分解

- total_pairs: 24
- human_valid_pairs: 15
- pairwise_valid_pairs_all: 9
- comparison_intersection_pairs: 7
- attrition_human_tie_or_invalid: 9
- attrition_pairwise_unstable_or_invalid: 6
- attrition_pointwise_invalid_or_nonformal: 2

本轮 agreement 数字只在三方交集上解释；当 pointwise baseline 不是 3-sample formal 口径时，delta 记为 unavailable。
