# F4 Pairwise Selection Pilot 大轮试验方案

日期：2026-05-26

## 0. 当前结论

`docs/specs/f4-pairwise-selection-codex-spec.md` 的方向成立，但不能直接按原文实现。原文把 pairwise 改造写成“在现有 pointwise prompt 后追加一段”的增量改造；实际代码中 F4 critic 是逐候选独立打分，再用 `weighted_total` 做 argmax 择优。因此，这一轮必须先做 **离线 pairwise pilot + 人工 A/B 验证**，在证据达标前不切换 `/chat` 的默认择优器。

2026-05-27 追加：10 对 smoke 已完成，结论是工具链可用但不足以判断 pairwise 优劣。下一步仍是 Phase A 修正重跑，不进入 Phase B；执行口径见 `docs/corpus/f9/pairwise-selection-pilot/phase-a-rerun-plan.md`。

2026-05-28 追加：Phase A rerun 已完成候选生成、pairwise judge 与正式 3-sample pointwise baseline；主 rerun 产物见 `docs/corpus/f9/pairwise-selection-pilot/inputs/phase-a-rerun/`、`runs/phase-a-rerun/`、`annotations/phase-a-rerun/`。当前 24 对主集场景均衡（亲子/同伴/学业各 8），pairwise stable 为 `14/24`、无 invalid，pointwise baseline 为 `24/24` 且 `pointwise_sample_count=3`。人工 A/B 标注尚未完成，因此还没有 go/no-go 结论，下一步是填写 `annotations/phase-a-rerun/f9_pairwise_rerun_human_ab.csv` 后运行 eval。

Claude 对 Codex 五条评审意见的回应合理，全部采纳：

1. **调用形态不匹配**：采纳。pairwise 是 per-pair 调用形态，不是 per-candidate prompt 的局部追加。
2. **单次调用不能干净抵消位置偏见**：采纳。pilot 默认使用两次独立调用，先求验证干净，再评估降本。
3. **`pointwise_tiebreak` 是否产偏好对矛盾**：采纳。pilot 阶段只有 `pairwise_stable` 来源进入 DPO 候选池；`single_survivor`、`pointwise_tiebreak` 只用于择优诊断和日志。
4. **缺少 pairwise 与 `CRITIC_SAMPLE_COUNT=3` 的聚合规则**：采纳。每个 pairwise sample 先产 `stable/unstable`，多 sample 聚合后只有同一 winner 达到多数或全票才算 `pairwise_stable`。
5. **F9 衔接不是同步脚本这么简单**：采纳。必须保留同一 turn 的两个候选，新增人工 A/B 标注表和 pairwise agreement 指标。

补充约束：旧的 pointwise 人工标注不能直接复用为 A/B 偏好真值。之前的 `10/20`、`11/20` 是 ER/IP 三档分匹配结果，只能作为背景证据；pairwise pilot 必须让人工对同一批候选对重新做 A/B 标注。

---

## 1. 试验目录

这一大轮试验的所有新文档和产物统一放在：

```text
docs/corpus/f9/pairwise-selection-pilot/
```

建议后续目录结构：

```text
docs/corpus/f9/pairwise-selection-pilot/
  f4-pairwise-selection-pilot-plan.md        # 本方案
  inputs/                                    # 冻结候选对输入包
  annotations/                               # 人工 A/B 标注表
  runs/                                      # critic pairwise 原始运行结果
  reports/                                   # agreement、稳定性、成本报告
```

当前只创建方案文件；`inputs/`、`annotations/`、`runs/`、`reports/` 在执行相应阶段时再创建，避免空目录无法入库。

---

## 2. 本轮目标与非目标

### 目标

- 验证 pairwise judge 是否比当前 pointwise `weighted_total` argmax 更接近人工偏好。
- 建立一套可复跑的 F9 A/B 验证流程：同一 turn 两个候选、人工 A/B 真值、critic pairwise 判断、agreement 指标。
- 保留当前 EPITOME/CASEL/boundary pointwise 打分作为诊断分，不再把它未经验证地当成择优真值。
- 为未来 runtime 切换准备清晰的 schema、配置和数据口径，但本轮不直接上线。

### 非目标

- 不修改 F1/F2/F3 的 runtime 接口。
- 不把 `CRITIC_SELECTION_MODE=pairwise` 设为默认。
- 不把旧 pointwise 人工标注转译成 pairwise 真值。
- 不生成正式 DPO 数据集；本轮最多生成“DPO 候选池”，且只包含 `pairwise_stable` 来源。
- 不做 3 个及以上候选的 pairwise tournament 聚合。
- 不优化成单次调用双排序；单次调用是未来降本项。

---

## 3. 关键原则

1. **先离线，后上线**  
   pairwise 未经 F9 A/B 证明前，不接管 `/chat` 默认择优。

2. **先干净，后省成本**  
   pilot 默认 `CRITIC_PAIRWISE_TWO_CALLS=true`。每个 pairwise sample 做两次独立 judge 调用：
   - call 1：展示顺序 `(c1, c2)`
   - call 2：展示顺序 `(c2, c1)`

3. **同一批候选对，人工和 critic 都看同一份输入**  
   输入包必须冻结。人工标注和 critic 判断都基于同一个 `pair_id`、同一条用户倾诉、同一段历史、同一对候选文本。

4. **pointwise 是 baseline 和诊断，不是 pilot 真值**  
   对同一候选对仍可计算 pointwise `weighted_total` argmax，作为 baseline 与 tiebreak 诊断；但 pairwise pilot 的主指标是 human A/B vs critic A/B。

5. **偏好对宁少勿脏**  
   只有 `selection_method=pairwise_stable` 的结果能进入 DPO 候选池。`single_survivor`、`pointwise_tiebreak`、`orientation_default`、`all_blocked` 均不进入 DPO。

---

## 4. 两阶段路线

### 阶段 A：离线 Pairwise Pilot

阶段 A 是当前要做的大轮试验。

#### A1. 构造冻结候选对输入包

输入包必须包含同一 turn 的两个候选：

```csv
pair_id,sample_no,scenario,user_text,history_json,c1_orientation,c1_text,c2_orientation,c2_text,source_run,notes
```

输入来源优先级：

1. **优先：重新从 F3 生成冻结候选对**  
   使用当前 `GeneratorService` 对选定样本生成 `c1=共情型` 和 `c2=引导反思型`，保留两个候选。这样最贴近未来 runtime 场景。

2. **可用于 smoke：已有包含双候选的 golden generated 包**  
   例如 `docs/corpus/f9/validation/golden/f9_golden_generated_scores.csv` 已按 generated candidates 输出多行，可用于小样本 smoke。但它不是完整正式 pilot 输入。

3. **不推荐：当前 rerun selected 包**  
   `f9_validation.py` 的 rerun 阶段当前只保留某个 orientation 的单候选，不能直接用于 pairwise pilot。

样本规模建议：

- smoke：10 对，验证格式、解析、人工表单是否可用。
- pilot：30-40 对，覆盖 `同伴关系`、`亲子摩擦`、`学业压力`、`其他`，并优先包含 R8/R9 暴露的高分争议样本类型。

输入包质量要求：

- 不接受 generator fallback 候选进入 pilot 主集。
- 若候选命中确定性内部提示外泄或硬 boundary，保留记录但单独标 `boundary_case=true`，不混入普通 pairwise agreement 主指标。

#### A2. 新增人工 A/B 标注表

旧 ER/IP/EX 人工标注不能复用。人工需要对冻结候选对重新标偏好：

```csv
pair_id,sample_no,human_preference,human_tie,human_invalid,human_boundary_winner,human_issue_type,human_notes,annotator_id
```

字段口径：

- `human_preference`：`c1` / `c2` / `tie` / `invalid`
- `human_tie=true`：两条都可用或难分高下。
- `human_invalid=true`：样本无法判断，例如上下文缺失、两条都严重越界、文本损坏。
- `human_boundary_winner`：若一条明显越界，填未越界候选；这类样本单独统计，不进入普通质量偏好 agreement。
- `human_issue_type`：可选枚举，如 `泛化安慰`、`语义重复`、`缺少陪伴感`、`成人复盘感`、`事实补全`、`第三方开脱`、`内部提示外泄`。
- `human_notes`：一句中文理由。

人工标注说明：

- 标注的是“这两条里哪条更适合作为系统给初中生的最终回复”，不是给 ER/IP/EX 三维打分。
- 允许 `tie`，不要为了制造偏好强行二选一。
- 对明显 boundary 的样本，优先标 boundary，而不是把它当普通偏好。

#### A3. 实现离线 pairwise judge

pilot 阶段不重构现有 `CriticService.evaluate()` 的 runtime 流程。新增离线 pairwise 评估能力，建议以脚本和小型可复用模块实现：

```text
app/services/critic_pairwise.py                 # 纯 pairwise prompt、解析、聚合逻辑
scripts/corpus/f9_pairwise_package.py           # 生成冻结候选对输入包
scripts/corpus/f9_pairwise_judge.py             # 对输入包跑 critic pairwise
scripts/corpus/f9_pairwise_eval.py              # 与人工 A/B 标注对齐，输出指标
tests/test_services/test_critic_pairwise.py
tests/test_corpus/test_f9_pairwise_eval.py
```

pairwise prompt 只负责比较两条回应，不在 pilot 阶段强行合并 pointwise 打分。pointwise baseline 可沿用现有逐候选 F4 打分结果或单独复评生成。

每个 pairwise sample 的两次调用：

```text
sample k:
  call 1 prompt: A=c1, B=c2
  call 2 prompt: A=c2, B=c1
```

每次调用输出 JSON：

```json
{
  "winner": "A|B|tie",
  "reason": "一句中文理由",
  "boundary_concern": false,
  "boundary_reason": ""
}
```

代码侧把 `A/B` 映射回 `candidate_id`。单个 sample 判定：

| call 1 | call 2 | sample 结果 |
|---|---|---|
| 都映射到 `c1` | 都映射到 `c1` | `stable_winner=c1` |
| 都映射到 `c2` | 都映射到 `c2` | `stable_winner=c2` |
| 任一为 `tie` | 另一为任意值 | `unstable` |
| 分别映射到不同候选 | - | `unstable` |
| parse failure / timeout | - | `invalid` |

#### A4. `CRITIC_SAMPLE_COUNT=3` 聚合规则

pilot 默认每个 pair 跑 `pairwise_sample_count=3`。每个 sample 由两次独立调用组成，因此默认每个 pair 是 6 次 pairwise LLM 调用。

聚合字段：

```json
{
  "pair_id": "p001",
  "pairwise_sample_count": 3,
  "stable_votes": {"c1": 2, "c2": 0},
  "unstable_count": 1,
  "invalid_count": 0,
  "winner_id": "c1",
  "pairwise_stable": true,
  "pairwise_confidence": "majority_with_unstable",
  "selection_method": "pairwise_stable"
}
```

聚合判定：

- `invalid_count > 0`：该 pair 不进入主 agreement，单独统计运行稳定性。
- 同一候选稳定票数达到多数，即 `>= ceil(pairwise_sample_count / 2)`，且高于另一候选稳定票数：`pairwise_stable=true`。
- 全票稳定时 `pairwise_confidence=unanimous`。
- 多数稳定但有 unstable 时 `pairwise_confidence=majority_with_unstable`。
- 多数稳定但另一候选也有稳定票时 `pairwise_confidence=split_majority`，进入报告，但默认不进入 DPO 候选池，除非人工复核批准。
- 无多数 winner：`selection_method=pointwise_tiebreak` 或 `orientation_default`，只用于诊断，不进入 DPO 候选池。

#### A5. pointwise baseline

为了判断 pairwise 是否真的比旧方案好，需要在同一冻结候选对上建立 pointwise baseline：

- 对 `c1`、`c2` 分别运行现有 F4 pointwise 打分。
- 用 `weighted_total` 高者作为 `pointwise_winner`。
- 若分数相等，记为 `pointwise_tie`，不强行归入任一候选。
- 用同一份人工 A/B 标注计算 `pointwise_winner` vs human A/B 的 agreement。

这不是复用旧 pointwise 人标，而是在同一 A/B 真值上比较两种 critic 决策形态。

#### A6. 指标与验收门槛

报告至少输出：

```text
total_pairs
human_valid_pairs
critic_valid_pairs
pairwise_parse_failure_rate
pairwise_stable_rate
pairwise_unanimous_rate
pairwise_majority_rate
human_tie_rate
critic_human_agreement
pointwise_human_agreement
agreement_delta_vs_pointwise
cohen_kappa_if_applicable
boundary_case_count
boundary_selection_error_count
estimated_llm_calls_per_pair
estimated_cost_or_latency
```

建议门槛：

- smoke 通过：
  - 10 对样本全部完成人工 A/B 表结构校验。
  - pairwise parse failure 为 0。
  - 无明显 prompt 泄漏、JSON 结构不稳定或 A/B 映射错误。

- pilot 通过：
  - 主集不少于 30 对 human-valid 样本。
  - `pairwise_parse_failure_rate <= 5%`。
  - `pairwise_stable_rate >= 70%`。
  - `critic_human_agreement >= 70%`。
  - `agreement_delta_vs_pointwise >= +10pp`。若 pointwise baseline 明显低于旧 R10 的 11/20，也要解释原因。
  - `boundary_selection_error_count = 0`。

如果 pilot 未达标，不能切换 runtime；应回到 pairwise prompt、模型、输入包质量或 F3 生成策略继续定位。

### 阶段 B：Runtime 切换候选方案

阶段 B 只有在阶段 A 达标并经人工确认后启动。

未来 runtime 切换应做：

- 新增 response schema：
  - `selection_method`
  - `pairwise`
  - `pairwise_confidence`
- `CRITIC_SELECTION_MODE` 支持：
  - `pointwise`
  - `pairwise_offline_only`
  - `pairwise`
- runtime 初期默认仍使用两次独立 pairwise 调用；单次调用双排序只作为后续降本实验。
- `turns` / `critic_runs` 是否新增 `selection_method`、`pairwise_result` 需要配套 Alembic migration。
- DPO 导出脚本只导出 `selection_method=pairwise_stable` 且 `pairwise_confidence in {unanimous, majority_with_unstable}` 的样本；`split_majority` 默认需人工复核。

---

## 5. 当前不能做的事

这些事项当前阶段不要做：

1. **不能直接实现旧 spec 的单次合并 prompt**  
   这会绕过当前 per-candidate 代码结构，且无法干净验证位置偏见。

2. **不能把旧 pointwise 人标当作 A/B 真值**  
   ER/IP/EX 三档分不是“哪条更好”的直接标注。

3. **不能把 pairwise 直接设为 `/chat` 默认**  
   当前没有 pairwise-human agreement 证据。

4. **不能把 `pointwise_tiebreak` 喂给 DPO**  
   pairwise 不稳时的 pointwise 兜底只说明需要运行时给用户一个回复，不说明存在干净偏好。

5. **不能用 selected-only rerun 包做 pairwise 验证**  
   它缺少同一 turn 的另一条候选。

---

## 6. 未来规划

以下内容放到阶段 A 达标后再做：

- 单次 LLM 调用内同时输出 `(c1,c2)` 与 `(c2,c1)`，与两次独立调用做一致性和成本对照。
- 把 pointwise 与 pairwise 合并到同一个 per-pair runtime prompt。
- 3+ 候选 pairwise tournament、Bradley-Terry 或 Elo 聚合。
- 数据库正式记录 `selection_method`、`pairwise_result`、`pairwise_confidence`。
- DPO 数据抽取加入 pairwise confidence 分层和人工复核队列。
- 正式 F9 从 pointwise 信度报告扩展为 pairwise 偏好信度报告，并保留 pointwise 诊断维度作为附录。

---

## 7. 下一步执行顺序

1. 写 `f9_pairwise_package.py`，生成 10 对 smoke 输入包。
2. 写人工 A/B 标注模板，人工先标 10 对 smoke。
3. 写 `critic_pairwise.py` 和 `f9_pairwise_judge.py`，默认两次独立调用、`pairwise_sample_count=3`。
4. 写 `f9_pairwise_pointwise_baseline.py`，在同一候选对上生成旧 pointwise `weighted_total` 对照。
5. 写 `f9_pairwise_eval.py`，对齐人工 A/B、pairwise、pointwise baseline，输出 smoke report。
6. smoke report 通过后，扩展到 30-40 对 pilot 主集。
7. pilot 达标后，再写 runtime 切换 spec 和实施计划。

---

## 8. 已落地的阶段 A 工具

当前已完成离线阶段 A 的基础工具，不改变 `/chat` runtime：

| 工具 | 作用 | 主要产物 |
|---|---|---|
| `app/services/critic_pairwise.py` | pairwise prompt、A/B 解析、两次换位判断、3-sample 聚合 | Python API |
| `scripts/corpus/f9_pairwise_package.py` | 从含 `c1/c2` 的候选行生成冻结候选对输入包，并可生成空白人工 A/B 标注模板 | `f9_pairwise_pairs.csv`、`f9_pairwise_human_ab.csv` |
| `scripts/corpus/f9_pairwise_judge.py` | 对冻结候选对跑 pairwise judge | `f9_pairwise_judge_runs.csv`、`f9_pairwise_judge_summary.csv`、manifest |
| `scripts/corpus/f9_pairwise_pointwise_baseline.py` | 对同一候选对跑旧 pointwise baseline | `f9_pairwise_pointwise_baseline.csv` |
| `scripts/corpus/f9_pairwise_eval.py` | 对齐人工 A/B、pairwise summary、pointwise baseline 并输出指标 | `f9_pairwise_eval.csv`、summary JSON、report MD |

建议 smoke 命令：

```powershell
$env:LLM_TIMEOUT='60'
C:\Python313\python.exe scripts\corpus\f9_pairwise_package.py --input docs\corpus\f9\validation\golden\f9_golden_generated_scores.csv --output docs\corpus\f9\pairwise-selection-pilot\inputs\f9_pairwise_smoke_pairs.csv --annotation-output docs\corpus\f9\pairwise-selection-pilot\annotations\f9_pairwise_smoke_human_ab.csv
C:\Python313\python.exe scripts\corpus\f9_pairwise_judge.py --pair-package docs\corpus\f9\pairwise-selection-pilot\inputs\f9_pairwise_smoke_pairs.csv --output-dir docs\corpus\f9\pairwise-selection-pilot\runs\smoke --pairwise-sample-count 3
C:\Python313\python.exe scripts\corpus\f9_pairwise_pointwise_baseline.py --pair-package docs\corpus\f9\pairwise-selection-pilot\inputs\f9_pairwise_smoke_pairs.csv --output docs\corpus\f9\pairwise-selection-pilot\runs\smoke\f9_pairwise_pointwise_baseline.csv
C:\Python313\python.exe scripts\corpus\f9_pairwise_eval.py --pairwise-summary docs\corpus\f9\pairwise-selection-pilot\runs\smoke\f9_pairwise_judge_summary.csv --human-annotations docs\corpus\f9\pairwise-selection-pilot\annotations\f9_pairwise_smoke_human_ab.csv --pointwise-baseline docs\corpus\f9\pairwise-selection-pilot\runs\smoke\f9_pairwise_pointwise_baseline.csv --output-dir docs\corpus\f9\pairwise-selection-pilot\reports\smoke
```

执行 `f9_pairwise_package.py` 后会生成 `annotations/f9_pairwise_smoke_human_ab.csv` 模板；人工填完偏好列前，不运行最终 eval。真实 LLM smoke 建议显式设置 `LLM_TIMEOUT=60`，避免 10 秒默认超时造成无效结果。若只需要快速 smoke pointwise 对照，可临时设置 `$env:CRITIC_SAMPLE_COUNT='1'`；正式 pilot 对照仍应使用默认 3-sample 或在报告中明确标注 sample count。

阶段 A 验证命令：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_critic_pairwise.py tests\test_corpus\test_f9_pairwise_package.py tests\test_corpus\test_f9_pairwise_judge.py tests\test_corpus\test_f9_pairwise_pointwise_baseline.py tests\test_corpus\test_f9_pairwise_eval.py tests\test_corpus\test_f9_pairwise_cli.py -q
C:\Python313\python.exe -m pytest tests\test_services\test_critic_service.py tests\test_corpus\test_f9_fixed_candidate_rescore.py tests\test_corpus\test_f9_validation.py -q
C:\Python313\python.exe -m pytest -q
```

---

## 9. 与原 pairwise 草案的关系

`docs/specs/f4-pairwise-selection-codex-spec.md` 保留为方向性草案；本文件是阶段 A 初版执行基准。10 对 smoke 后的下一轮执行以 `docs/corpus/f9/pairwise-selection-pilot/phase-a-rerun-plan.md` 为准。若三者冲突，优先级为：`phase-a-rerun-plan.md` > 本文件 > 原 spec。

- 以两次独立调用为 pilot 默认，而不是单次调用双排序。
- 以离线 pilot 验证为前置，而不是直接改 runtime 默认择优。
- 以人工 A/B 新标注为真值，而不是旧 pointwise 人标。
- 以 `pairwise_stable` 作为 DPO 候选入口，其他 selection method 只做诊断。
