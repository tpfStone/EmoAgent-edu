# F4 成对比较择优 Phase A 实施计划

> **给自动化执行者：** 必须使用 `superpowers:executing-plans` 按任务逐项执行本计划。步骤使用复选框（`- [x]`）便于追踪。

**目标：** 构建离线 Phase A 成对比较（pairwise）试点工具链，不改变 `/chat` 的运行时默认择优逻辑。

**架构：** 新增一个聚焦的 `app/services/critic_pairwise.py` 模块，负责成对比较 prompt 构建、JSON 解析、正反两次换位判断、以及多次样本聚合。新增 F9 语料脚本，用于生成冻结候选对输入包、运行 pairwise judge、在同一批候选对上生成 pointwise 基线，并把 pairwise / pointwise 决策与新的人工 A/B 标注对齐评估。所有阶段 A 产物都放在 `docs/corpus/f9/pairwise-selection-pilot/` 下。

**技术栈：** Python 3.13、pytest、现有 `Settings`、现有 `LLMClientProtocol`、Python 标准库 CSV/JSON 工具。

---

### 任务 1：成对比较 Critic 核心

**文件：**
- 新建：`app/services/critic_pairwise.py`
- 测试：`tests/test_services/test_critic_pairwise.py`

- [x] **步骤 1：编写预期失败测试**

覆盖 JSON 解析、A/B 展示顺序到 `candidate_id` 的映射、正反两次独立换位判断的稳定性、无效结果处理、以及 3 次样本聚合。

- [x] **步骤 2：运行测试并确认 RED（预期失败）**

运行：`C:\Python313\python.exe -m pytest tests\test_services\test_critic_pairwise.py -q`

预期：因为缺少 `app.services.critic_pairwise`，导入失败。

- [x] **步骤 3：实现最小成对比较核心**

创建 `PairwiseCandidate`、`PairwiseSampleResult`、`PairwiseAggregateResult` 等 dataclass，创建 `CriticPairwiseService`，并实现 prompt 构建器、解析器、`judge_sample`、`aggregate_pairwise_samples`。

- [x] **步骤 4：运行测试并确认 GREEN（通过）**

运行：`C:\Python313\python.exe -m pytest tests\test_services\test_critic_pairwise.py -q`

预期：全部测试通过。

### 任务 2：冻结候选对输入包生成器

**文件：**
- 新建：`scripts/corpus/f9_pairwise_package.py`
- 测试：`tests/test_corpus/test_f9_pairwise_package.py`

- [x] **步骤 1：编写预期失败测试**

覆盖把 `generated_scores` 行按 `sample_no` 组成完整 `c1/c2` 候选对、跳过不完整候选对、写出带 UTF-8 BOM 的 CSV、以及生成空白人工 A/B 标注模板。

- [x] **步骤 2：运行测试并确认 RED（预期失败）**

运行：`C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_package.py -q`

预期：因为缺少脚本，导入失败。

- [x] **步骤 3：实现输入包生成器**

实现 `build_pair_rows()`、`write_pair_package()`、`build_annotation_rows()`、`write_annotation_template()`，并定义 `PAIR_PACKAGE_COLUMNS` 与 `HUMAN_ANNOTATION_COLUMNS`。

- [x] **步骤 4：运行测试并确认 GREEN（通过）**

运行：`C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_package.py -q`

预期：全部测试通过。

### 任务 3：成对比较 Judge 运行脚本

**文件：**
- 新建：`scripts/corpus/f9_pairwise_judge.py`
- 测试：`tests/test_corpus/test_f9_pairwise_judge.py`

- [x] **步骤 1：编写预期失败测试**

使用测试替身 `CriticPairwiseService` 覆盖运行明细行与汇总聚合行的生成，包括 `pairwise_sample_count=3`、稳定票数统计、无效计数、`pairwise_confidence`、以及运行清单（manifest）字段。

- [x] **步骤 2：运行测试并确认 RED（预期失败）**

运行：`C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_judge.py -q`

预期：因为缺少脚本，导入失败。

- [x] **步骤 3：实现 judge 运行脚本**

实现 CSV 读取、候选对行转换、重复调用 `judge_sample`、聚合、运行明细/汇总输出、运行清单（manifest）输出，并保证脚本可从仓库根目录直接运行。

- [x] **步骤 4：运行测试并确认 GREEN（通过）**

运行：`C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_judge.py -q`

预期：全部测试通过。

### 任务 4：成对比较评估报告

**文件：**
- 新建：`scripts/corpus/f9_pairwise_eval.py`
- 测试：`tests/test_corpus/test_f9_pairwise_eval.py`

- [x] **步骤 1：编写预期失败测试**

覆盖人工 A/B 标注对齐、从主一致性指标分母中排除人工 `tie/invalid` 行、排除 critic invalid/unstable 行、与 pointwise 基线对照、以及 Markdown 报告输出。

- [x] **步骤 2：运行测试并确认 RED（预期失败）**

运行：`C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_eval.py -q`

预期：因为缺少脚本，导入失败。

- [x] **步骤 3：实现评估器**

实现 `build_eval_rows()`、`summarize_eval_rows()`、`build_markdown_report()` 和输出写入函数。主指标只统计人工有效且 critic pairwise 稳定的样本。

- [x] **步骤 4：运行测试并确认 GREEN（通过）**

运行：`C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_eval.py -q`

预期：全部测试通过。

### 任务 4b：Pointwise 基线运行脚本

**文件：**
- 新建：`scripts/corpus/f9_pairwise_pointwise_baseline.py`
- 测试：`tests/test_corpus/test_f9_pairwise_pointwise_baseline.py`

- [x] **步骤 1：编写预期失败测试**

覆盖基于 `weighted_total` 的 pointwise winner 选择、平分检测、boundary 候选处理、带 UTF-8 BOM 的 CSV 输出、以及脚本可从仓库根目录直接运行。

- [x] **步骤 2：运行测试并确认 RED（预期失败）**

运行：`C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_pointwise_baseline.py -q`

预期：因为缺少脚本，导入失败。

- [x] **步骤 3：实现基线运行脚本**

对每个冻结候选对调用现有 pointwise `CriticService`，输出 `pointwise_winner`、`pointwise_tie`、两个候选的 `weighted_total` 与 boundary 标记，供 `f9_pairwise_eval.py` 对照使用。

- [x] **步骤 4：运行测试并确认 GREEN（通过）**

运行：`C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_pointwise_baseline.py -q`

预期：全部测试通过。

### 任务 5：文档与自动化验证

**文件：**
- 修改：`docs/corpus/f9/pairwise-selection-pilot/f4-pairwise-selection-pilot-plan.md`
- 修改：`docs/corpus/f9/pairwise-selection-pilot/phase-a-implementation-plan.md`

- [x] **步骤 1：更新试点方案中的已落地工具清单**

在 `f4-pairwise-selection-pilot-plan.md` 中新增或更新“已落地的阶段 A 工具”章节，列出新脚本、主要产物和测试命令。

- [x] **步骤 2：运行阶段 A 聚焦测试集**

运行：`C:\Python313\python.exe -m pytest tests\test_services\test_critic_pairwise.py tests\test_corpus\test_f9_pairwise_package.py tests\test_corpus\test_f9_pairwise_judge.py tests\test_corpus\test_f9_pairwise_pointwise_baseline.py tests\test_corpus\test_f9_pairwise_eval.py tests\test_corpus\test_f9_pairwise_cli.py -q`

预期：全部测试通过。

- [x] **步骤 3：运行相邻回归测试**

运行：`C:\Python313\python.exe -m pytest tests\test_services\test_critic_service.py tests\test_corpus\test_f9_fixed_candidate_rescore.py tests\test_corpus\test_f9_validation.py -q`

预期：全部测试通过。

- [x] **步骤 4：运行全量测试**

运行：`C:\Python313\python.exe -m pytest -q`

预期：全部测试通过。

---

## 人工指引与验收流程

### 检查结果

原计划已经包含自动化开发步骤和测试命令，但人工 A/B 标注步骤与阶段 A 验收流程不够明确。本节补齐这两部分，作为阶段 A 进入真实冒烟验证（smoke）/ 试点（pilot）的操作依据。

### 人工填写步骤

1. 先生成冻结候选对输入包和人工标注模板：

   ```powershell
   C:\Python313\python.exe scripts\corpus\f9_pairwise_package.py --input docs\corpus\f9\validation\golden\f9_golden_generated_scores.csv --output docs\corpus\f9\pairwise-selection-pilot\inputs\f9_pairwise_smoke_pairs.csv --annotation-output docs\corpus\f9\pairwise-selection-pilot\annotations\f9_pairwise_smoke_human_ab.csv
   ```

2. 人工打开 `docs/corpus/f9/pairwise-selection-pilot/annotations/f9_pairwise_smoke_human_ab.csv`，逐行阅读 `user_text`、`c1_text`、`c2_text`。人工标注时只看这三列和必要的上下文列，不参考 pointwise 分数、candidate id 以外的来源或模型判定结果。

3. 先按以下 A/B 判定标准形成偏好：
   - 先判硬性排除：文本损坏、上下文不足、两条都无法判断时填 `invalid`；一条明显越界、泄露内部提示、严重不适龄或强行诊断/承诺时，另一条胜并填写 `human_boundary_winner`。
   - 再判质量偏好：优先选择更回应用户真实情绪和诉求、更具体自然、更有陪伴感、不过度说教、不成人化复盘、不编造事实、不重复空泛的一条。
   - 两条都可用但难分高下，或两条都不太行且没有明确赢家时填 `tie`，不要为了制造偏好强行二选一。

4. 人工填写以下字段：
   - `human_preference`：只能填 `c1`、`c2`、`tie`、`invalid`。
   - `human_tie`：若两条难分高下，填 `true`，否则填 `false`。
   - `human_invalid`：若样本无法判断或文本损坏，填 `true`，否则填 `false`。
   - `human_boundary_winner`：若一条明显越界，填未越界候选；没有明显越界则留空。
   - `human_issue_type`：简短填写主要问题类型，例如 `泛化安慰`、`模板化`、`语义重复`、`缺少陪伴感`、`成人复盘感`、`事实补全`、`第三方开脱`、`内部提示外泄`、`格式异常`、`回应过短`、`无效二选一`、`不当安抚`。
   - `human_notes`：一句中文理由。
   - `annotator_id`：标注者代号。

5. 旧 pointwise 人工标注不能替代这一步。`ER/IP/EX` 三档分只作为背景证据，不是 A/B 偏好真值。

### 冒烟验证（Smoke）验收流程

1. 生成或确认 `f9_pairwise_smoke_pairs.csv` 与 `f9_pairwise_smoke_human_ab.csv`。
2. 人工完成 `f9_pairwise_smoke_human_ab.csv`。
3. 运行 pairwise judge：

   ```powershell
   $env:LLM_TIMEOUT='60'
   C:\Python313\python.exe scripts\corpus\f9_pairwise_judge.py --pair-package docs\corpus\f9\pairwise-selection-pilot\inputs\f9_pairwise_smoke_pairs.csv --output-dir docs\corpus\f9\pairwise-selection-pilot\runs\smoke --pairwise-sample-count 3
   ```

4. 运行 pointwise baseline：

   ```powershell
   C:\Python313\python.exe scripts\corpus\f9_pairwise_pointwise_baseline.py --pair-package docs\corpus\f9\pairwise-selection-pilot\inputs\f9_pairwise_smoke_pairs.csv --output docs\corpus\f9\pairwise-selection-pilot\runs\smoke\f9_pairwise_pointwise_baseline.csv
   ```

   真实 LLM smoke 若默认 3-sample pointwise baseline 运行过慢，可临时设置 `$env:CRITIC_SAMPLE_COUNT='1'` 生成快速对照；正式 pilot 报告必须记录实际 sample count。

5. 人工标注完成后运行 eval：

   ```powershell
   C:\Python313\python.exe scripts\corpus\f9_pairwise_eval.py --pairwise-summary docs\corpus\f9\pairwise-selection-pilot\runs\smoke\f9_pairwise_judge_summary.csv --human-annotations docs\corpus\f9\pairwise-selection-pilot\annotations\f9_pairwise_smoke_human_ab.csv --pointwise-baseline docs\corpus\f9\pairwise-selection-pilot\runs\smoke\f9_pairwise_pointwise_baseline.csv --output-dir docs\corpus\f9\pairwise-selection-pilot\reports\smoke
   ```

6. 冒烟验证通过标准：
   - 人工模板 10 行均有明确填写，除非标为 `invalid`。
   - pairwise judge 无解析失败（parse failure）或超时（timeout）。
   - `f9_pairwise_eval_report.md` 成功生成。
   - `critic_human_agreement`、`pointwise_human_agreement`、`agreement_delta_vs_pointwise` 均可读且分母正确。

### 本轮 Smoke 结果记录

本轮真实 pairwise smoke 已完成，结果文件位于：
- `docs/corpus/f9/pairwise-selection-pilot/runs/smoke/`
- `docs/corpus/f9/pairwise-selection-pilot/reports/smoke/`

运行口径：
- pairwise judge 使用真实 LLM，`pairwise_sample_count=3`，并设置 `LLM_TIMEOUT=60`。
- 默认 3-sample pointwise baseline 在真实 API 下运行超过 30 分钟未完成；当前 smoke eval 中的 pointwise 对照为快速诊断口径，使用 `CRITIC_SAMPLE_COUNT=1`，不能当作正式 pilot pointwise 结论。

核心结果：
- `total_pairs=10`
- `human_valid_pairs=8`
- pairwise judge 无 invalid：`0/10`
- pairwise stable：`8/10`
- `critic_valid_pairs=6`
- `pairwise_matches=3`
- `critic_human_agreement=0.500`
- `pointwise_valid_pairs=5`
- `pointwise_matches=3`
- `pointwise_human_agreement=0.600`
- `agreement_delta_vs_pointwise=-0.100`
- `human_tie_rate=0.200`

结论修正：本轮 smoke 工具链跑通，但 agreement 数字不能用于判断 pairwise 是否优于或劣于 pointwise。原因是有效分母过小、pairwise 与 pointwise 使用的 valid 集不一致、pointwise 对照为 `CRITIC_SAMPLE_COUNT=1` 快速诊断口径，且 smoke 输入候选本身存在 `无效二选一`、`不当安抚`、`格式异常`、`缺少陪伴感` 等明显噪声。因此本轮唯一稳妥结论是：工具链可用、pairwise judge 无 invalid、格式未崩；不能上线，也不能切换为 `/chat` 默认择优器。

下一步仍属于 Phase A，不是 Phase B。后续按 `docs/corpus/f9/pairwise-selection-pilot/phase-a-rerun-plan.md` 执行 Phase A rerun / Phase A.2：先修 F3 prompt、补 provenance、改 eval 交集口径、显式化模型，再用修复后的真实 F3 重新生成 15-20 对 human-valid 主集。

### 试点（Pilot）验收流程

1. 冒烟验证通过后，将输入包扩展到 30-40 对 human-valid 样本。
2. 对试点主集重复同样的人工 A/B 标注、pairwise judge、pointwise 基线、评估流程。
3. 试点建议通过标准：
   - 主集不少于 30 对 human-valid 样本。
   - `pairwise_parse_failure_rate <= 5%`。
   - `pairwise_stable_rate >= 70%`。
   - `critic_human_agreement >= 70%`。
   - `agreement_delta_vs_pointwise >= +10pp`。
   - `boundary_selection_error_count = 0`。
4. 未达到以上标准时，不得把 pairwise 切换为 `/chat` 默认择优器，也不得把 `pointwise_tiebreak` 结果喂给 DPO。
