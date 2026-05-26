# R9 模型因素调研与 F4-only 对照实验计划

日期：2026-05-26

## 当前判断

R8 priority 10 条人工复核后，问题已经不能简化成 `32/40` gate 是否太严：

- ER：人工仅认可 1/10 条应得 2。
- IP：人工认可 0/10 条应得 2。
- 主要问题是语义重复、缺少真正承接安慰、把显性情绪换词复述、提问像复盘或说教。

这说明当前候选质量和 F4 高分判断都存在系统偏差。下一轮先查模型因素，不继续盲目改 prompt。

## 模型前提

当前本地配置：

- `.env`：`LLM_PROVIDER=deepseek`
- `.env`：`DEEPSEEK_MODEL=deepseek-chat`
- F3 generator temperature：0.8
- F4 critic temperature：0.1
- F4 critic sample count：3，并取中位数

DeepSeek 官方文档当前口径：

- `deepseek-chat` 是 legacy 名称，当前对应 `deepseek-v4-flash` 的非思考模式。
- 官方模型列表包含 `deepseek-v4-flash` 与 `deepseek-v4-pro`。
- 本轮只把 `deepseek-v4-pro` 作为 F4 judge 对照模型，不直接更换 F3 generator。

参考：

- https://api-docs.deepseek.com/updates/
- https://api-docs.deepseek.com/api/list-models
- https://api-docs.deepseek.com/quick_start/pricing

## 实验原则

本轮只做 F4-only 模型对照：

- 固定候选文本：使用 `docs/corpus/f9/validation-stability/post-erip-run-2/f9_priority_review_queue.csv` 中 10 条 `review_bucket=priority`。
- 固定人工锚点：使用用户已经填写的 ER/IP yes/no 标签。
- 只替换 F4 judge 模型：baseline 为 `deepseek-chat`，candidate 为 `deepseek-v4-pro`。
- 不重跑 F3，不修改 F3/F4 prompt，不修改 `32/40` gate，不启动正式人工 F9。

这样可以把“候选生成质量”和“打分模型能力”拆开看。

## 执行步骤

1. 扩展固定候选复评脚本：
   - 支持读取 `user_text` / `candidate_text` 列。
   - 支持 `--bucket priority`。
   - 支持 `--deepseek-model`，仅覆盖本次复评模型，不改 `.env`。
   - manifest 记录 `deepseek_model`、`bucket`、输入行数、实际复评行数。

2. 新增模型对比脚本：
   - 输入人工 priority 队列。
   - 输入 baseline 复评 summary。
   - 输入 candidate 复评 summary。
   - 输出 `f9_priority_model_comparison.csv` 和 summary markdown。

3. 运行 baseline：

   ```powershell
   $env:LLM_TIMEOUT='60'
   C:\Python313\python.exe scripts\corpus\f9_fixed_candidate_rescore.py --input-scores docs\corpus\f9\validation-stability\post-erip-run-2\f9_priority_review_queue.csv --output-dir docs\corpus\f9\validation-stability\model-eval\deepseek-chat --critic-sample-count 3 --repeats 3 --bucket priority --deepseek-model deepseek-chat
   ```

4. 运行 candidate：

   ```powershell
   $env:LLM_TIMEOUT='60'
   C:\Python313\python.exe scripts\corpus\f9_fixed_candidate_rescore.py --input-scores docs\corpus\f9\validation-stability\post-erip-run-2\f9_priority_review_queue.csv --output-dir docs\corpus\f9\validation-stability\model-eval\deepseek-v4-pro --critic-sample-count 3 --repeats 3 --bucket priority --deepseek-model deepseek-v4-pro
   ```

5. 生成对比：

   ```powershell
   C:\Python313\python.exe scripts\corpus\f9_model_eval.py --human-queue docs\corpus\f9\validation-stability\post-erip-run-2\f9_priority_review_queue.csv --baseline docs\corpus\f9\validation-stability\model-eval\deepseek-chat\f9_fixed_candidate_rescore_summary.csv --candidate docs\corpus\f9\validation-stability\model-eval\deepseek-v4-pro\f9_fixed_candidate_rescore_summary.csv --output-dir docs\corpus\f9\validation-stability\model-eval --baseline-model deepseek-chat --candidate-model deepseek-v4-pro
   ```

## 判定规则

如果 `deepseek-v4-pro` 明显更接近人工：

- 尤其能把“语义重复 / 无陪伴 / 显性复述”从 ER/IP=2 降下来；
- 同时不误杀 sample 6 这种人工认可 ER 的样本；
- 则优先考虑升级 F4 judge，或引入高质量模型复核。

如果 `deepseek-v4-pro` 也和人工差距大：

- 说明问题不只是模型能力；
- 继续换模型收益有限；
- 下一步转向 F3 生成策略和人工标注锚点。

如果 `deepseek-v4-pro` 只是整体变严：

- 但没有更接近人工，或误杀 sample 6；
- 不能采纳，避免把“更低分”误当“更准”。

## 输出产物

- `docs/corpus/f9/validation-stability/model-eval/deepseek-chat/f9_fixed_candidate_rescore_summary.csv`
- `docs/corpus/f9/validation-stability/model-eval/deepseek-v4-pro/f9_fixed_candidate_rescore_summary.csv`
- `docs/corpus/f9/validation-stability/model-eval/f9_priority_model_comparison.csv`
- `docs/corpus/f9/validation-stability/model-eval/f9_priority_model_comparison_summary.md`

## 执行结果

baseline：

- 模型：`deepseek-chat`
- 配置：`CRITIC_SAMPLE_COUNT=3`，`repeats=3`
- 结果：完成。
- 输出目录：`docs/corpus/f9/validation-stability/model-eval/deepseek-chat/`

candidate：

- 模型：`deepseek-v4-pro`
- 原计划配置：`CRITIC_SAMPLE_COUNT=3`，`repeats=3`
- 结果：超时，未生成完整产物。

fallback pilot：

- 模型：`deepseek-v4-pro`
- 配置：`CRITIC_SAMPLE_COUNT=3`，`repeats=1`
- 结果：完成，但 10/10 行均触发 `llm_parse_failure`。
- 输出目录：`docs/corpus/f9/validation-stability/model-eval/deepseek-v4-pro/`

修正后的模型对比：

- 输出：`docs/corpus/f9/validation-stability/model-eval/f9_priority_model_comparison.csv`
- summary：`docs/corpus/f9/validation-stability/model-eval/f9_priority_model_comparison_summary.md`
- baseline valid rows：10/10
- candidate invalid rows：10/10
- 结论：当前不能判断 `deepseek-v4-pro` 是否更接近人工；它作为 drop-in F4 judge 替换不可用。

## R9 后续决策

R9 初次不能采纳 `deepseek-v4-pro` 结果：

- 0/0 分数来自 `llm_parse_failure` 兜底，不是有效判分。
- fallback pilot 仍耗时较长，说明即便解决结构化输出问题，也需要评估成本。

下一步二选一：

1. 继续模型路线：
   - 做最小 raw-response 诊断，只跑 1-2 条 priority。
   - 捕获 `deepseek-v4-pro` 原始输出。
   - 判断是否可通过 JSON mode、schema 约束或 prompt 输出格式修正解决。

2. 暂停模型路线：
   - 回到 F3 生成策略。
   - 重点处理 priority 人工标注暴露的“语义重复、缺少安慰、提问像复盘”的候选质量问题。

## R10 正式新模型接入结果

根因诊断：

- `deepseek-v4-pro` 初次 `llm_parse_failure` 的直接原因是输出预算不足。
- 原调用在较小 `max_tokens` 下返回 `finish_reason=length`，且 `message.content` 为空。
- 提高到 4096 token 并启用 `response_format={"type":"json_object"}` 后，`message.content` 能返回可解析 JSON；模型的思考内容在 `reasoning_content` 中，不应被当作最终 JSON。

代码改动：

- F3 generator 继续使用 `DEEPSEEK_MODEL=deepseek-chat`。
- F4 critic 新增独立模型配置：
  - `CRITIC_DEEPSEEK_MODEL=deepseek-v4-pro`
  - `CRITIC_LLM_MAX_TOKENS=4096`
  - `CRITIC_LLM_RESPONSE_FORMAT_JSON=true`
- 依赖层新增 critic 专用 LLM client，避免 F3/F4 共用同一个模型实例。
- `f9_validation.py` 与 fixed rescore 脚本同步使用 critic 专用模型。

smoke 验证：

- 命令：priority 10 条，`CRITIC_SAMPLE_COUNT=1`，`repeats=1`。
- 输出目录：`docs/corpus/f9/validation-stability/model-eval/deepseek-v4-pro-json-smoke/`
- 结果：10/10 行无 `llm_parse_failure`。
- 对比目录：`docs/corpus/f9/validation-stability/model-eval/json-smoke-comparison/`
- baseline `deepseek-chat`：10/20 匹配人工 ER/IP。
- candidate `deepseek-v4-pro-json-smoke`：11/20 匹配人工 ER/IP。

解释：

- 新模型已能作为 F4 judge 跑通。
- 改善存在但很小，主要体现在部分 IP 从 2 降到 1。
- ER 仍偏宽；sample 10 仍被新模型打到 ER/IP=2。
- 这说明模型升级不是充分解法，后续仍需要处理 F3 候选质量或 F4 ER 判分锚点。

## 约束

- 不把 R9 结果解释成正式 F9 信度。
- 不由脚本替代人工判断；脚本只比较模型输出是否贴近已有人工标签。
- 不为了压低 ER/IP=2 数量而让 F3 生成更差文本。
- 不在 F4-only 结果明确前启动 F3 生成模型实验。
