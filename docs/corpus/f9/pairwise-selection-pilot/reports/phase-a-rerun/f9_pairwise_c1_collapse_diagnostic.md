# F9 Pairwise C1 Collapse Diagnostic

日期：2026-05-28

## 当前可执行结论：C1 最小防污染项

本文保留 `C1 collapse` 作为历史问题名；正文中的准确含义是 **`c1` 候选槽位塌缩**。Phase A.2 的 `c1/c2` 同时绑定了候选槽位、取向标签和具体文本，旧结果只能作为诊断证据，不能作为新 IRI 取向下的正式偏好结论。

Phase A.3 前置的最小防污染项是：

- `c1/c2` 只表示候选槽位，不表示取向。
- pairwise prompt 匿名化：不展示 `candidate_id`，不展示 `orientation`，只展示 `回应A` / `回应B` 的文本。
- 保留 A/B 双向换位，并继续把 A/B 展示位映射回候选槽位。
- 保留 raw pattern gate，报告 `A/B` 原始模式与候选槽位映射后的稳定性。
- eval 必须按候选槽位、取向、raw pattern 分层输出 winner 分布。
- 下一版冻结输入包必须记录原始取向到最终候选槽位的映射，且正式包应均衡或随机映射 `情感共情型` / `认知共情型` 到 `c1/c2`。

执行口径：Step 1/2/3 是 Phase A.2 已完成的历史诊断证据；Step 4 是 Phase A.3 默认 judge 口径；Step 5 已迁移到 Phase A.3 的冻结输入包与 eval 实施计划，不在旧诊断轮直接执行。

## 文档归属

本文记录 Phase A rerun 后发现的 `c1` 塌缩问题、当前已完成的检查、诊断设计，以及后续处理方案。

放置位置：`docs/corpus/f9/pairwise-selection-pilot/reports/phase-a-rerun/`。

原因：该问题来自 Phase A rerun 的真实产物分析，属于 rerun 诊断报告，不是顶层试验方案，也不是新的 Phase B 运行时设计。顶层计划只保留阶段口径和门槛，避免把单轮诊断细节混入长期方案。

相关文件：

- `docs/corpus/f9/pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md`
- `docs/corpus/f9/pairwise-selection-pilot/runs/phase-a-rerun/f9_pairwise_judge_runs.csv`
- `docs/corpus/f9/pairwise-selection-pilot/runs/phase-a-rerun/f9_pairwise_judge_summary.csv`
- `app/services/critic_pairwise.py`
- `tests/test_services/test_critic_pairwise.py`

## 问题描述

Phase A rerun 的 pairwise summary 中，`pairwise_stable=true` 的聚合 winner 全部为 `c1`：

```text
stable pairwise winner: c1 = 14/14
stable pairwise winner: c2 = 0/14
```

但人工有效偏好接近平衡：

```text
human-valid: c1 = 7, c2 = 8
```

这说明当前 pairwise judge 的稳定输出与人工偏好不一致，且存在明显偏斜。该问题暂称为 `c1 collapse`，准确说是 `c1` 候选槽位塌缩；但不能预设根因一定是 `c1` 列 bug，需要区分以下三类可能：

1. 代码层映射或聚合 bug：A/B 展示位映射回 `candidate_id` 时出错，或聚合时硬绑 `c1`。
2. 展示位偏置：真实 LLM 偏好展示位 A 或 B，即使双向换位后也产生大量位置冲突。
3. 风格/标签偏好：LLM 偏好 Phase A.2 历史标签中的 `共情型` 风格，或受 prompt 中暴露的 `c1/c2`、`orientation` 标签影响。

## 当前检查结果

### 1. 代码层现状

`CriticPairwiseService.judge_sample()` 当前确实执行了双向换位：

```python
first = await self._judge_order(context, candidate_a, candidate_b)
second = await self._judge_order(context, candidate_b, candidate_a)
```

A/B 展示位到候选 id 的回映射由 `_map_display_winner()` 完成：

```python
if winner == "A":
    return first.candidate_id
if winner == "B":
    return second.candidate_id
```

因此从静态代码看，没有明显的 “A 位直接等于 c1” 硬编码。

基于上述双向换位，单个 pairwise sample 的两次调用应按以下真值表解释：

```text
call 1: A=c1, B=c2
call 2: A=c2, B=c1
```

| call 1 raw winner | call 2 raw winner | candidate-id 结果 | 期望 sample |
|---|---|---|---|
| A | B | c1, c1 | stable c1 |
| B | A | c2, c2 | stable c2 |
| A | A | c1, c2 | unstable |
| B | B | c2, c1 | unstable |
| tie | 任意 | None / 任意 | unstable |
| 任意 | tie | 任意 / None | unstable |

### 2. 初始 mock 测试覆盖与补齐项

补齐前已运行：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_critic_pairwise.py -q
```

结果：

```text
7 passed
```

当时测试已覆盖：

- `A` then `B` 可映射为同一候选并 stable。
- 恒定返回 `A` 位会被识别为 unstable。
- 聚合支持 `majority_with_unstable`、`split_majority`、`invalid`。

当时仍缺少的代码层检查：

- 精确断言 prompt 内容换位：第一次 `回应A=AAA, 回应B=BBB`；第二次 `回应A=BBB, 回应B=AAA`。
- 恒定返回 `B` 位的对称测试。
- 原始 A/B 判定组合真值表测试。

这些检查已在 Step 1/2 执行记录中补齐，再进入真实 LLM 对照。

### 3. 当前真实 run 的 raw pattern

从 `f9_pairwise_judge_runs.csv` 聚合单个 sample 的两次换位结果：

```text
judgment_1_winner_id, judgment_2_winner_id, stable
c1, c1, true      = 42
c1, c2, false     = 28
c2, c2, true      = 2
c2, c1, false     = 0
```

解读：

- `c1,c2,false` 表示两次都偏展示位 A，是直接的 A 位偏置证据。
- 但 stable 样本中仍大量为 `c1,c1,true`，说明问题不只是展示位 A 偏置。
- `c2,c2,true` 只有 2 次，说明当前 judge 对 `c2` 的内容或标签偏好很弱。
- 物理对调后若仍稳定输出新的 `c1`，不能直接称为 A 位偏置；在当前双向换位实现下，更准确的解释是候选列偏置、标签诱导，或二者与内容偏好的混合。真正的 A 位偏置应看 `judgment_1_winner_id=c1` 且 `judgment_2_winner_id=c2` 这类 raw position conflict。

### 4. Prompt 暴露标签导致变量混淆

当前 pairwise prompt 暴露了候选 id 和取向：

下列 `共情型/引导反思型` 是 Phase A.2 历史标签，用来解释旧产物中的污染来源，不是 Phase A.3 的取向定义。

```text
【回应A】(c1, 共情型) ...
【回应B】(c2, 引导反思型) ...
```

这会把以下变量绑在一起：

- 展示位：A/B
- 候选槽位：c1/c2
- 取向标签：Phase A.2 历史标签 `共情型/引导反思型`
- 实际文本内容

因此，仅凭 “stable winner 全部是 c1” 无法区分是列偏置、风格偏好，还是标签诱导。

## 诊断方案与后续处理

诊断顺序采用“先 mock、再无 API 汇总、再真实 LLM 小对照、最后定性”的路径。第一段不调用 LLM，用来先排除最便宜、最确定的代码层错误；只有代码层诊断通过后，才进入真实 LLM 对照。

### Step 1：补代码层诊断测试（已完成，历史诊断证据）

优先补 `tests/test_services/test_critic_pairwise.py`：

1. `test_judge_sample_prompt_swaps_candidate_texts`
   - 使用 `c1.text="AAA"`、`c2.text="BBB"`。
   - 断言第一次 prompt 中 `回应A` 对应 `AAA`、`回应B` 对应 `BBB`。
   - 断言第二次 prompt 中 `回应A` 对应 `BBB`、`回应B` 对应 `AAA`。

2. `test_judge_sample_marks_b_position_conflict_unstable`
   - fake judge 两次都返回 `B`。
   - 期望 `judgment_1_winner_id=c2`、`judgment_2_winner_id=c1`、`stable=false`。

3. `test_judge_sample_raw_ab_truth_table`
   - 枚举 `A/B`、`B/A`、`A/A`、`B/B`。
   - 断言分别对应 `stable c1`、`stable c2`、`unstable`、`unstable`。

验证命令：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_critic_pairwise.py -q
```

### Step 2：补无 API 诊断汇总（已完成，历史诊断证据）

在不重跑 LLM 的前提下，从既有 `f9_pairwise_judge_runs.csv` 生成或记录 raw pattern：

```powershell
$rows = Import-Csv -Encoding UTF8 docs\corpus\f9\pairwise-selection-pilot\runs\phase-a-rerun\f9_pairwise_judge_runs.csv
$rows | Group-Object judgment_1_winner_id,judgment_2_winner_id,stable | Select-Object Name,Count
```

该统计应作为后续报告的一部分，避免只看 summary 的 `winner_id`。

### Step 1/2 执行记录

执行时间：2026-05-28。

已完成：

- 已补 `tests/test_services/test_critic_pairwise.py` 中的 prompt 换位断言、恒定 `B` 展示位冲突测试、以及 `A/B` raw winner 真值表测试。
- 新增 `test_judge_sample_prompt_hides_candidate_metadata`，先确认当前 prompt 会泄露 `candidate_id` / `orientation`，再修正 prompt。
- 已将 `app/services/critic_pairwise.py` 的 pairwise prompt 临时调整为只展示匿名 `回应A` / `回应B` 文本，不再展示 `candidate_id` 和 `orientation`，并加入“忽略回应 A/B 的呈现顺序，只比较两条回应文本本身”。
- 已复核既有 rerun raw pattern：

```text
c1, c1, true   = 42
c1, c2, false  = 28
c2, c2, true   = 2
c2, c1, false  = 0
```

验证命令与结果：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_critic_pairwise.py -q
```

```text
14 passed
```

```powershell
C:\Python313\python.exe -m pytest -q
```

```text
156 passed
```

结论：mock 层未复现 A/B 到 `candidate_id` 的映射 bug；当前更应继续验证真实 LLM 的位置偏置、内容/风格偏好、以及标签诱导。

### Step 3：修正真实 LLM 对照设计（已完成，历史诊断证据）

真实 LLM 对照应拆成三类，不要只做一个物理对调：

1. 物理交换 `c1/c2` 文本与 orientation。
   - 目的：看 judge 是否跟内容/风格走。
   - 若 winner 跟着共情型内容移动，说明风格偏好强。
   - 若仍偏 `c1`，说明候选列或标签偏置强。

2. identical text 对照。
   - 两边文本完全相同。
   - 两边 orientation 也应设为相同或隐藏，否则仍有标签变量。
   - 期望输出 tie 或 unstable。
   - 若稳定选某一展示位或列，说明存在非内容偏置。

3. 隐藏标签对照。
   - prompt 中只展示 `回应A` / `回应B` 的文本。
   - 不展示 `(c1, 共情型)`、`(c2, 引导反思型)`；这里的取向名是 Phase A.2 历史标签。
   - 目的：隔离 “候选 id / orientation 标签诱导”。

### Step 3 执行记录

执行时间：2026-05-28。

执行方式：使用真实 DeepSeek critic LLM，对 6 个样本做小对照；样本覆盖亲子摩擦、同伴关系、学业压力各 2 个。每个 variant 使用 `pairwise_sample_count=3`，即每组 18 个 pairwise sample、36 次 LLM order 调用。

输入包：

- `docs/corpus/f9/pairwise-selection-pilot/inputs/phase-a-rerun-step3-controls/f9_pairwise_step3_hidden_label_original_pairs.csv`
- `docs/corpus/f9/pairwise-selection-pilot/inputs/phase-a-rerun-step3-controls/f9_pairwise_step3_physical_swap_pairs.csv`
- `docs/corpus/f9/pairwise-selection-pilot/inputs/phase-a-rerun-step3-controls/f9_pairwise_step3_identical_text_pairs.csv`

输出目录：

- `docs/corpus/f9/pairwise-selection-pilot/runs/phase-a-rerun-step3-controls/hidden-label-original/`
- `docs/corpus/f9/pairwise-selection-pilot/runs/phase-a-rerun-step3-controls/physical-swap/`
- `docs/corpus/f9/pairwise-selection-pilot/runs/phase-a-rerun-step3-controls/identical-text/`

同一 6 样本在既有 Phase A rerun 旧 prompt 下的 baseline：

```text
raw pattern:
c1, c1, true   = 12
c1, c2, false  = 6
c2, c2, true   = 0
c2, c1, false  = 0

summary:
c1 stable      = 4/6
c2 stable      = 0/6
unstable       = 2/6
```

隐藏标签、原始文本对照：

```text
raw pattern:
c1, c1, true   = 11
c2, c2, true   = 3
c1, c2, false  = 3
c2, c1, false  = 1

summary:
c1 stable      = 3/6
c2 stable      = 1/6
unstable       = 2/6
```

物理交换 `c1/c2` 文本与 orientation 后：

```text
raw pattern:
c2, c2, true   = 9
c1, c1, true   = 4
c1, c2, false  = 3
c2, c1, false  = 2

summary:
c2 stable      = 3/6
c1 stable      = 1/6
unstable       = 2/6
```

identical text 对照：

```text
raw pattern:
None, None, false = 18

summary:
unstable       = 6/6
stable winner  = 0/6
```

逐样本关键观察：

| sample | hidden-label original | physical swap | 解读 |
|---|---|---|---|
| sample-1 | unstable | unstable | 无稳定偏好 |
| sample-11 | stable c1 unanimous | stable c2 unanimous | winner 跟随原 c1 内容移动 |
| sample-2 | stable c1 unanimous | stable c2 unanimous | winner 跟随原 c1 内容移动 |
| sample-3 | stable c2 split-majority | unstable | 对原 c2 内容有弱偏好，但不稳定 |
| sample-6 | stable c1 majority-with-unstable | stable c2 split-majority | winner 大体跟随原 c1 内容移动 |
| sample-7 | unstable | stable c1 majority-with-unstable | 对原 c2 内容有弱偏好 |

Step 3 结论：

- identical text 全部返回 tie/unstable，没有稳定选择 A/B 或 `c1/c2`，说明在隐藏标签 prompt 下未复现纯展示位或纯候选列偏置。
- 物理交换后，原先偏 `c1` 的多个样本转为偏 `c2`，说明 winner 主要跟随文本内容/风格移动，而不是固定跟随 `candidate_id=c1`。
- 隐藏标签后，6 样本子集的 `c1` 稳定 winner 从旧 prompt 的 `4/6` 降到 `3/6`，并首次出现 `c2 stable=1/6`；标签暴露不是唯一根因，但确实污染了判断。
- 仍存在少量 `c1,c2,false` 与 `c2,c1,false` raw position conflict；这些冲突已被 sample 层判为 unstable，后续报告应继续保留 raw pattern gate。

当前判断：`c1` 候选槽位塌缩不是代码层映射 bug，也不是隐藏标签 prompt 下的纯位置偏置；更像是旧 prompt 标签暴露与内容/风格偏好共同造成的混合问题。

### Step 4：F4 prompt 匿名化（Phase A.3 默认 judge 口径）

Step 1/2/3 已完成且未发现代码层映射 bug；Phase A.3 的 F4 prompt 应至少做以下改动：

- prompt 中不展示 `candidate_id`。
- prompt 中不展示 `orientation`。
- 只展示匿名 `回应A`、`回应B`。
- 保留代码侧 A/B 到 candidate_id 的映射。
- 在 judge 指令中加入“忽略呈现顺序”，但不要把这当成唯一去偏手段；核心仍是双向换位和 raw pattern 诊断。

### Step 5：冻结输入包设计修正（迁移到 Phase A.3 实施）

后续冻结输入包不应固定 `c1=共情型`、`c2=引导反思型`。这里的绑定是 Phase A.2 历史问题；Phase A.3 应使用 `情感共情型` / `认知共情型`，并让取向与候选槽位解耦。建议：

- 在 package 阶段随机或均衡 `c1/c2` 的取向分配。
- manifest 中记录原始取向与最终候选槽位的映射。
- eval 报告同时输出按取向和候选槽位分层的 winner 分布。

本步骤暂不在当前诊断轮直接执行，原因：

- 它会改变冻结输入包的身份语义，不只是重跑 judge；现有 `c1/c2` 已经被人工标注、judge runs、summary、eval report 共同引用，直接重排会让既有 Phase A rerun 产物不可横向比较。
- 它需要同步修改 package manifest、人工标注模板、eval 汇总口径，以及按 `candidate_id` / `orientation` 分层的报告字段，否则会把“候选列”与“原始取向”混在一起。
- 它属于下一轮输入包设计修正；Step 3 真实 LLM 对照已经支持“标签暴露会污染判断，但不是唯一根因”这一判断，因此应以新 package 版本执行，不应混入当前 `phase-a-rerun` 诊断产物。

### 当前下一步方案评估

当前方案方向是完善的，但不能把“完整 rerun”当成下一条可直接命令执行。

- Step 4 的 F4 prompt 匿名化、双向换位保留、raw pattern gate 保留，证据链充分，应作为 Phase A.3 judge 的默认口径。
- Step 5 的冻结输入包设计方向合理，已迁移到 Phase A.3 实施计划；需要明确 manifest 字段、人工标注模板字段、eval 分层输出字段和验收命令后再重跑 Phase A.3。
- 下一轮 rerun 应等待 F3 新取向小样本验证、`c1/c2` 取向均衡入包、eval 分层 gate 和 comparison-intersection 样本门槛都落地后再执行。

## 决策口径

上述诊断完成后的当前口径：

- 不进入 Phase B。
- 不切换 `/chat` 默认择优为 pairwise。
- 不把本轮 `pairwise_stable` 输出进入 DPO 候选池。
- 不把当前 `14/24 stable` 解读为有效稳定偏好；它已经被 c1 collapse 诊断污染。
- 可以执行 F4 prompt 匿名化、raw pattern gate 保留、eval 分层输出，以及下一版冻结输入包的 `c1/c2` 取向均衡设计。
- 不能直接重跑完整 Phase A rerun；需要先把 F3 候选质量修复、输入包 manifest、人工标注模板、eval 字段和通过门槛落成可执行任务。

可能结论及后续：

| 结论 | 判据 | 后续 |
|---|---|---|
| 代码 bug | Step 1 任一 mock 测试失败 | 修代码，重跑本轮 pairwise judge |
| 展示位偏置 | identical / hidden-label 对照仍稳定偏 A 或 B | 当前未在隐藏标签 prompt 下复现纯位置偏置；继续保留双向换位和 raw pattern gate |
| candidate_id/标签偏置 | 隐藏标签后偏斜显著下降 | prompt 不再暴露 candidate_id/orientation；已作为下一轮 F4 prompt 修正项 |
| 风格偏好 | winner 跟随 Phase A.2 `共情型` 内容移动，且 hidden-label 后仍明显偏旧 `共情型` | 修订 F4 rubric，正面处理 judge 与人工偏好的定义差异 |

当前更可能的判断是混合问题：`c1` 候选槽位塌缩不是代码层映射 bug，也不是隐藏标签 prompt 下的纯位置偏置；更像是旧 prompt 标签暴露与内容/风格偏好共同造成的混合问题。当前 Step 4 的 prompt 匿名化进入 Phase A.3 默认口径；Step 5 的冻结输入包设计方向合理，但还需要拆成明确的 package、annotation、eval 实施任务后再进入下一轮 rerun。
