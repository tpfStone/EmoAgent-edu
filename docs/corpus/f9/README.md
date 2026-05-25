# F9 产物与验收状态总览

本目录保存 F9 人工信度、错误分析、以及 F3/F4 修订后的自动验收产物。当前核心状态是：**未达到正式 F9 人工验收前置条件**。F3 生成端有初步改善，但 F4 评审端仍未通过自动准入，下一步应优先修 F4，再重跑 validation。

## 当前判定

- **Gate Decision：FAIL**
- **不建议现在进入正式人工 F9。**
- `validation/rerun/f9_rerun_blind_annotation.csv` 是当前版本的重跑诊断包，可以用于定位问题；但不应作为正式 F9 人工验收包发出，除非目标是记录“当前版本仍不合格”。

自动验收的主要证据：

- F3 golden 回归：20 条生成候选中 19 条通过，sample 27 的 `c2` 仍出现第三方事实/动机补全痕迹。
- 旧坏候选 F4 复评：10 条中只有 4 条达到预期，失败样本为 3、11、19、25、27、40。
- 新 40 条重跑包：生成端没有触发已列出的字符串级坏模式，也没有 fallback；但 F4 仍接近满分饱和，ER=2 为 38/40，IP=2 为 37/40。

## 接下来步骤

1. 继续修 F4 判分执行力，重点让模板化、第三方解释、无信息增量、事实补全、强行重构实际降分。
2. 重跑 `C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation`。
3. 检查 `validation/f9_validation_report.md` 的 `Gate Decision` 和 blocking reasons。
4. 只有自动准入通过后，再把 `validation/rerun/f9_rerun_blind_annotation.csv` 作为正式人工 F9 的候选入口。

## 自动准入门槛

进入正式人工 F9 前，至少应满足：

- 旧坏候选 F4 复评通过率至少 80%，即 10 条中至少 8 条符合预期。
- 旧坏候选 ER/IP 同时 2/2 的比例不超过 20%，避免继续放过明显坏文本。
- 新 40 条重跑样本中 ER=2 与 IP=2 的比例都不超过 80%，不能接近全满分。
- F4 rationale 如果识别到模板化、第三方解释、事实补全、强行重构，分数必须实际降下来。
- F3 golden 和新 40 条重跑样本不得出现检测到的第三方事实/动机补全等 regression flags。
- 生成器不得 fallback。

## 目录结构

| 路径 | 用途 |
|---|---|
| `baseline/` | 第一轮 F9 抽样、人工标注合并、F4 holdout 和信度报告。用于追溯历史人工验收。 |
| `error-analysis/` | 基于第一轮 40 条候选文本做的 AI 初标错误分析和 taxonomy 汇总。用于指导 F3/F4 修复，不替代人工 ER/IP/EX 标注。 |
| `validation/golden/` | 修订后对 golden 样本的生成结果，以及对旧坏候选的 F4 复评结果。用于判断 F3/F4 修改是否击中关键问题。 |
| `validation/rerun/` | 修订后重新生成的 40 条诊断包、对应 F4 holdout 和完整打分明细。当前仅作诊断，不推荐作为正式人工 F9 包。 |
| `validation/f9_validation_report.md` | 自动验收摘要，包含 Gate Decision、blocking reasons、golden、旧坏候选复评和 40 条重跑结果。 |

## 关键文件

### 第一轮 F9 基线

- `baseline/f9_blind_annotation.csv`：第一轮人工盲标表，不含 F4 分数。
- `baseline/f9_f4_scores_holdout.csv`：第一轮 F4 分数表，用 `sample_no` 对齐，人工标完后再合并。
- `baseline/f9_annotations_merged.csv`：第一轮人工标注和 F4 分数合并表。
- `baseline/f9_reliability_summary.csv`：第一轮信度统计明细。
- `baseline/f9_reliability_report.md`：第一轮信度报告。
- `baseline/f9_sampling_manifest.json`：第一轮抽样配置和样本来源。

### 错误分析

- `error-analysis/f9_error_analysis_draft.csv`：40 条候选文本的 AI 初标错误分析表。
- `error-analysis/f9_error_taxonomy_summary.md`：错误类型统计、F3/F4 修复方向、回归样本建议。

### 修订后自动验收

- `validation/golden/f9_golden_generated_scores.csv`：golden 样本重新生成候选和 F4 分数。
- `validation/golden/f9_golden_existing_f4_scores.csv`：旧坏候选重新交给当前 F4 打分的结果。
- `validation/rerun/f9_rerun_blind_annotation.csv`：新一轮 40 条盲标格式表，不含 F4 分数；当前作为诊断包保留。
- `validation/rerun/f9_rerun_f4_scores_holdout.csv`：新一轮 40 条 F4 分数表；若未来正式人工 F9 启动，人工标完后再合并。
- `validation/rerun/f9_rerun_selected_scores.csv`：新一轮 40 条完整自动打分明细，只用于内部诊断，不给人工标注者。
- `validation/rerun/f9_rerun_manifest.json`：新一轮自动验收运行配置。

## 推荐阅读顺序

1. 看 `validation/f9_validation_report.md`，确认当前 Gate Decision 和 blocking reasons。
2. 看 `error-analysis/f9_error_taxonomy_summary.md`，确认需要继续修的 F3/F4 问题类型。
3. 修 F4 后重跑 validation。
4. 只有 `Gate Decision: PASS` 后，再准备正式人工 F9。

## 常用命令

```powershell
python scripts\corpus\f9_sampling.py
python scripts\corpus\f9_reliability.py
C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation
python -m pytest -q
```
