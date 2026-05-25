# F4 F9 修复执行总结

日期：2026-05-26

## 执行结果

已执行 `docs/corpus/f9/f4-fix-plan.md` 中的 F4 critic 修复方案。

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
- `docs/specs/f4-critic-epitome-codex-spec.md`
- `scripts/corpus/f9_validation.py`
- `tests/test_corpus/test_f9_validation.py`
- `docs/corpus/f9/f4-fix-plan.md`
- `docs/corpus/f9/f4-fix-execution-summary.md`
- `docs/corpus/f9/validation/...`

建议与 F4/F9 修复组分开处理：

- F3/generator 相关改动：
  - `app/services/generator_service.py`
  - `tests/test_services/test_generator_service.py`
  - `docs/specs/f3-multi-orientation-generator-codex-spec.md`
  - `docs/corpus/emoedu-corpus-synthesis.md`
- 通用仓库文档改动，例如 `README.md`。
- 用户刻意删除的前端目录 `frontend/...`。

前端删除说明：

- `frontend/...` 是用户刻意删除的内容，不应自动恢复。
- 该删除不影响 Python F4/F9 单元测试，也不影响后端 validation 运行。
- 该删除会影响仍依赖 `frontend/student`、`frontend/console` 或 `frontend/shared` 的前端构建、前端 dev server 和 UI 工作流。
- 该删除建议作为单独的产品或仓库清理变更提交，不要混入 F4 critic 修复提交。

## 下一步计划

1. 按 `docs/corpus/f9/f3-fix-plan.md` 修复 F3 生成器问题。范围不是只替换 sample 25 的 `说明你` 字符串，而是修复 sample 25 暴露出的品质化总结、强行正向重构和固定转折模板。
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
