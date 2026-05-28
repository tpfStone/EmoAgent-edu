# F4 成对比较择优 Phase A.2 Rerun 计划与结果

- 计划日期：2026-05-27
- 结果整理：2026-05-28
- 文档整理：2026-05-29

## 0. 文档职责与阶段定位

本文是 **Phase A.2 / Phase A rerun** 的主文档，承接 `phase-a-implementation-plan.md` 中的 Phase A.1 工具链与 smoke 结果。

当前状态：**Phase A.2 rerun 已完成，结论为 inconclusive**。本轮不能进入 Phase B，不能把 `/chat` runtime 切到 pairwise，也不能把本轮 pairwise stable 输出进入 DPO。

详细结果产物：
- `reports/phase-a-rerun/f9_pairwise_eval_report.md`
- `reports/phase-a-rerun/f9_pairwise_eval_summary.json`
- `reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md`
- `reports/phase-a-rerun/f9_pairwise_c1_collapse_diagnostic.md`

## 1. 原因：为什么需要 Phase A.2

Phase A 已经完成离线 pairwise 工具链、10 对 smoke、人工 A/B 标注和初版 eval。当前结论不是“pairwise 已经比 pointwise 差”，而是：工具链可用，但本轮 smoke 同时存在候选质量噪声、样本量过小、模型/provenance 记录不足、eval 分母错配，因此不能回答“pairwise 是否值得继续投入”。

Phase A rerun 的目标是清噪后重新跑一轮 15-20 对 human-valid 样本，用更干净的输入和交集口径做 go/no-go。只有 Phase A rerun 达标后，才进入 Phase B/runtime 集成或 `/chat` 默认择优切换。

## 2. 解决方案：建议审查结论

| 建议 | 结论 | 调整 |
|---|---|---|
| 先修 F3 prompt，再重跑候选 | 采纳 | smoke 人工 note 确实集中指向 `无效二选一`、`不当安抚`、`格式异常`、`缺少陪伴感`。 |
| 增加 provenance 字段 | 采纳 | 不使用 `HEAD` 判定 prompt 版本，改用稳定的 `f3_prompt_bundle_hash`。 |
| eval 改成交集口径 | 采纳 | 主 delta 只在 `human_valid ∩ pairwise_stable ∩ pointwise_valid` 上计算。 |
| F3 显式迁到 `deepseek-v4-flash` | 采纳 | 官方说明 `deepseek-chat` 当前对应 flash non-thinking，但会在 2026-07-24 废弃；新实验用显式模型名。 |
| F4 使用 `deepseek-v4-pro` | 采纳 | 下一轮 F4 judge 固定 `thinking=enabled`，并写入 manifest。 |
| flash/pro 小对照 | 采纳 | 对照点放在 F3 candidate generation，不混入主 pilot。 |
| 45 条 MVP 重跑 | 延后采纳 | 放在 Phase A rerun 主要结论后，作为 F3 修复和模型迁移的收尾验收。 |
| 命名为 Phase B | 不采纳 | 当前仍是 Phase A 的修正重跑。 |

官方 DeepSeek 依据：
- `https://api-docs.deepseek.com/quick_start/pricing`
- `https://api-docs.deepseek.com/updates/`
- `https://api-docs.deepseek.com/guides/thinking_mode`
- `https://api-docs.deepseek.com/api/list-models`

## 3. 解决方案：必做去噪项

### 3.1 F3 prompt 修复

归属文件：
- `app/services/generator_service.py`
- `docs/specs/f3-multi-orientation-generator.md`
- `tests/test_services/test_generator_service.py`

改动：
- 撤掉“优先 `是A还是B`”表述。
- 引导反思型若发问，二选一必须同时满足：
  - 两个选项来自孩子真实面临的处境；
  - 两个选项互斥，不是因果关系或同一问题的上下游；
  - 任一答案都能推进孩子继续表达。
- 任一条件不满足时，不发问；退回为关于孩子自己的感受、需要或可控边界的可能性陈述。
- 共情型增加主导情绪门控：
  - 难过、委屈、孤独：可用停留式安抚，例如“先这样待一会儿也可以”。
  - 愤怒、不公感：不得用“停在这里也没关系”“这样也没什么不对”，改为认可这股气或不公感有来处。
- F3 输出后做机械清洗：剥除整段包裹引号，规整异常换行；不改写正文语义。

### 3.2 F4 boundary 兜底

归属文件：
- `app/services/critic_service.py`
- `tests/test_services/test_critic_service.py`

改动：
- 增加 deterministic `format_artifact` boundary：
  - 整段候选被中文/英文引号包裹；
  - 明显异常换行导致回复像被损坏的片段。
- 普通句内引用不触发 boundary，避免误伤。

### 3.3 模型显式化

归属文件：
- `app/config.py`
- `app/services/llm_client.py`
- `app/dependencies.py`
- `tests/test_app/test_dependencies.py`

改动：
- F3 generator 默认 `DEEPSEEK_MODEL=deepseek-v4-flash`。
- F3 显式 `thinking=disabled`，保留 `GENERATOR_LLM_TEMPERATURE`。
- F4 critic 默认 `CRITIC_DEEPSEEK_MODEL=deepseek-v4-pro`。
- F4 显式 `thinking=enabled`，并保留 JSON response format 与 critic token budget。
- `DeepSeekLLMClient.generate()` 支持可选 `extra_body` 或 thinking 配置。

### 3.4 Provenance

归属文件：
- `scripts/corpus/f9_validation.py`
- `scripts/corpus/f9_pairwise_package.py`
- `scripts/corpus/f9_pairwise_judge.py`
- `scripts/corpus/f9_pairwise_pointwise_baseline.py`

候选与 pair package 增加字段：
- `generator_run_id`
- `generated_at`
- `generator_model`
- `generator_thinking`
- `f3_prompt_bundle_hash`

manifest 增加字段：
- `llm_provider`
- `generator_model`
- `generator_thinking`
- `critic_model`
- `critic_thinking`
- `critic_sample_count`
- `pairwise_sample_count`
- `llm_timeout`
- `f3_prompt_bundle_hash`

正式 Phase A rerun 输入包准入：
- 缺 provenance 字段拒入；
- `f3_prompt_bundle_hash` 与当前 prompt bundle 不一致拒入；
- generator fallback 拒入；
- 双 boundary、双 fallback、重复 `user_text` 拒入。

### 3.5 Eval 交集口径

归属文件：
- `scripts/corpus/f9_pairwise_eval.py`
- `tests/test_corpus/test_f9_pairwise_eval.py`

主指标只在同一批样本上计算：
- `human_preference in {c1,c2}`
- `pairwise_stable=true`
- `pointwise_winner in {c1,c2}`

报告同时输出样本流失分解：
- `total_pairs`
- `human_valid_pairs`
- `pairwise_stable_after_human_valid`
- `pointwise_valid_after_human_valid`
- `comparison_intersection_pairs`
- 每一步排除原因计数。

非交集结果只作为诊断，不参与 `agreement_delta_vs_pointwise`。

## 4. 解决方案：Rerun 执行顺序

1. 完成 3.1-3.5 的代码和测试。
2. 用修复后的真实 F3 重新生成 20-25 对候选。
3. 预过滤后筛出 15-20 对 human-valid 主集：
   - 学业压力、同伴关系、亲子摩擦尽量均衡；
   - 剔除重复 `user_text`；
   - 剔除双 boundary、双 fallback、格式损坏样本。
4. 同时生成：
   - pair package；
   - human A/B annotation template；
   - pairwise judge runs：两次换位 × `pairwise_sample_count=3`；
   - pointwise baseline：正式口径使用 `CRITIC_SAMPLE_COUNT=3`。
5. 人工完成 A/B 标注后运行 eval。
6. 用交集指标执行 go/no-go。

若真实 API 下 pointwise baseline 无法在可接受时间完成，不降级偷算正式 delta；报告中把 `agreement_delta_vs_pointwise` 标为 unavailable，并把原因写入 manifest/report。

## 5. 解决方案：F3 flash/pro Sidecar 对照

该对照独立于主 Phase A rerun，不混入主指标。

做法：
- 选 5-8 条覆盖学业、同伴、亲子的样本。
- 同一修复后 F3 prompt 下各跑一组：
  - `deepseek-v4-flash`, `thinking=disabled`
  - `deepseek-v4-pro`, `thinking=enabled`
- 人工或 F4 只判断 pro 候选是否显著优于 flash。

结论口径：
- flash 足够：F3 固定 `deepseek-v4-flash thinking=disabled`。
- pro 明显更好且成本可接受：另开模型成本/质量决策，不阻塞主 Phase A rerun。

## 6. 解决方案：单人人工标注 SOP

标注时隐藏 pairwise、pointwise、F4 分数，只看：
- `user_text`
- `c1_text`
- `c2_text`

判定顺序：
1. 先判硬排除：文本损坏、上下文不足、两条都无法判断时填 `invalid`；一条明显越界、泄露内部提示、严重不适龄时，另一条胜并填写 `human_boundary_winner`。
2. 再判质量偏好：选择更回应真实情绪诉求、更具体自然、更有陪伴感、不说教、不成人复盘、不编造、不空泛的一条。
3. 两条难分高下，或两条都不行但没有明确赢家时，填 `tie`，不强行二选一。

字段沿用现表：
- `human_preference`
- `human_tie`
- `human_invalid`
- `human_boundary_winner`
- `human_issue_type`
- `human_notes`
- `annotator_id`

单人减负：
- 15-20 对分两次标，每次 8-10 对。
- `tie` 的 note 可一句话。
- 分得出高下的样本写一句中文理由即可。

## 7. 结果判定：Go / No-Go

只看交集分母。

- `comparison_intersection_pairs < 12`：结论为 inconclusive，先修样本流失，不判断 pairwise 优劣。
- 继续投入：`critic_human_agreement >= 0.70` 且 `agreement_delta_vs_pointwise > 0`。
- 止损：候选已清理后仍 `critic_human_agreement <= 0.55` 且 delta 不为正。
- 中间区间：`0.58-0.68`，扩到 30 对 human-valid 再判断，不进入 runtime。

## 8. 后续规划：45 条 MVP 重跑

放在 Phase A rerun 的主要去噪项之后执行，不覆盖旧验收结果。

输出放入新的日期目录，沿用 `docs/acceptance/orchestrator-mvp/` 的结构。

人工只做 Step 3 排雷：
- 越界；
- 文不对题；
- 取向不分化；
- 明显格式损坏；
- 明显不适龄。

不逐行打质量分，不改写旧统计。

## 9. 验证命令

聚焦测试：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_generator_service.py tests\test_services\test_critic_service.py tests\test_app\test_dependencies.py -q
C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_pairwise_package.py tests\test_corpus\test_f9_pairwise_judge.py tests\test_corpus\test_f9_pairwise_pointwise_baseline.py tests\test_corpus\test_f9_pairwise_eval.py -q
```

全量测试：

```powershell
C:\Python313\python.exe -m pytest -q
```

Phase A rerun 产物建议目录：

```text
docs/corpus/f9/pairwise-selection-pilot/
  inputs/phase-a-rerun/
  annotations/phase-a-rerun/
  runs/phase-a-rerun/
  reports/phase-a-rerun/
  runs/f3-model-sidecar/
  reports/f3-model-sidecar/
```

## 10. 执行结果与结论（2026-05-28）

### 10.1 执行完成项

- 3.1-3.5 去噪代码已实现，F3 spec 已同步。
- 已新增 Phase A.2 rerun 候选生成脚本 `scripts/corpus/f9_pairwise_rerun_generate.py`。
- 已完成 F3 flash/pro sidecar 候选对照产物：
  - `runs/f3-model-sidecar/`
  - `reports/f3-model-sidecar/`
- 已用 `deepseek-v4-flash thinking=disabled` 生成主 rerun pair package：
  - `inputs/phase-a-rerun/f9_pairwise_rerun_pairs.csv`
  - `annotations/phase-a-rerun/f9_pairwise_rerun_human_ab.csv`
- 已完成正式 F4 pairwise judge 与 pointwise baseline：
  - `runs/phase-a-rerun/f9_pairwise_judge_summary.csv`
  - `runs/phase-a-rerun/f9_pairwise_pointwise_baseline.csv`
- 已完成人工 A/B 标注整理和 Phase A.2 eval：
  - `reports/phase-a-rerun/f9_pairwise_eval_report.md`
  - `reports/phase-a-rerun/f9_pairwise_eval_summary.json`
  - `reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md`

### 10.2 主集与运行口径

- 主 rerun pair 数：`24`
- 场景分布：亲子摩擦 `8`、同伴关系 `8`、学业压力 `8`
- provenance：完整
- fallback pair：`0`
- 重复 `user_text`：`0`
- F3 generator：`deepseek-v4-flash thinking=disabled`
- F4 pairwise judge：`deepseek-v4-pro thinking=enabled`，`pairwise_sample_count=3`
- pointwise baseline：`deepseek-v4-pro thinking=enabled`，`pointwise_sample_count=3`

### 10.3 人工标注结果

- 人工 A/B 行数：`24`
- 最终人工偏好：`c1=7`、`c2=8`、`tie=9`、`invalid=0`
- human-valid：`15/24`
- human tie rate：`0.375`
- 提示词/格式残留样本：`sample-1`、`sample-23`

### 10.4 Eval 结果

| Metric | Value |
|---|---:|
| total_pairs | 24 |
| human_valid_pairs | 15 |
| pairwise_valid_pairs_all | 9 |
| pointwise_valid_pairs_all | 13 |
| comparison_intersection_pairs | 7 |
| pairwise_matches | 3 |
| critic_human_agreement | 0.429 |
| pointwise_matches | 3 |
| pointwise_human_agreement | 0.429 |
| agreement_delta_vs_pointwise | 0.000 |

严格按第 7 节 go/no-go 口径，`comparison_intersection_pairs=7` 低于下限 `12`，所以本轮正式结论是 **inconclusive**。它不能证明 pairwise 优于 pointwise，也不能推进到 Phase B/runtime 切换。

诊断性解读：即便只看 7 个三方交集样本，pairwise 也没有优于 pointwise，两者都是 `3/7`，`agreement_delta_vs_pointwise=0.000`。

### 10.5 样本流失与诊断

- 人工 tie/invalid 流失：`9` 行。
- human-valid 后 pairwise unstable/invalid 流失：`6` 行。
- pairwise-valid 后 pointwise invalid/nonformal 流失：`2` 行。
- 最大流失来自人工 tie 和 pairwise 不稳定。

诊断发现：
- Pairwise stable 输出明显偏斜：本轮 stable pairwise winner 全部是 `c1`，而 human-valid 偏好接近平衡（`c1=7`、`c2=8`）。
- 当前 pair package 固定 `c1=共情型`、`c2=引导反思型`，无法区分候选身份、取向风格和内容偏好。
- 人工 note 反复指出两条候选过于相似或质量都低：`取向不分化`、`模板化`、`语义重复`、`复述原文`。
- 多个求助型用户 turn 没有得到足够可执行的回应，尤其是用户问“该怎么说”“要不要告诉家长”的样本。
- 候选清理仍不够干净，仍有 2 行提示词/格式残留。
- `c1` 偏斜专项诊断见 `reports/phase-a-rerun/f9_pairwise_c1_collapse_diagnostic.md`。

### 10.6 可用结论与下一步规划

本轮可以给出可执行判断，但不能给出正式的模型优劣证明：

1. 不进入 Phase B，不把 `/chat` 切到 pairwise。
2. 不建议在当前设置上直接扩样本，因为问题不是单纯分母不够。
3. 本轮 `pairwise_stable` 结果已被 `c1` 偏斜污染，不能作为可靠偏好来源进入 DPO 或后续训练集。
4. `c1 collapse` 诊断未发现代码层 A/B 到 `candidate_id` 的映射 bug，也未在隐藏标签 prompt 下复现纯位置偏置；当前更像是旧 prompt 标签暴露与内容/风格偏好共同造成的混合问题。
5. 先修 F3 候选生成、pair package 设计和 pairwise 去偏诊断，再 rerun。

下一轮优先修复：
- 增加或重写面向具体求助 turn 的取向，覆盖用户问“怎么说”“下一步怎么做”的场景。
- 收紧 F3 清洗，入包前移除括号里的 prompt 检查、元说明和其他格式残留。
- 降低模板化共情表达，尤其是重复的“憋屈”“那股...”类句式。
- Pairwise prompt 不展示 `candidate_id` 和 `orientation`，只展示匿名 `回应A` / `回应B` 文本；代码侧继续保留 A/B 到 candidate_id 的映射。
- 后续 frozen package 中随机或均衡 `c1/c2` 对应的取向，避免分析时无法区分候选身份、取向风格和内容偏好。
- Eval 报告同时输出按 `candidate_id`、orientation、raw A/B pattern 分层的 winner 分布，把 `c1` 偏斜作为正式 gate。
- 完成上述修复后再 rerun，目标至少拿到 12 个 comparison-intersection 样本，最好接近 20+；若再次出现稳定单边 `c1/c2` 塌缩，不判断 pairwise 优劣，先继续排查 judge 或输入包。
