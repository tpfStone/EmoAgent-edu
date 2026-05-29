# F9 Validation

本目录是修订后 F3/F4 的主 validation 包，状态为 **单次 PASS / 不作为正式人工 F9 入口**。主包验证曾通过自动 gate，但后续 stability rerun 未通过，因此这里的 rerun 包只作为诊断记录保留。

| 路径 | 用途 |
|---|---|
| `f9_validation_report.md` | 主 validation 报告，包含 Gate Decision、blocking reasons、golden、旧坏候选复评和 rerun 指标。 |
| `golden/` | golden 样本重新生成候选，以及旧坏候选交给当前 F4 复评的结果。 |
| `rerun/` | 新 40 条候选包、盲标格式表、F4 holdout、完整自动打分明细和 manifest。 |

使用约束：

- `rerun/f9_rerun_blind_annotation.csv` 当前不建议发给正式人工 F9 标注。
- `rerun/f9_rerun_selected_scores.csv` 只用于内部诊断，不给人工标注者。
- 重跑脚本入口：`scripts/corpus/f9_validation.py`。
