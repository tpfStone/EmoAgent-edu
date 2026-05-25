# F9 Golden/F4 Rerun Validation Report

## Run Config

- llm_provider: deepseek
- deepseek_model: deepseek-chat
- critic_sample_count: 3
- golden_sample_nos: [3, 11, 16, 19, 22, 25, 27, 31, 40, 15]
- f9_rerun_rows: 40

## Gate Decision

- decision: FAIL
- old_candidate_expectation_pass: 10/10 (门槛: >= 8/10)
- old_candidate_ER_IP_2_2: 2/10 (上限: <= 2/10)
- rerun_ER_2: 22/40 (上限: <= 32/40)
- rerun_IP_2: 22/40 (上限: <= 32/40)
- generated_detected_flags: 1 (门槛: 0)
- rerun_detected_flags: 1 (门槛: 0)
- generator_fallback_rows: 0 (门槛: 0)

## Automatic Gate Criteria

- 旧坏候选 F4 复评通过率至少 80%。
- 旧坏候选 ER/IP 同时 2/2 的比例不超过 20%。
- 重跑样本 ER=2 与 IP=2 的比例都不超过 80%，避免接近满分饱和。
- F4 rationale 若识别模板化、第三方解释、事实补全、强行重构，分数必须实际降下来。
- F3 golden 与重跑样本不得出现检测到的第三方事实/动机补全等 regression flags。
- 生成器不得 fallback。

## Blocking Reasons

- F3 golden 检测到 1 条 flagged rows，需清除第三方事实/动机补全等残留。
- 重跑样本检测到 1 条 flagged rows，不应进入正式人工 F9。

## Golden Generated Candidates

- generated_candidate_rows: 20
- f3_regression_pass_distribution: {'true': 19, 'false': 1}
- rows_with_detected_flags: 1
- ER/IP_all_2: False
- F4_distribution: {'ER': {'1': 9, '2': 11}, 'IP': {'1': 10, '2': 10}, 'EX': {'0': 16, '1': 3, '2': 1}}

## Existing Bad Candidate F4 Re-score

- old_candidate_rows: 10
- f4_expectation_pass_distribution: {'true': 10}
- expectation_failed_rows: 0
- ER/IP_all_2: False
- F4_distribution: {'ER': {'1': 8, '2': 2}, 'IP': {'1': 6, '2': 2, '0': 2}, 'EX': {'0': 7, '2': 1, '1': 2}}

## F9 Rerun Package

- blind_annotation_path: `docs\corpus\f9\validation\rerun\f9_rerun_blind_annotation.csv`
- f4_holdout_path: `docs\corpus\f9\validation\rerun\f9_rerun_f4_scores_holdout.csv`
- rerun_scores_path: `docs\corpus\f9\validation\rerun\f9_rerun_selected_scores.csv`
- f3_detected_flags_in_selected_rows: 1
- generator_fallback_rows: 0
- ER/IP_all_2: False
- F4_distribution: {'ER': {'2': 22, '1': 18}, 'IP': {'2': 22, '1': 18}, 'EX': {'1': 9, '0': 26, '2': 5}}

## Generated Flagged Rows

| sample_no | candidate_id | flags |
|---:|---|---|
| 25 | c2 | contains:说明你 |

## F9 Rerun Selected Flagged Rows

| sample_no | flags |
|---:|---|
| 25 | contains:说明你 |
