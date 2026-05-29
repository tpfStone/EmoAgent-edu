# F4 F9 修复执行总结

日期：2026-05-26

## 执行结果

已执行 `docs/corpus/f9/plans/f4-critic-fix-plan.md` 中的 F4 critic 修复方案。

已完成的改动：

- 在 F4 内部 judge prompt 和原始 judge JSON 契约中加入 F9 `audit_tags`。
- 为 F9 可靠性失败模式加入代码侧确定性分数 cap。
- 将普通 `unsupported_fact_completion` 与硬边界事实编造分开处理：
  - `unsupported_fact_completion` 只压低 ER/IP，不自动设置 `boundary_flag`。
  - `hard_boundary_fabrication` 设置 `boundary_flag=true`，并压低 ER/IP。
- 为容易混淆的标签补充 prompt 示例，包括 `template_low_information`、`forced_positive_reframe`、`unsupported_fact_completion`、`hard_boundary_fabrication` 和 `low_pressure_binary_question`。
- 保持公开 `CandidateScore` schema 不变。`audit_tags` 仍是内部原始 judge 字段，只附加到 `rationale` 中用于诊断。
- 修复 F9 validation 的计数逻辑，使运行时产生的整数分数能被正确统计。

验证结果：

- `python -m pytest tests\test_services\test_critic_service.py -q`：22 passed
- `python -m pytest tests\test_corpus\test_f9_validation.py -q`：8 passed
- `python -m pytest -q`：93 passed

F9 validation gate 结果：

- decision: FAIL
- old_candidate_expectation_pass: 10/10，门槛 >= 8/10
- old_candidate_ER_IP_2_2: 2/10，上限 <= 2/10
- rerun_ER_2: 22/40，上限 <= 32/40
- rerun_IP_2: 22/40，上限 <= 32/40
- generated_detected_flags: 1，门槛 0
- rerun_detected_flags: 1，门槛 0
- generator_fallback_rows: 0，门槛 0

结果解释：

- F4 critic 的自动验收指标已经达到阈值。
- 当前 gate 仍失败，是因为 F3 generation 仍有残留问题：sample 25 仍输出被规则捕获的 `说明你` 模式。
- F4 已正确识别并压低该候选，将其标为 `forced_positive_reframe`；剩余问题应在 generator 侧处理。

## Dirty Changes 分组

F4/F9 修复组建议放在一起：

- `app/services/critic_service.py`
- `tests/test_services/test_critic_service.py`
- `docs/specs/f4-critic-epitome.md`
- `scripts/corpus/f9_validation.py`
- `tests/test_corpus/test_f9_validation.py`
- `docs/corpus/f9/plans/f4-critic-fix-plan.md`
- `docs/corpus/f9/pointwise-diagnostics/execution-summary.md`
- `docs/corpus/f9/validation/...`

建议与 F4/F9 修复组分开处理：

- F3/generator 相关改动：
  - `app/services/generator_service.py`
  - `tests/test_services/test_generator_service.py`
  - `docs/specs/f3-multi-orientation-generator.md`
  - `docs/corpus/emoedu-corpus-synthesis.md`
- 通用仓库文档改动，例如 `README.md`。
- 用户刻意删除的前端目录 `frontend/...`。

前端删除说明：

- `frontend/...` 是用户刻意删除的内容，不应自动恢复。
- 该删除不影响 Python F4/F9 单元测试，也不影响后端 validation 运行。
- 该删除会影响仍依赖 `frontend/student`、`frontend/console` 或 `frontend/shared` 的前端构建、前端 dev server 和 UI 工作流。
- 该删除建议作为单独的产品或仓库清理变更提交，不要混入 F4 critic 修复提交。

## 下一步计划

1. 按 `docs/corpus/f9/plans/f3-generator-fix-plan.md` 修复 F3 生成器问题。范围不是只替换 sample 25 的 `说明你` 字符串，而是修复 sample 25 暴露出的品质化总结、强行正向重构和固定转折模板。
2. 扩展 F9 validation：
   - sample-specific hard flags 继续要求 generated/rerun 均为 0。
   - global quality probes 单独统计，generated 上限 2/20，rerun 上限 4/40。
   - 输出 `f9_low_score_review_queue.csv`，作为正式人工 F9 前的抽查清单。
3. 重跑 F9 validation：

   ```powershell
   $env:PYTHONPATH='.'
   $env:PYTHONIOENCODING='utf-8'
   C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation
   ```

4. 下一轮验收目标：

   - `generated_detected_flags: 0`
   - `rerun_detected_flags: 0`
   - `generated_global_quality_flagged_rows <= 2/20`
   - `rerun_global_quality_flagged_rows <= 4/40`
   - 旧坏候选 F4 指标继续保持在当前通过阈值内
   - 全量测试继续通过

## F3 修复执行结果

已按 `docs/corpus/f9/plans/f3-generator-fix-plan.md` 执行 F3 修复，并重跑 F9 validation。

本轮 validation gate 结果：

- decision: FAIL
- old_candidate_expectation_pass: 10/10，门槛 >= 8/10
- old_candidate_ER_IP_2_2: 2/10，上限 <= 2/10
- rerun_ER_2: 37/40，上限 <= 32/40
- rerun_IP_2: 38/40，上限 <= 32/40
- generated_detected_flags: 0，门槛 0
- rerun_detected_flags: 0，门槛 0
- generated_global_quality_flagged_rows: 0/20，上限 <= 2/20
- rerun_global_quality_flagged_rows: 2/40，上限 <= 4/40
- generator_fallback_rows: 0，门槛 0

结果解释：

- F3 的 sample-specific hard flags 已清零。
- 新增 global quality probes 在阈值内。
- `f9_low_score_review_queue.csv` 已生成，本轮待抽查行数为 0。
- 该中间轮 Gate 仍失败，唯一阻塞项是 rerun 样本 ER/IP 重新接近满分饱和。

后续决策点：

- 不建议为了通过 gate 让 F3 生成更差的候选。
- 需要单独审查 rerun ER/IP 饱和 gate：确认这是 F4 仍过宽，还是 F3 修复后候选质量提高导致旧饱和阈值不再适合作为阻塞项。
- 当时在确认前，不建议把该中间轮 rerun 包直接作为正式人工 F9 入口。

## F3 具体复述约束同步结果

用户继续收紧 `docs/specs/f3-multi-orientation-generator.md` 中的提示词后，已同步到 F3 runtime prompt 和测试：

- 新增共同约束：承接必须包含对孩子说出的那一件具体的事的复述，点回刚讲的具体场景或动作。
- 明确“换谁都会”“这种感觉很正常”“都会觉得难受”这类泛化句最多只能跟在具体复述后面作补充，不能单独充当承接。
- 引导反思型开头改为“一句具体复述接住情绪”；承接可以短，但不能空。
- 未修改 F4 critic 或任何 F4 cap 逻辑。

本轮重跑 validation gate 结果：

- decision: PASS
- old_candidate_expectation_pass: 10/10，门槛 >= 8/10
- old_candidate_ER_IP_2_2: 2/10，上限 <= 2/10
- rerun_ER_2: 31/40，上限 <= 32/40
- rerun_IP_2: 31/40，上限 <= 32/40
- generated_detected_flags: 0，门槛 0
- rerun_detected_flags: 0，门槛 0
- generated_global_quality_flagged_rows: 0/20，上限 <= 2/20
- rerun_global_quality_flagged_rows: 0/40，上限 <= 4/40
- generator_fallback_rows: 0，门槛 0

人工抽查观察：

- sample 2 的引导反思型候选前半已能点回“最后一小步被拎出来”“周围有人笑”“脸烧起来”等具体场景，再提出二选一问题。
- sample 1 先点回“把手机放下那一下”和“说了也是白说”的具体动作/念头，再提出低压二选一问题。
- sample 37 不再命中 global quality probes，但仍包含“换谁都会觉得憋屈”作为具体复述后的补充，当前未触发 gate。
- `f9_low_score_review_queue.csv` 已生成，本轮待抽查行数为 3：sample 19/c2、25/c2、36/c1。

当前自动准入已通过；low-score review queue 的人工确认结论见下一节。

## 人工低分抽查结论

已人工检查 `validation/rerun/f9_low_score_review_queue.csv` 中 3 行降分样本，结论是：这些行缺失或命中的质量问题基本存在，未发现明显 F4 矫枉过正。

- sample 19/c2：F4 指出的 `forced_positive_reframe` 成立。候选先承接“等着被剩下”，随后把自我怀疑重构成“认真相处”“珍贵品质”，正向改写过早，ER/IP 降分合理。
- sample 25/c2：F4 指出的 `adult_coaching_question` 成立。候选把愤怒转成“分得清楚”“有明确看法”，再提出较抽象的二选一反思，成人化引导感偏强，ER/IP 降分合理。
- sample 36/c1：F4 指出的 `template_low_information` 与 EX 关闭对话问题成立。候选前半有具体承接，但结尾“先自己缓一缓，也没什么不对”偏模板化，并收束了继续表达空间，EX=0 合理。

因此，本轮 F3/F4 主包自动验收和人工前置低分抽查均已完成；但该结论随后被 stability rerun 进一步约束，见下一节。

## Stability Rerun 与高分对称抽查

为确认主包 `rerun_ER_2: 31/40`、`rerun_IP_2: 31/40` 不是高温采样下的擦边通过，已在不覆盖主包的独立目录中重跑两次 validation：

| 运行目录 | decision | rerun_ER_2 | rerun_IP_2 | generated_global_quality_flagged_rows | rerun_global_quality_flagged_rows | generator_fallback_rows |
|---|---|---:|---:|---:|---:|---:|
| `validation-stability/run-1` | FAIL | 35/40 | 36/40 | 1/20 | 3/40 | 0 |
| `validation-stability/run-2` | FAIL | 36/40 | 36/40 | 1/20 | 2/40 | 0 |

两次复跑均不是 hard flags 或 fallback 失败，而是 ER/IP 满分比例超过 32/40 上限。这说明主包 PASS 的确贴近 F3 高温生成分布边缘，当前不能把它视为稳定准入通过。

同时从主包 31 条 ER=2 样本中用固定随机种子抽查 5 条，补齐“F4 是否漏判高分”的对称检查：

- sample 31/c2：具体承接作业数量与手酸感，提问仍贴合场景，ER/IP=2 基本合理。
- sample 3/c1：具体承接反复看群消息与被排除感，ER/IP=2 基本合理，EX=0 也合理。
- sample 18/c2：具体承接抽屉/私人物品被翻动，隐含情绪命名较准，ER/IP=2 基本合理。
- sample 37/c2：按现有第 15 条规则，“换谁都会觉得憋屈”位于具体复述之后，因此未触发 gate 符合设计；但该组合仍有模板化边缘风险，需要在人工 F9 中观察是否大量出现。
- sample 39/c2：候选含有可见结构提示“先接住你的场景/再递新视角”，且后半有成人化引导感；虽然 F4 已把 EX 压到 1，但 ER/IP=2 不是干净高分对照，提示 F4 高分侧仍可能偏宽。

更新后的结论：

- low-score review queue 的 3 条降分样本确认合理，未发现明显矫枉过正。
- 但 high-score 侧和重复采样稳定性仍有风险；当前主包不建议直接作为正式人工 F9 入口。
- 下一步应先审查 stability rerun 中 ER/IP=2 的高分样本，判断是继续收紧 F4/F3，还是调整并记录 ER/IP 饱和 gate 的阈值口径。只有复跑稳定落在阈值内，或阈值口径被明确修订后，再启动正式人工 F9。

## Stability Gate Plan 执行进度

已执行 `docs/corpus/f9/plans/stability-gate-plan.md` 中不依赖人工判断的前置任务。

完成内容：

- F3 generator prompt 已补充括号式阶段标签禁令，明确禁止在最终回复中输出 `（先接住你的场景）`、`（再递新视角）`、`（共情）`、`（提问）` 等内部结构提示。
- F4 critic 已增加代码侧 deterministic 内部提示外泄检测。命中 `如果孩子想继续`、`可以追问`、`建议回复`、`可继续引导`，或括号式阶段标签时，直接返回 `boundary_flag=true`，`boundary_reason=internal_prompt_leak`，不再依赖 LLM judge 自行识别。
- 新增 `scripts/corpus/f9_stability_diff.py`，用于生成 high-score 差集人工审查队列；脚本只输出候选与空白人工列，不自动判断好坏。
- 已生成 `docs/corpus/f9/validation-stability/run-2/f9_high_score_diff_review_queue.csv`，共 8 行：sample 10、13、15、19、25、34、36、38。队列已包含 `scenario` 和 `student_text`，便于对照初中生原话判断候选是否应得 ER/IP=2；`human_er_should_be_2`、`human_ip_should_be_2`、`human_issue_type`、`human_notes` 均保持空白，等待人工填写。

验证结果：

- `C:\Python313\python.exe -m pytest tests\test_services\test_generator_service.py tests\test_services\test_critic_service.py -q`：28 passed
- `C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_stability_diff.py -q`：2 passed

当前阻塞：

- 不能继续执行 Task 3 之后的 A/B 判断，因为差集 8 行是否“本来就该得 ER/IP=2”必须由人工按 F9 标准判断。
- 当前 validation/rerun 与 validation-stability 产物仍是修 sample 39 代码前的历史结果；正式复跑应在人工差集结论明确后进行，避免继续产生没有决策价值的采样包。

---

## 2026-05-26：high-score 差集人工复核后的 F4 ER/IP 定义收紧

人工已填写 `docs/corpus/f9/validation-stability/run-2/f9_high_score_diff_review_queue.csv`。复核结论如下：

- sample 10/19：认可 stability 候选的 ER/IP=2，可作为后续正向对照。
- sample 13/15/25/34/36/38：不认可或部分不认可 ER/IP=2，集中暴露两个 F4 高分侧问题：
  - ER：候选能说出或深化情绪，但读起来像旁观者分析，没有让孩子感到被陪伴、被关心。
  - IP：候选把孩子已经明说的情绪或担忧换词复述，却被当作"未明说的深层理解"给到 2。

处理决策：

- 不新增 audit tag，不修改 cap 逻辑；本轮问题属于 ER/IP 高档正向定义过松。
- 不调整 `32/40` 阈值；先稳定 F4 判分口径，再根据三次 validation 的真实分布决定是否修订阈值。
- 收紧 F4 规范与 runtime prompt：ER=2 需要明确的陪伴感，IP=2 需要点出未明说内容；仅复述、分析或命名情绪默认最高落在 1。
- sample 10/19 作为防矫枉过正对照；如果后续 validation 中被压到 1，需要回调定义措辞。

执行与验证：

- 已更新 `docs/specs/f4-critic-epitome.md`、`app/services/critic_service.py`、`tests/test_services/test_critic_service.py`。
- 已确认新增 prompt 断言先失败、修改后通过。
- `C:\Python313\python.exe -m pytest tests\test_services\test_critic_service.py -q`：23 passed
- `C:\Python313\python.exe -m pytest -q`：102 passed

post-erip 三次 validation：

| run | decision | rerun_ER_2 | rerun_IP_2 | generated_flags | rerun_flags | generated_global | rerun_global | fallback |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `validation-stability/post-erip-run-1` | FAIL | 40/40 | 40/40 | 0 | 0 | 1/20 | 2/40 | 0 |
| `validation-stability/post-erip-run-2` | FAIL | 36/40 | 37/40 | 0 | 0 | 0/20 | 2/40 | 0 |
| `validation-stability/post-erip-run-3` | FAIL | 38/40 | 38/40 | 1 | 0 | 1/20 | 1/40 | 0 |

补充说明：

- 沙箱内首次三次 validation 全部出现 `generator_fallback_rows=60` 与 `llm_failure`，经最小 DeepSeek 调用确认是沙箱网络连接失败；上述表格为联网后覆盖重跑的有效结果。
- 本轮 F4 prompt 收紧没有解决 ER/IP 高分饱和，不能进入正式人工 F9。
- sample 19 在三次 post-erip rerun 中均保持 ER/IP=2；sample 10 在 run-2 被 `template_low_information` cap 到 1/1。由于每次候选文本不同，该现象需要按候选文本人工复核，不能直接判定为误伤。

## 2026-05-26：R8 方差隔离方案

对 post-erip 三连跑的补充审查结论：

- 三次 validation 的高分比例波动不能直接归因于 F4 judge 抖动，因为完整 validation 每次都会重新运行 F3 高温生成。
- F4 当前已经默认 `CRITIC_SAMPLE_COUNT=3` 并取中位数；下一步不是“落地 median”，而是诊断 `count=1` 原始单次 judge 抖动，以及 `count=3` median 是否足够稳定。
- 继续全局收紧 F3/F4 prompt 的边际收益已经很低；R8 不再做第 8 轮泛化 prompt 收紧。
- `32/40` gate 暂不修改；是否降级为诊断项，要等固定候选复评和 run-2 人工校准后再决定。

R8 执行计划：

- 固定候选包：`docs/corpus/f9/validation-stability/post-erip-run-2/rerun/f9_rerun_selected_scores.csv`。
- `CRITIC_SAMPLE_COUNT=1` 复评 3 次，观察未经 median 平滑的原始抖动。
- `CRITIC_SAMPLE_COUNT=3` 复评 3 次，观察现有 median 策略是否稳定。
- 生成 `docs/corpus/f9/validation-stability/post-erip-run-2/f9_high_score_calibration_queue.csv`，队列包含 R6 的 8 条校准样例和 run-2 的 40 条待人工判断候选。
- 人工校准前置标准：ER=2 必须让孩子感到被陪伴、被关心；IP=2 必须点出孩子未明说、但藏在话里的情绪或担忧。

R8 执行结果：

- 新增脚本：
  - `scripts/corpus/f9_fixed_candidate_rescore.py`
  - `scripts/corpus/f9_high_score_calibration_queue.py`
- 新增测试：
  - `tests/test_corpus/test_f9_fixed_candidate_rescore.py`
  - `tests/test_corpus/test_f9_high_score_calibration_queue.py`
- 测试结果：
  - `C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_fixed_candidate_rescore.py tests\test_corpus\test_f9_high_score_calibration_queue.py -q`：5 passed
  - `C:\Python313\python.exe -m pytest -q`：107 passed
- `count=1` 固定候选复评：
  - 产物目录：`docs/corpus/f9/validation-stability/r8-fixed-rescore/count1/`
  - 40 条 summary、120 条 run rows、无 `llm_failure`。
  - ER 1/2 flip 1 条，IP 1/2 flip 2 条；ER unstable 0 条，IP unstable 1 条。
- `count=3` 固定候选复评：
  - 产物目录：`docs/corpus/f9/validation-stability/r8-fixed-rescore/count3/`
  - 40 条 summary、120 条 run rows、无 `llm_failure`。
  - ER 1/2 flip 1 条，IP 1/2 flip 1 条；ER unstable 0 条，IP unstable 1 条。
- 人工校准队列：
  - `docs/corpus/f9/validation-stability/post-erip-run-2/f9_high_score_calibration_queue.csv`
  - 48 行：8 条 calibration + 40 条 review；review 中 36 条 `ER_IP_2`、3 条 `ER_IP_not_2`、1 条 `ER_not_2`。
- 优先人工队列：
  - `docs/corpus/f9/validation-stability/post-erip-run-2/f9_priority_review_queue.csv`
  - 48 行：8 条 calibration + 10 条 priority + 30 条 backup。
  - priority 样本为第一轮人工判断范围；backup 仅在 10 条结论不足时再看。

当前结论：

- R8 固定候选复评显示 F4 对同一批候选仍有少量边缘波动，但没有出现全局失稳或网络失败。
- 现在不能继续全局改 prompt，也不能直接改 `32/40` gate；下一步是人工填写优先队列中的 10 条 priority review，再决定后续分支。

## 2026-05-26：R9 priority 人工结果与模型因素调研

priority 10 条人工复核结果：

- ER：`yes=1/10`，`no=9/10`。
- IP：`yes=0/10`，`no=10/10`。
- 人工理由集中在：语义重复、没有真正承接安慰、只是在找原因或深化情绪、把孩子已经说出的情绪换词复述、问题像复盘或说教。

结论：

- 这不是单纯 `32/40` gate 擦边问题；当前候选质量和 F4 高分判断都存在系统偏差。
- 也不能直接把问题归因于 F4 prompt，因为 F3/F4 当前都使用同一 DeepSeek 模型配置。
- 下一步先做 F4-only 模型对照，固定 priority 10 条候选，只替换 judge 模型，判断更强模型是否能缓解高分误判。

R9 执行计划：

- baseline：`deepseek-chat` 对 priority 10 条复评。
- candidate：`deepseek-v4-pro` 对同一 10 条复评。
- 对比：用已有人工 ER/IP 标签作为锚点，生成 `docs/corpus/f9/validation-stability/model-eval/f9_priority_model_comparison.csv`。
- 本轮不重跑 F3，不修改 F3/F4 prompt，不修改 `32/40` gate，不启动正式人工 F9。

已完成的代码准备：

- 扩展 `scripts/corpus/f9_fixed_candidate_rescore.py`：
  - 支持 `user_text` / `candidate_text` 列。
  - 支持 `--bucket priority`。
  - 支持 `--deepseek-model`，不改 `.env` 即可做单次模型覆盖。
  - manifest 记录 `deepseek_model`、`bucket`、输入行数、复评行数。
- 新增 `scripts/corpus/f9_model_eval.py`：
  - 计算 baseline / candidate 与人工 ER/IP 标签的一致数量。
  - 输出 Excel 友好的 UTF-8 BOM CSV 和 summary markdown。

R9 执行结果：

- `deepseek-chat` baseline：`CRITIC_SAMPLE_COUNT=3`、`repeats=3` 完成。
- `deepseek-v4-pro` 原计划：`CRITIC_SAMPLE_COUNT=3`、`repeats=3` 超时，未生成完整产物。
- `deepseek-v4-pro` fallback pilot：`CRITIC_SAMPLE_COUNT=3`、`repeats=1` 完成，但 10/10 行均触发 `llm_parse_failure`。
- 对比脚本已修正：`llm_parse_failure` 行标为 invalid，不再把 0/0 误算成贴近人工。
- 对比 summary：
  - baseline valid rows：10/10
  - candidate invalid rows：10/10
  - baseline total matches：10/20
  - candidate total matches：0/20（全部 invalid，不代表模型准确性）

当前结论：

- `deepseek-v4-pro` 不能作为 drop-in F4 judge 直接升级。
- 本轮不能得出“更好模型能有效缓解”的准确性结论；先要解决结构化输出/解析兼容性和运行成本。
- 在这件事解决前，不修改 F3/F4 prompt，不修改 `32/40` gate，不启动正式人工 F9。

## 2026-05-26：R10 F4 正式切换新模型

R9 解析失败根因：

- `deepseek-v4-pro` 初次失败不是因为模型无法判断，而是当前输出预算不足。
- 原调用在较低 `max_tokens` 下返回 `finish_reason=length`，最终 `content` 为空，导致 `llm_parse_failure`。
- 将 F4 max tokens 提高到 4096，并启用 JSON response format 后，可以得到可解析 JSON。

代码改动：

- `app/config.py`
  - 新增 `CRITIC_DEEPSEEK_MODEL=deepseek-v4-pro`。
  - 新增 `CRITIC_LLM_MAX_TOKENS=4096`。
  - 新增 `CRITIC_LLM_RESPONSE_FORMAT_JSON=True`。
- `app/dependencies.py`
  - 新增 critic 专用 LLM client。
  - F3 generator/safety/scenario 继续使用 `DEEPSEEK_MODEL`。
  - F4 critic 使用 `CRITIC_DEEPSEEK_MODEL`。
- `app/services/critic_service.py`
  - F4 调用使用 critic 专用 token budget。
  - F4 调用启用 `response_format={"type": "json_object"}`。
- `app/services/llm_client.py`
  - `generate()` 支持可选 `response_format`。
- F9 脚本同步使用 critic 专用模型配置。

smoke 结果：

- `docs/corpus/f9/validation-stability/model-eval/deepseek-v4-pro-json-smoke/`
- priority 10 条，`CRITIC_SAMPLE_COUNT=1`，`repeats=1`。
- 10/10 行无 `llm_parse_failure`。
- 人工一致性对比：
  - baseline `deepseek-chat`：10/20
  - candidate `deepseek-v4-pro-json-smoke`：11/20

当前结论：

- 新模型现在能跑通，但只带来小幅改善。
- 它主要缓解部分 IP 偏宽，ER 高分侧仍偏宽。
- 不能把“换模型”当作 F9/F3/F4 的完整修复；下一步仍需在“扩大 v4-pro 验证”和“回修 F3 生成质量”之间决策。
