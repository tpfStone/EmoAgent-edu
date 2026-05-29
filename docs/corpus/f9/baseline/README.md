# F9 Baseline

本目录是第一轮 F9 人工信度基线，状态为 **历史归档 / 可追溯**。它用于回看最初的人工盲标、F4 holdout 分数和信度统计，不代表当前可直接复用的正式 F9 入口。

| 文件 | 用途 |
|---|---|
| `f9_blind_annotation.csv` | 第一轮人工盲标表，不含 F4 分数。 |
| `f9_f4_scores_holdout.csv` | 第一轮 F4 分数 holdout，用 `sample_no` 与盲标表对齐。 |
| `f9_annotations_merged.csv` | 人工标注与 F4 分数合并后的分析表。 |
| `f9_reliability_summary.csv` | 信度统计明细。 |
| `f9_reliability_report.md` | 第一轮信度报告。 |
| `f9_sampling_manifest.json` | 抽样配置和样本来源。 |

脚本入口：`scripts/corpus/f9_sampling.py`、`scripts/corpus/f9_reliability.py`。
