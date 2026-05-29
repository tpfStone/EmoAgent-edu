# F9 产物与验收状态总览

本目录保存 F9 人工信度、错误分析、F3/F4 修订后的自动验收产物，以及 F4 pairwise preference-pair pilot。当前需要分清两条线：

- **Pointwise reliability diagnostics**：围绕旧 F4 EPITOME/CASEL pointwise 分数、ER/IP 高分饱和和 F3/F4 质量偏差展开。该线用于解释历史实现和定位问题，不再作为新的 DPO 主线。
- **Pairwise preference-pair pilot**：围绕人工 A/B、critic pairwise、pointwise baseline 交集评估和偏好对来源验证展开。该线是 F4 目标主线，但 Phase A rerun 结论仍为 `inconclusive`，尚未解锁 `/chat` runtime 切换或 DPO。

正式人工 F9 仍暂停。旧 pointwise validation 主包单次 PASS，但稳定性复跑未通过；pairwise pilot 工具链可用，但当前样本、候选质量和判定稳定性不足以证明 pairwise 优于 pointwise。

## 当前判定

### Pointwise 诊断线

- 主包 `validation/f9_validation_report.md` 的 **Gate Decision：PASS**。
- 两次独立 stability rerun 的 **Gate Decision：FAIL**，阻塞项均为 rerun ER/IP 满分比例超过 32/40。
- F4 ER/IP 定义收紧后的三次 `post-erip` validation 仍 **Gate Decision：FAIL**：
  - `post-erip-run-1`：ER=2 40/40，IP=2 40/40
  - `post-erip-run-2`：ER=2 36/40，IP=2 37/40
  - `post-erip-run-3`：ER=2 38/40，IP=2 38/40
- R8 priority 10 条人工复核显示候选质量普遍偏差：ER 仅 1/10 被人工认可应得 2，IP 0/10 被人工认可应得 2。
- R10 已将 F4 critic 单独切到 `deepseek-v4-pro`、`CRITIC_LLM_MAX_TOKENS=4096`、JSON response format；F3 generator 仍保留 `deepseek-chat`，避免生成和打分变量混在一起。v4-pro JSON smoke 可跑通，但只把人工一致性从 10/20 小幅提高到 11/20。
- **暂不建议把任何现有 rerun 包直接作为正式人工 F9 入口**，除非明确把它当作一次冻结样本包的诊断记录，而不是 F3/F4 稳定准入通过。

### Pairwise 主线

- Phase A smoke：工具链跑通，但 agreement 数字不能用于判断 pairwise 是否优于 pointwise。
- Phase A rerun：`comparison_intersection_pairs=7`，低于计划下限 `12`；`critic_human_agreement=0.429`，`agreement_delta_vs_pointwise=0.000`。
- 结论：`inconclusive`。不能进入 Phase B，不能把 `/chat` 切到 pairwise，不能把本轮 pairwise stable 输出进入 DPO。
- 诊断：stable pairwise winner 明显偏向 `c1`，人工有效偏好接近平衡；详见 `pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_c1_collapse_diagnostic.md`。
- 下一步：先修 F3 候选生成、输入包冻结/清洗和 pairwise 判定稳定性，再 rerun。

## Pointwise 历史轮次

原主线说明已合并到本 README，主线历史保留为下表；更细的执行日志见 `pointwise-diagnostics/execution-summary.md`。

| 轮次 | 起因 | 主要修改 | 验证结果 | 结论 / 下一步 |
|---|---|---|---|---|
| R0 | 第一轮 F9 暴露坏候选也能拿高 ER/IP | 做 F9 error analysis，拆出 F3 生成问题与 F4 判分问题 | 确认问题不是单点样本，而是 F3/F4 组合失稳 | 先回修 F4，再回修 F3 |
| R1 | F4 放过旧坏候选 | F4 加 `audit_tags`、deterministic caps，拆分轻重事实补全 | 旧坏候选复评 10/10 达标，ER/IP 2/2 为 2/10；但 F3 sample 25 仍有 `说明你` | F4 第一轮达标，转向 F3 残留 |
| R2 | F3 品质化总结、固定转折仍被探针捕获 | 扩展 global quality probes，收紧 F3 prompt，输出 low-score review queue | hard flags 清零，但 rerun_ER_2=37/40、rerun_IP_2=38/40 | F3 字符串问题缓解，F4 高分饱和重新暴露 |
| R3 | “换谁都会”式承接让引导反思型显得疏离 | F3 增加具体复述约束 | 主包单次 PASS：ER=2 31/40，IP=2 31/40；low-score review 3 行人工确认合理 | 主包擦边过，需要 stability rerun |
| R4 | 担心主包 PASS 是采样运气 | 独立跑 `validation-stability/run-1` 与 `run-2` | run-1：ER=2 35/40、IP=2 36/40；run-2：ER=2 36/40、IP=2 36/40 | 主包 PASS 不稳定，不能进正式人工 F9 |
| R5 | sample 39 出现内部结构提示外泄 | F3 禁止括号式阶段标签；F4 增加 `internal_prompt_leak` hard boundary；生成 high-score diff review queue | 生成 8 行 high-score 差集：10、13、15、19、25、34、36、38 | sample 39 属确定 bug；差集交给人工判断 |
| R6 | 人工复核 high-score diff 后发现 6/8 高分不成立 | 不新增 tag、不改阈值，先收紧 F4 ER/IP 高档定义 | sample 10/19 认可高分；sample 13/15/25/34/36/38 暴露“缺陪伴感”和“显性情绪当隐含理解” | F4 ER/IP=2 必须有陪伴感和未明说洞察 |
| R7 | 需要验证 F4 ER/IP 定义收紧是否解决高分饱和 | 更新 F4 spec、runtime prompt 与 prompt 断言测试；联网三次 post-erip validation | 三次均 FAIL：40/40、36/37、38/38；fallback=0，rerun hard flags=0 | prompt 收紧不足以解决高分饱和 |
| R8 | R7 仍无法区分 F3 批次方差和 F4 judge 方差 | 固定 run-2 候选复评：count=1 看原始抖动，count=3 看 median 稳定性；生成 run-2 双侧人工校准队列 | count=1：ER 1/2 flip 1、IP 1/2 flip 2；count=3：ER 1/2 flip 1、IP 1/2 flip 1；全量队列 48 行 | 先人工填写 10 条 priority review，再决定是否需要看 backup |
| R9 | priority 10 条人工复核显示候选普遍质量差 | 固定这 10 条候选，做 F4-only 模型对照：`deepseek-chat` baseline vs `deepseek-v4-pro` | baseline 完成；v4-pro 完整 3 repeats 超时，fallback pilot 10/10 `llm_parse_failure` | 失败根因待查，不能把 0/0 当成有效判分 |
| R10 | R9 显示 v4-pro 未跑通，需要正式兼容新模型 | 诊断 raw response；F4 单独使用 `deepseek-v4-pro`、4096 token、JSON response format；F3 仍用 `deepseek-chat` | v4-pro JSON smoke 10/10 无 parse failure；priority 匹配从 10/20 到 11/20 | 新模型已接入 F4，但改善有限；下一步仍要处理 F3 生成质量和 F4 ER 偏宽 |

## 当前阻塞点

1. **候选质量与高分判断仍有系统偏差。** R8 priority 10 条人工判断中，ER 仅 1/10 认可应得 2，IP 0/10 认可应得 2；问题集中在语义重复、没有真正承接安慰、像复盘或说教。
2. **F4 已切新模型，但不是完整修复。** v4-pro 已能以 JSON mode 跑通，但 smoke 只带来小幅改善，不能单靠模型升级解锁正式 F9。
3. **正式人工 F9 不能启动。** 候选质量、F4 judge 口径和人工锚点都还不足够明确，任一现有 rerun 包都不能直接作为正式入口。

## 下一步决策

1. 如果继续模型路线：跑 priority 10 的 `CRITIC_SAMPLE_COUNT=3` 完整 v4-pro 对照，确认 smoke 的 11/20 是否稳定。
2. 如果接受 smoke 已足够判断：转向 F3 生成策略，减少“复述 + 加深情绪 + 分析提问”的默认生成模式。
3. 如果担心成本：把 v4-pro 定位成离线复核模型，而不是实时全量 judge。
4. 在这个分支未决前，不启动正式人工 F9。

## 自动验收证据

- F3 golden 回归：20 条生成候选中 sample-specific hard flags 为 0，global quality flagged rows 为 0/20。
- 旧坏候选 F4 复评：10/10 达到预期，ER/IP 同时 2/2 为 2/10。
- 新 40 条重跑包：sample-specific hard flags 为 0，global quality flagged rows 为 0/40，没有 fallback；ER=2 为 31/40，IP=2 为 31/40，均低于 32/40 上限。
- F3 已同步新的具体复述约束：承接必须点回孩子刚说的具体场景或动作，不能用“换谁都会”这类万能句单独充当承接。sample 2 的前半承接已有改善。
- `validation/rerun/f9_low_score_review_queue.csv` 的 3 行已完成人工抽查：sample 19/c2 的强行正向重构、sample 25/c2 的成人化引导、sample 36/c1 的模板化收束与关闭对话问题基本成立，未见明显矫枉过正。
- 稳定性复跑结果不稳定：`validation-stability/run-1` 为 ER=2 35/40、IP=2 36/40；`validation-stability/run-2` 为 ER=2 36/40、IP=2 36/40，均超过 32/40 上限。
- 对称抽查从当前主包 31 条 ER=2 中固定随机抽 5 条：sample 31/c2、3/c1、18/c2 的 ER/IP=2 基本站得住；sample 37/c2 符合“具体复述后补充泛化句”的现有规则但偏模板边缘；sample 39/c2 出现可见结构提示与成人化引导痕迹，不是干净的高分对照。
- 已执行 `plans/stability-gate-plan.md` 的非人工前置部分：F3 prompt 明确禁止括号式阶段标签，F4 增加代码侧内部提示外泄 hard boundary；并生成 `validation-stability/run-2/f9_high_score_diff_review_queue.csv`，共 8 行，已包含 `scenario` 和 `student_text`。
- high-score 差集已人工复核：sample 10/19 认可高分；sample 13/15/25/34/36/38 暴露 F4 高分侧问题。已据此收紧 F4 ER/IP 定义，但 post-erip 三次 validation 仍未过 gate。

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
| `validation/` | 主 validation 包。包含 golden 回归、旧坏候选复评、新 40 条 rerun 包和自动验收报告。 |
| `validation-stability/` | 不覆盖主包的独立稳定性复跑、post-erip 三连跑、固定候选复评和模型评测产物。用于判断 gate 是否受高温采样或 judge 抖动影响。 |
| `pairwise-selection-pilot/` | F4 pairwise 离线试点输入包、人工 A/B 标注、judge 运行结果、pointwise baseline 和 Phase A rerun 报告。当前结论为 `inconclusive`。 |
| `plans/` | F3/F4 pointwise 诊断线的历史执行计划：generator 修复、critic 修复、stability gate、model eval。 |
| `pointwise-diagnostics/` | pointwise 线执行总结和轮次细节。 |

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

- `validation/f9_validation_report.md`：自动验收摘要，包含 Gate Decision、blocking reasons、golden、旧坏候选复评和 40 条重跑结果。
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
- `validation-stability/model-eval/`：R9/R10 F4-only 模型对照与 JSON smoke 产物。
- `validation-stability/r8-fixed-rescore/`：固定候选复评产物，用于区分 F4 judge 抖动和 F3 生成批次方差。

### Pointwise 计划和总结

- `plans/f3-generator-fix-plan.md`：F3 generator 修复计划。
- `plans/f4-critic-fix-plan.md`：F4 critic 修复计划。
- `plans/stability-gate-plan.md`：稳定性 gate 与 high-score diff queue 的执行计划。
- `plans/model-eval-plan.md`：F4-only 模型因素调研计划。
- `pointwise-diagnostics/execution-summary.md`：F3/F4/F9 pointwise 线执行总结、测试命令和 validation 指标。

### Pairwise pilot

- `pairwise-selection-pilot/f4-pairwise-selection-pilot-plan.md`：F4 pairwise 大轮试验方案。
- `pairwise-selection-pilot/phase-a-rerun-plan.md`：Phase A rerun 的去噪、provenance、模型显式化和交集评估计划。
- `pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md`：当前 rerun 结论，正式状态为 `inconclusive`。
- `pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_c1_collapse_diagnostic.md`：`c1` 偏斜诊断与后续处理建议。
- `pairwise-selection-pilot/reports/f3-model-sidecar/f3_flash_pro_sidecar_report.md`：F3 flash/pro 侧线对照，仅比较候选质量，不混入 Phase A rerun 主指标。

## 推荐阅读顺序

1. 看本 README 的“当前判定”“Pointwise 历史轮次”“当前阻塞点”，确认 pointwise 诊断线的 R0-R10 历史和当前阻塞。
2. 看 `pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md`，确认 pairwise 主线当前为何不能上线。
3. 看 `pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_c1_collapse_diagnostic.md`，了解 pairwise judge 偏斜与输入包问题。
4. 如需追溯 pointwise 执行细节，再看 `pointwise-diagnostics/execution-summary.md`、`validation-stability/post-erip-run-1..3/f9_validation_report.md` 和 `validation-stability/run-2/f9_high_score_diff_review_queue.csv`。

## 常用命令

```powershell
python scripts\corpus\f9_sampling.py
python scripts\corpus\f9_reliability.py
C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation
python -m pytest -q
```
