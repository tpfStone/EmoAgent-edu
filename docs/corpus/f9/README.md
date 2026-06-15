# F9 产物与验收状态总览

> 先读主线：`docs/corpus/f9/f9-mainline.md`。该文档说明 F3、F4、F9 的职责边界、当前阻塞点和下一步决策顺序。

本目录保存 F9 人工信度、错误分析、以及 F3/F4 修订后的自动验收产物。当前核心状态是：**主 validation 包单次 PASS，但稳定性复跑未通过，暂不建议直接进入正式人工 F9**。F4 已收紧 ER/IP 高档定义并完成三次 post-erip validation，但三次仍因 rerun ER/IP=2 超过 32/40 而 FAIL；当前阻塞不再是 fallback 或 hard flags，而是 F4 高分侧仍未稳定。

## 当前判定

- 主包 `validation/f9_validation_report.md` 的 **Gate Decision：PASS**。
- 两次独立 stability rerun 的 **Gate Decision：FAIL**，阻塞项均为 rerun ER/IP 满分比例超过 32/40。
- F4 ER/IP 定义收紧后的三次 `post-erip` validation 仍 **Gate Decision：FAIL**：
  - `post-erip-run-1`：ER=2 40/40，IP=2 40/40
  - `post-erip-run-2`：ER=2 36/40，IP=2 37/40
  - `post-erip-run-3`：ER=2 38/40，IP=2 38/40
- **暂不建议把当前 rerun 包直接作为正式人工 F9 入口**，除非明确把它当作一次冻结样本包的单次记录，而不是 F3/F4 稳定准入通过。

自动验收的主要证据：

- F3 golden 回归：20 条生成候选中 sample-specific hard flags 为 0，global quality flagged rows 为 0/20。
- 旧坏候选 F4 复评：10/10 达到预期，ER/IP 同时 2/2 为 2/10。
- 新 40 条重跑包：sample-specific hard flags 为 0，global quality flagged rows 为 0/40，没有 fallback；ER=2 为 31/40，IP=2 为 31/40，均低于 32/40 上限。
- F3 已同步新的具体复述约束：承接必须点回孩子刚说的具体场景或动作，不能用“换谁都会”这类万能句单独充当承接。sample 2 的前半承接已有改善。
- `validation/rerun/f9_low_score_review_queue.csv` 的 3 行已完成人工抽查：sample 19/c2 的强行正向重构、sample 25/c2 的成人化引导、sample 36/c1 的模板化收束与关闭对话问题基本成立，未见明显矫枉过正。
- 稳定性复跑结果不稳定：`validation-stability/run-1` 为 ER=2 35/40、IP=2 36/40；`validation-stability/run-2` 为 ER=2 36/40、IP=2 36/40，均超过 32/40 上限。
- 对称抽查从当前主包 31 条 ER=2 中固定随机抽 5 条：sample 31/c2、3/c1、18/c2 的 ER/IP=2 基本站得住；sample 37/c2 符合“具体复述后补充泛化句”的现有规则但偏模板边缘；sample 39/c2 出现可见结构提示与成人化引导痕迹，不是干净的高分对照。
- 已执行 `f9-stability-gate-plan.md` 的非人工前置部分：F3 prompt 明确禁止括号式阶段标签，F4 增加代码侧内部提示外泄 hard boundary；并生成 `validation-stability/run-2/f9_high_score_diff_review_queue.csv`，共 8 行，已包含 `scenario` 和 `student_text`。
- high-score 差集已人工复核：sample 10/19 认可高分；sample 13/15/25/34/36/38 暴露 F4 高分侧问题。已据此收紧 F4 ER/IP 定义，但 post-erip 三次 validation 仍未过 gate。

## 接下来步骤

1. 暂缓正式人工 F9，不把当前 `validation/rerun/f9_rerun_blind_annotation.csv` 或 `post-erip` rerun 包直接发出。
2. 人工抽查 `post-erip-run-1` 中 40 条 ER/IP=2，判断这些 2 分是 F4 仍偏宽，还是 `32/40` 阈值已经不匹配当前 F3 输出分布。
3. 如果漏判为主，继续修 F4 高分侧；如果好候选为主，人工批准后再修订 `32/40` 阈值口径；如果混合，先修明确漏判再复跑。
4. 只有在后续复跑稳定落在批准阈值内，或明确调整并记录 gate 口径后，再启动正式人工 F9。

## 自动准入门槛

进入正式人工 F9 前，至少应满足：

- 旧坏候选 F4 复评通过率至少 80%，即 10 条中至少 8 条符合预期。
- 旧坏候选 ER/IP 同时 2/2 的比例不超过 20%，避免继续放过明显坏文本。
- 新 40 条重跑样本中 ER=2 与 IP=2 的比例都不超过 80%，不能接近全满分。
- F4 rationale 如果识别到模板化、第三方解释、事实补全、强行重构，分数必须实际降下来。
- F3 golden 和新 40 条重跑样本不得出现检测到的第三方事实/动机补全等 regression flags。
- F3 全局品质化总结探针在 golden generated rows 中最多 2/20，在 rerun selected rows 中最多 4/40。
- 生成器不得 fallback。

## 目录结构

| 路径 | 用途 |
|---|---|
| `baseline/` | 第一轮 F9 抽样、人工标注合并、F4 holdout 和信度报告。用于追溯历史人工验收。 |
| `error-analysis/` | 基于第一轮 40 条候选文本做的 AI 初标错误分析和 taxonomy 汇总。用于指导 F3/F4 修复，不替代人工 ER/IP/EX 标注。 |
| `validation/golden/` | 修订后对 golden 样本的生成结果，以及对旧坏候选的 F4 复评结果。用于判断 F3/F4 修改是否击中关键问题。 |
| `validation/rerun/` | 修订后重新生成的 40 条候选包、对应 F4 holdout 和完整打分明细。主包单次 PASS，但稳定性复跑未通过，当前只建议作为诊断包保留。 |
| `validation-stability/` | 不覆盖主包的独立稳定性复跑结果。用于判断当前 gate 是否受高温采样影响。 |
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
- `validation/rerun/f9_rerun_blind_annotation.csv`：新一轮 40 条盲标格式表，不含 F4 分数；当前因 stability rerun 失败，暂不建议作为正式人工 F9 入口。
- `validation/rerun/f9_rerun_f4_scores_holdout.csv`：新一轮 40 条 F4 分数表；正式人工 F9 标注完成后再合并。
- `validation/rerun/f9_rerun_selected_scores.csv`：新一轮 40 条完整自动打分明细，只用于内部诊断，不给人工标注者。
- `validation/rerun/f9_rerun_manifest.json`：新一轮自动验收运行配置。
- `validation-stability/run-1/f9_validation_report.md`：第一轮独立 stability rerun，Gate Decision 为 FAIL。
- `validation-stability/run-2/f9_validation_report.md`：第二轮独立 stability rerun，Gate Decision 为 FAIL。
- `validation-stability/run-2/f9_high_score_diff_review_queue.csv`：stability run-2 相对主包多出的 ER/IP=2 差集人工审查队列；包含 `scenario`、`student_text`、stability 候选与 F4 rationale，人工列需人工填写。
- `validation-stability/post-erip-run-1/f9_validation_report.md`、`post-erip-run-2/f9_validation_report.md`、`post-erip-run-3/f9_validation_report.md`：F4 ER/IP 高档定义收紧后的三次联网 validation，Gate Decision 均为 FAIL。

## 推荐阅读顺序

1. 看 `validation/f9_validation_report.md`，确认当前 Gate Decision 和 blocking reasons。
2. 看 `validation-stability/post-erip-run-1..3/f9_validation_report.md`，确认 F4 ER/IP 定义收紧后仍未通过稳定性 gate。
3. 看 `validation-stability/run-2/f9_high_score_diff_review_queue.csv`，了解上一轮人工差集复核如何导向本轮 F4 收紧。
4. 下一轮应从 `post-erip-run-1/rerun/f9_rerun_selected_scores.csv` 抽查 ER/IP=2 高分样本，再决定继续修 F4 还是修订 gate 阈值。

## 常用命令

```powershell
python scripts\corpus\f9_sampling.py
python scripts\corpus\f9_reliability.py
C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation
python -m pytest -q
```
