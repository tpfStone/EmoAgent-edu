# Orchestrator MVP Test Summary

- run_id: `real-llm-20260522-215717`
- run_mode: `real-llm`
- total_samples: 45
- request_ok: 45
- scenario_accuracy: 43/45 (95.6%)
- auto_issue_rows: 2

## Auto Issue Counts

- scenario_mismatch: 2

## Manual Review

- manual_issue_rows: 2
- other_major: 2
- syn_0012: 回复末尾外泄内部提示“如果孩子想继续，可以追问...”，不应作为面向学生的最终回复出现。
- syn_0032: 回复称“把三科的作业都列出来排了顺序”，但用户输入没有列科目或排序，属于事实编造/文不对题风险。

## Remediation Design

- scope: MVP 缺陷闭环；保留本 run 的历史验收统计，不将原结果改写为已修复通过。
- affected_modules: F3 generator prompt, F4 critic boundary prompt, acceptance docs.
- F3 changes: 最终回复只包含学生可见内容；禁止内部提示外泄；不得编造用户未说的数量、科目、排序、具体行为或第三方心理；语气轻量收紧为少评价、少说教、少替第三方解释，多承接孩子感受。
- F4 changes: 内部提示外泄、prompt 痕迹、面向开发者或教师的元话术，以及明显事实编造均标记 `boundary_flag=true`，即使 EPITOME 分高也直接出局。
- non_goals: 不新增后处理器，不改 `/chat`/F3/F4 API schema，不新增数据库字段，不调整 EPITOME/CASEL 权重，不改变 45 条验收通过标准。
- retest_required: 修复后重新跑 F3/F4 单元测试、F1 固定用例、真实 LLM 45 条验收，并人工确认 `syn_0012` 不再外泄内部提示、`syn_0032` 不再编造“三科作业排序”。

## Prompt Iteration And Retest Notes

- 原始问题定位：`syn_0012` 的最终回复外泄“如果孩子想继续，可以追问...”这类内部提示；`syn_0032` 的最终回复编造“三科作业排序”事实。两者都来自 F3 `c2` 候选，且 F4 未将其作为 boundary 排除。
- prompt 修改经历：F3 增加“最终回复只包含学生可见内容”“禁止内部提示外泄”“不得编造用户未说事实”“少评价、少说教、少替第三方解释，多承接孩子感受”；F4 增加硬边界，要求内部提示外泄、prompt 痕迹、教师/开发者元话术和明显事实编造均 `boundary_flag=true`。
- 单元验证：新增 F3 prompt 拼接断言、F4 boundary prompt 断言，以及内部提示外泄/事实编造候选出局测试；`python -m pytest tests\test_services\test_generator_service.py tests\test_services\test_critic_service.py -q` 输出 `20 passed`，`python -m pytest tests -q` 输出 `52 passed`。
- 小样本复验：`small-sample-20260523-161056` 覆盖 `syn_0012`、`syn_0032` 的 `/api/generator/generate` 与 `/chat`。机械检查通过：未再出现内部提示外泄，也未复现 `syn_0032` 的“三科作业排序”事实编造；两条 `/chat` 均为 `status=answered`、`risk_level=green`，情境分类正确。

## Known Follow-up Issue

- `syn_0012` 在小样本 `/chat` 复验中仍出现第三方动机推测：“也许不是她觉得你不够好，而是她太希望你好了，好到不知道该怎么表达，只能用这种最笨的办法。”
- 该问题不是原始的内部提示外泄，但仍违反“少替第三方解释 / 不推测第三方动机”的方向。后续修复应继续收紧亲子/同伴冲突场景：新视角只能落在孩子自己的感受、需要、边界、关系价值或可控表达上，不解释家长、老师、同学“其实为什么这么做”。
- 该残留问题已同步记录到 `docs/issues/2026-05-22-f3-prompt-iteration-issues.md` 的 `2026-05-23 小样本复验证据` 小节。

## Database Validation

- turns: 45
- messages: 90
- candidates: 90
- preference_pairs: 43
- result: PASS

## Scenario Accuracy

- 亲子摩擦: 14/15 (93.3%)
- 同伴关系: 15/15 (100.0%)
- 学业压力: 14/15 (93.3%)

## Files

- `docs\acceptance\orchestrator-mvp\2026-05-21\runs\real-llm-20260522-215717\raw_results.json`
- `docs\acceptance\orchestrator-mvp\2026-05-21\runs\real-llm-20260522-215717\review_all.csv`
- `docs\acceptance\orchestrator-mvp\2026-05-21\runs\real-llm-20260522-215717\low_quality_only.csv`
