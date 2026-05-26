# F9 主线说明：从 F9 问题回修 F3/F4 的完整链路

日期：2026-05-26

## 当前结论

正式人工 F9 仍暂停。R8 priority 10 条人工复核显示，当前候选质量普遍偏差：ER 仅 1/10 被人工认可应得 2，IP 0/10 被人工认可应得 2。这说明问题已经不只是 `32/40` gate 擦边或阈值口径，而是 F3 候选质量与 F4 高分判断之间存在系统偏差。

当前主线进入 R9/R10：先做模型因素调研，再把 F4 critic 正式切到新模型。R9 发现 `deepseek-v4-pro` 初次失败不是能力结论，而是运行配置不兼容：原 `LLM_MAX_TOKENS` 不足，导致 `finish_reason=length` 且 `content` 为空。R10 已将 F4 单独切到 `deepseek-v4-pro`、`CRITIC_LLM_MAX_TOKENS=4096`、JSON response format；F3 generator 仍保留 `deepseek-chat`，避免生成和打分变量混在一起。

---

## 为什么 F9 牵出 F3/F4

这条线最初不是为了重做 F3/F4，而是 F9 人工信度与自动验收暴露出候选质量和 F4 分数之间的不稳定：一些明显有问题的候选仍能拿到较高 ER/IP。错误分析显示问题来自两侧：

- F3 generator 会生成模板化安抚、品质化总结、强行正向重构、事实/动机补全、成人化引导等候选。
- F4 critic 会把这些问题误判成“还不错的共情”，没有稳定降分或出局。

因此主线变成一个闭环：

`F9 发现信度问题 -> 定位 F3/F4 根因 -> 修 F3/F4 -> 用 F9 validation 重新验收 -> 决定是否进入正式人工 F9`

---

## 轮次总览

| 轮次 | 起因 | 主要修改 | 验证结果 | 结论 / 下一步 |
|---|---|---|---|---|
| R0 | 第一轮 F9 暴露坏候选也能拿高 ER/IP | 做 F9 error analysis，拆出 F3 生成问题与 F4 判分问题 | 确认问题不是单点样本，而是 F3/F4 组合失稳 | 先回修 F4，再回修 F3 |
| R1 | F4 放过旧坏候选 | F4 加 `audit_tags`、deterministic caps，拆分轻重事实补全 | 旧坏候选复评 10/10 达标，ER/IP 2/2 为 2/10；但 F3 sample 25 仍有 `说明你` | F4 第一轮达标，转向 F3 残留 |
| R2 | F3 品质化总结、固定转折仍被探针捕获 | 扩展 global quality probes，收紧 F3 prompt，输出 low-score review queue | hard flags 清零，但 rerun_ER_2=37/40、rerun_IP_2=38/40 | F3 字符串问题缓解，F4 高分饱和重新暴露 |
| R3 | “换谁都会”式承接让引导反思型显得疏离 | F3 增加具体复述约束：承接必须点回学生刚说的具体场景/动作 | 主包单次 PASS：ER=2 31/40，IP=2 31/40；low-score review 3 行人工确认合理 | 主包擦边过，需要 stability rerun |
| R4 | 担心主包 PASS 是采样运气 | 独立跑 `validation-stability/run-1` 与 `run-2` | run-1：ER=2 35/40、IP=2 36/40；run-2：ER=2 36/40、IP=2 36/40 | 主包 PASS 不稳定，不能进正式人工 F9 |
| R5 | sample 39 出现内部结构提示外泄 | F3 禁止括号式阶段标签；F4 增加代码侧 `internal_prompt_leak` hard boundary；生成 high-score diff review queue | 生成 8 行 high-score 差集：10、13、15、19、25、34、36、38 | sample 39 属确定 bug；差集交给人工判断 |
| R6 | 人工复核 high-score diff 后发现 6/8 高分不成立 | 决定不新增 tag、不改阈值，先收紧 F4 ER/IP 高档定义 | sample 10/19 认可高分；sample 13/15/25/34/36/38 暴露“缺陪伴感”和“显性情绪当隐含理解” | F4 ER/IP=2 必须有陪伴感和未明说洞察 |
| R7 | 需要验证 F4 ER/IP 定义收紧是否解决高分饱和 | 更新 F4 spec、runtime prompt 与 prompt 断言测试；联网三次 post-erip validation | 三次均 FAIL：40/40、36/37、38/38；fallback=0，rerun hard flags=0 | prompt 收紧不足以解决高分饱和；下一步人工抽查 post-erip 高分侧 |
| R8 | R7 仍无法区分 F3 批次方差和 F4 judge 方差 | 固定 run-2 候选复评：count=1 看原始抖动，count=3 看 median 稳定性；生成 run-2 双侧人工校准队列 | count=1：ER 1/2 flip 1、IP 1/2 flip 2；count=3：ER 1/2 flip 1、IP 1/2 flip 1；全量队列 48 行，优先队列 8+10+30 | 下一步先人工填写 10 条 priority review，再决定是否需要看 backup |
| R9 | priority 10 条人工复核显示候选普遍质量差，不能只讨论 gate 阈值 | 固定这 10 条候选，做 F4-only 模型对照：`deepseek-chat` baseline vs `deepseek-v4-pro` | baseline 完成；v4-pro 完整 3 repeats 超时，fallback pilot 10/10 `llm_parse_failure` | 失败根因待查，不能把 0/0 当成有效判分 |
| R10 | R9 显示 v4-pro 未跑通，需要正式兼容新模型 | 诊断 raw response；F4 单独使用 `deepseek-v4-pro`、4096 token、JSON response format；F3 仍用 `deepseek-chat` | v4-pro JSON smoke 10/10 无 parse failure；priority 匹配从 10/20 到 11/20 | 新模型已接入 F4，但改善有限；下一步仍要处理 F3 生成质量和 F4 ER 偏宽 |

---

## 逐轮记录

### R0：F9 第一轮暴露系统性问题

起因：

- F9 初始抽样与信度检查发现：候选文本质量和 F4 分数不稳定。
- 一些存在模板化、成人化、事实补全或强行正向重构的候选，仍可能拿较高 ER/IP。

修改：

- 产出 F9 error analysis 与 taxonomy。
- 将问题拆成两侧：
  - F3 负责生成，问题是坏候选来源。
  - F4 负责判分和出局，问题是坏候选没有被稳定拦住。

结果：

- 明确 F9 不只是最终人工标注环节，也承担当前 F3/F4 修复的验收 gate。

下一步：

- 先修 F4 判分执行力，因为旧坏候选被放过会直接污染后续 F9。

---

### R1：F4 第一轮修复 audit tags 与代码侧 cap

起因：

- 旧坏候选里，模板化安抚、强行正向重构、第三方解释、事实补全、成人化引导等问题没有被 F4 稳定降分。
- 仅靠 prompt 文字规则不够，LLM judge 会把规则当建议。

修改：

- 在 F4 judge prompt 中加入 F9 `audit_tags`。
- 在代码侧加入 deterministic caps。
- 将 `unsupported_fact_completion` 拆成轻度事实补全与 `hard_boundary_fabrication`，避免普通事实补全直接触发 hard boundary。
- 为容易混淆的标签补中文示例。
- 增加多标签组合测试，确保 caps 可叠加。

验证结果：

- `old_candidate_expectation_pass = 10/10`
- `old_candidate_ER_IP_2_2 = 2/10`
- `rerun_ER_2 = 22/40`
- `rerun_IP_2 = 22/40`
- gate 仍 FAIL，阻塞是 F3 仍出现 sample 25 的 `说明你` 模式。

结论：

- F4 第一轮对旧坏候选有效。
- 剩余阻塞转向 F3：生成端仍有品质化总结和强行正向重构残留。

下一步：

- 修 F3，不只是禁一个字符串，而是处理 `说明你` 背后的品质化总结倾向。

---

### R2：F3 global probes 与 prompt 收紧

起因：

- F4 第一轮达标后，validation 仍被 F3 生成端的 `说明你` 残留阻塞。
- 该问题不是 sample 25 独有，而是 F3 在共情场景里的默认倾向：把学生痛苦总结成品质、在意、成熟或优点。

修改：

- 扩展 `SAMPLE_PROHIBITED_PATTERNS` / global quality probes，避免只修 sample 25。
- 收紧 F3 prompt，禁止在未充分承接前把痛苦品质化为优点。
- 输出 `f9_low_score_review_queue.csv`，用于人工确认 F4 是否矫枉过正。

验证结果：

- `generated_detected_flags = 0`
- `rerun_detected_flags = 0`
- `generated_global_quality_flagged_rows = 0/20`
- `rerun_global_quality_flagged_rows = 2/40`
- `generator_fallback_rows = 0`
- 但 `rerun_ER_2 = 37/40`，`rerun_IP_2 = 38/40`

结论：

- F3 字符串与探针层面的问题缓解。
- 但 F4 ER/IP 高分饱和重新出现，说明要继续看高分侧是否漏判，不能只看 hard flags。

下一步：

- 检查生成文本实际质量，尤其是引导反思型的承接是否真的让学生感觉被接住。

---

### R3：F3 具体复述约束

起因：

- 人工观察 sample 2 等候选后发现：“换谁都会觉得……”这类泛化承接，即使没有命中 hard flag，也会显得高高在上、事不关己。
- 问题主要在 F3 引导反思型的节奏：情绪还没被接住，就快速进入归因式提问。

修改：

- 在 F3 共同约束中加入：承接必须包含对学生刚说的具体事件、场景或动作的复述。
- 明确“换谁都会”“这种感觉很正常”等泛化句最多只能作为具体复述后的补充，不能单独充当承接。
- 引导反思型开头改为“一句具体复述接住情绪”；承接可以短，但不能空。

验证结果：

- 主包 validation 单次 PASS。
- `rerun_ER_2 = 31/40`
- `rerun_IP_2 = 31/40`
- `generated_detected_flags = 0`
- `rerun_detected_flags = 0`
- `generated_global_quality_flagged_rows = 0/20`
- `rerun_global_quality_flagged_rows = 0/40`
- `generator_fallback_rows = 0`
- low-score review queue 有 3 行：sample 19/c2、25/c2、36/c1。

人工低分抽查：

- sample 19/c2：`forced_positive_reframe` 成立。
- sample 25/c2：`adult_coaching_question` 成立。
- sample 36/c1：`template_low_information` 与 EX 关闭对话问题成立。

结论：

- 主包自动 gate 与低分抽查通过。
- 但 ER/IP=2 只比 `32/40` 上限低 1 条，不能视为稳定准入。

下一步：

- 独立重跑 stability validation，验证主包 PASS 是否只是采样低点。

---

### R4：stability rerun 失败

起因：

- 主包 ER/IP=2 为 31/40，贴近 32/40 上限。
- F3 是高温生成，同配置重复运行可能改变候选分布。

修改：

- 不覆盖主包，新增独立 stability rerun：
  - `docs/corpus/f9/validation-stability/run-1/`
  - `docs/corpus/f9/validation-stability/run-2/`

验证结果：

| run | decision | rerun_ER_2 | rerun_IP_2 | 主要失败原因 |
|---|---|---:|---:|---|
| `validation-stability/run-1` | FAIL | 35/40 | 36/40 | ER/IP=2 超过 32/40 |
| `validation-stability/run-2` | FAIL | 36/40 | 36/40 | ER/IP=2 超过 32/40 |

结论：

- 主包 PASS 不稳定。
- 当前不能把 `validation/rerun/f9_rerun_blind_annotation.csv` 作为正式人工 F9 入口。
- 失败不来自 fallback 或 hard flags，而是高分侧分布不稳。

下一步：

- 同时检查两个方向：
  - 是否存在 F4 高分侧漏判。
  - `32/40` 是否过紧。

---

### R5：sample 39 内部提示外泄与 high-score diff queue

起因：

- 对称抽查发现 sample 39/c2 出现可见结构提示：
  - `（先接住你的场景）`
  - `（再递新视角）`
- 这类内容是内部提示外泄，不是普通分数高低问题。
- F4 当时只把它标成 `adult_coaching_question`，EX 降到 1，但 ER/IP 仍为 2，没有 hard boundary。

修改：

- F3 prompt 增加括号式阶段标签禁令，禁止最终回复中出现 `（先接住...）`、`（再递...）`、`（共情）`、`（提问）` 等内部结构提示。
- F4 增加代码侧 deterministic boundary：
  - 命中内部提示外泄 marker 或括号式阶段标签，直接 `boundary_flag=true`。
  - `boundary_reason=internal_prompt_leak`。
  - 不再依赖 LLM judge 自行识别。
- 新增 `scripts/corpus/f9_stability_diff.py`，生成 high-score 差集 review queue。

验证结果：

- 相关 generator / critic / diff 脚本测试通过。
- 生成 `docs/corpus/f9/validation-stability/run-2/f9_high_score_diff_review_queue.csv`。
- 差集共 8 行：sample 10、13、15、19、25、34、36、38。
- 队列包含 `scenario`、`student_text`、stability 候选与 F4 rationale，人工列供人工填写。

结论：

- sample 39 是确定 bug，已补 F3 禁令和 F4 hard boundary。
- high-score 差集需要人工判断，脚本不能替代。

下一步：

- 人工填写 high-score diff queue，判断这些新增 ER/IP=2 是否真的成立。

---

### R6：人工复核 high-score diff 后收紧 F4 ER/IP 高档定义

起因：

- 人工填写 high-score diff queue 后，8 条中只有 sample 10/19 被认可为高分基本成立。
- sample 13/15/25/34/36/38 暴露出 F4 高分侧问题。

人工发现的问题：

- ER：候选能说出或深化情绪，但像旁观者分析，没有让孩子感到被陪伴、被关心。
- IP：候选把孩子已经明说的情绪或担忧换词复述，却被当作“未明说的深层理解”给到 2。

修改决策：

- 不新增 `low_care` 或 `explicit_emotion_restatement` audit tag。
- 不修改 cap 逻辑。
- 不调整 `32/40` 阈值。
- 先收紧 ER=2 / IP=2 的正向档位定义：
  - ER=2 必须有“有人在陪我、在乎我”的陪伴感。
  - IP=2 必须点出孩子没有明说、但藏在话里的情绪或担忧。
  - 只是复述、分析或命名情绪，默认最高落在 1。

验证准备：

- sample 10/19 作为正向对照，但只按具体候选文本判断，不作为无条件锚点。

结论：

- 这一轮处理的是“高档门槛过松”，不是新的坏模式 tag。

下一步：

- 同步 F4 spec、runtime prompt 和 prompt 断言测试，再跑三次 post-erip validation。

---

### R7：F4 ER/IP 定义收紧后 post-erip 三连跑

起因：

- R6 决定先稳定 F4 ER/IP 高档定义，再讨论阈值。

修改：

- 更新 `docs/specs/f4-critic-epitome-codex-spec.md`。
- 更新 `app/services/critic_service.py` 中的 F4 runtime prompt。
- 更新 `tests/test_services/test_critic_service.py`，断言 prompt 包含：
  - `旁观者在描述他的状态`
  - `有人在陪我、在乎我`
  - `气死了`
  - `是不是我哪里不好`
  - `孩子没有明说、但藏在话里的情绪或担忧`

本地验证：

- `C:\Python313\python.exe -m pytest tests\test_services\test_critic_service.py -q`：23 passed
- `C:\Python313\python.exe -m pytest -q`：102 passed

post-erip validation：

| run | decision | rerun_ER_2 | rerun_IP_2 | generated_flags | rerun_flags | generated_global | rerun_global | fallback |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `validation-stability/post-erip-run-1` | FAIL | 40/40 | 40/40 | 0 | 0 | 1/20 | 2/40 | 0 |
| `validation-stability/post-erip-run-2` | FAIL | 36/40 | 37/40 | 0 | 0 | 0/20 | 2/40 | 0 |
| `validation-stability/post-erip-run-3` | FAIL | 38/40 | 38/40 | 1 | 0 | 1/20 | 1/40 | 0 |

补充：

- 沙箱内首次运行出现 `generator_fallback_rows=60` 与 `llm_failure`，经最小 DeepSeek 调用确认是网络连接失败。
- 上表为联网后覆盖重跑的有效结果。
- fallback 均为 0，rerun hard flags 均为 0。

结论：

- 仅靠 prompt 收紧 ER/IP 档位定义，不足以解决 F4 高分饱和。
- 当前不能进入正式人工 F9。
- 下一步不能继续第 8 轮全局 prompt 收紧；必须先把 F3 高温生成批次方差和 F4 judge 残余抖动分开看。

下一步：

- 进入 R8：固定 `post-erip-run-2` 候选包复评，并生成 run-2 双侧人工校准队列。

---

### R8：固定候选复评与 gate 重新定位

起因：

- R7 三次 `post-erip` validation 的 `rerun_ER_2` / `rerun_IP_2` 分别为 40/40、36/37、38/38。
- 这些数字来自完整 validation，每次都会重新运行 F3 高温生成，因此不能直接判定为 F4 对同一候选随机抖动。
- F4 当前已默认 `CRITIC_SAMPLE_COUNT=3` 并取中位数；R8 不是补做 median，而是诊断 median 前后的稳定性。

修改：

- 新增固定候选复评脚本，对 `post-erip-run-2/rerun/f9_rerun_selected_scores.csv` 的同一批 40 条候选重复打分。
- `CRITIC_SAMPLE_COUNT=1` 跑 3 次，用于观察未经 median 平滑的单次原始抖动。
- `CRITIC_SAMPLE_COUNT=3` 跑 3 次，用于观察现有 median 策略是否足够压住 F4 judge 抖动。
- 新增 run-2 人工校准队列：保留 ER/IP=2 的高分侧，也保留未给 2 的另一侧；前置 R6 已人工标注的 8 条校准样例。

验证结果：

| 复评配置 | summary rows | run rows | boundary/llm failures | ER 1/2 flip | IP 1/2 flip | ER unstable | IP unstable |
|---|---:|---:|---:|---:|---:|---:|---:|
| `count=1, repeats=3` | 40 | 120 | 0 | 1 | 2 | 0 | 1 |
| `count=3, repeats=3` | 40 | 120 | 0 | 1 | 1 | 0 | 1 |

补充：

- `count=1` 的有效复评中，120 次评分里 ER=2 为 105 次、IP=2 为 107 次。
- `count=3` 的有效复评中，120 次评分里 ER=2 为 105 次、IP=2 为 109 次。
- `count=3` 仍有 1 条 IP 在 1/2 间波动，不能说 F4 完全无抖动；但固定候选复评的波动明显小于完整 validation 的跨批次波动。
- 人工校准队列已生成 48 行：8 条 R6 校准样例 + 40 条 run-2 review；review 中 36 条为 ER/IP=2，3 条为 ER/IP 都非 2，1 条为 ER 非 2。
- 为降低人工负担，已生成优先队列：`f9_priority_review_queue.csv`。该文件仍含 48 行，但分为 8 条 `calibration`、10 条 `priority`、30 条 `backup`。第一轮只需要填写 10 条 `priority` review。

判断规则：

- 如果 count=1 抖动明显、count=3 稳定：说明 median 已压住 F4 judge 抖动，R7 分布波动主要来自 F3 高温生成批次差异。
- 如果 count=3 固定候选仍明显抖动：先评估 `CRITIC_SAMPLE_COUNT=5` 或更强锚点，不进入正式 F9。
- 如果固定候选稳定，但人工校准发现大量 2 分不成立：定点修具体漏判模式，不再全局收紧 ER/IP 定义。
- 如果固定候选稳定，且人工认为多数 2 分成立：`32/40` 更可能是过紧经验 gate，应讨论降级为诊断项，并重新设计正式 F9 分层抽样。

当前结论：

- 固定候选复评没有出现网络或 fallback 失败，R8 数据可用。
- F4 对固定候选不是完全无抖动，但 count=3 下只剩少量边缘波动；下一步决策需要结合人工校准队列，而不是继续全局收紧 prompt。

下一步：

- 人工填写 `docs/corpus/f9/validation-stability/post-erip-run-2/f9_priority_review_queue.csv` 中 10 条 `review_bucket=priority` 的 review。
- R8 人工校准完成前，不修改 F3/F4 prompt，不修改 `32/40` gate，不启动正式人工 F9。

---

### R9：模型因素调研与 F4-only 对照实验

起因：

- R8 priority 10 条人工复核已完成。
- 人工判断结果：ER 仅 1/10 认可应得 2，IP 0/10 认可应得 2。
- 人工理由集中在“语义重复”“没有承接安慰”“只是在找原因/深化情绪”“问题像复盘或说教”。
- 这说明当前问题不是单纯 `32/40` gate 过严，也不是只靠继续看 backup 就能解决；需要先判断是否存在模型能力瓶颈。

当前模型前提：

- `.env` 中 `LLM_PROVIDER=deepseek`，`DEEPSEEK_MODEL=deepseek-chat`。
- F3 generator 与 F4 critic 当前共用该 DeepSeek 模型配置；F3 temperature 为 0.8，F4 temperature 为 0.1，F4 已使用 `CRITIC_SAMPLE_COUNT=3` median。
- DeepSeek 官方文档中 `deepseek-chat` 属于 legacy 名称，当前指向 `deepseek-v4-flash` 非思考模式；官方模型列表包含 `deepseek-v4-flash` 与 `deepseek-v4-pro`。

修改：

- 新增 R9 独立计划文档：`docs/corpus/f9/f9-model-eval-plan.md`。
- 扩展 `scripts/corpus/f9_fixed_candidate_rescore.py`：
  - 支持读取 `f9_priority_review_queue.csv` 中的 `user_text` / `candidate_text` 列。
  - 支持 `--bucket priority`，只复评 10 条 priority。
  - 支持 `--deepseek-model`，在本次 F4 复评中临时覆盖模型，不修改 `.env`。
  - manifest 记录 `deepseek_model`、`bucket`、输入行数和实际复评行数。
- 新增 `scripts/corpus/f9_model_eval.py`，用于把 baseline / candidate 复评结果与人工 priority 标签对齐，输出模型对比表和 summary。

验证目标：

- baseline：当前 `deepseek-chat` 对 priority 10 条的 F4 复评结果。
- candidate：`deepseek-v4-pro` 对同一 10 条的 F4 复评结果。
- 对比项：每条样本的人标 ER/IP、baseline ER/IP、v4-pro ER/IP、各自是否更接近人工，以及 sample 6 这种人工认可 ER 的样本是否被误杀。

执行结果：

- baseline `deepseek-chat`：`CRITIC_SAMPLE_COUNT=3`、`repeats=3` 完成，输出目录为 `docs/corpus/f9/validation-stability/model-eval/deepseek-chat/`。
- candidate `deepseek-v4-pro`：按 `CRITIC_SAMPLE_COUNT=3`、`repeats=3` 运行超时，未生成完整产物。
- fallback pilot：按 `CRITIC_SAMPLE_COUNT=3`、`repeats=1` 完成，但 10/10 行最终均为 `llm_parse_failure`，输出目录为 `docs/corpus/f9/validation-stability/model-eval/deepseek-v4-pro/`。
- 修正后的模型对比脚本会把 `llm_parse_failure` 标记为 invalid，不再把 0/0 误算成贴近人工。
- 对比 summary：baseline valid rows 10/10，candidate invalid rows 10/10；因此本轮不能得出“v4-pro 更准”的结论。

决策规则：

- 如果 `deepseek-v4-pro` 明显更接近人工，且不误杀 sample 6：优先考虑升级 F4 judge 或引入高质量模型复核。
- 如果 `deepseek-v4-pro` 也和人工差距大：问题不只是模型能力，继续换模型收益有限，应转向 F3 生成策略和人工标注锚点。
- 如果 `deepseek-v4-pro` 只是整体变严但没有更接近人工：不能采纳，避免把“更低分”误当“更准”。

下一步：

- 不把 v4-pro 的 0/0 当成准确降分；它们来自解析失败。
- 若继续模型路线，先做结构化输出兼容性诊断：捕获 v4-pro 原始响应、评估 JSON mode / 更强 schema 约束 / 更小样本单调用。
- 在结构化输出问题解决前，不做 F3 生成模型实验，不修改 F3/F4 prompt，不修改 `32/40` gate，不启动正式人工 F9。

---

## 当前阻塞点

### 阻塞点 1：priority 10 条显示质量普遍偏差，新 F4 模型只能小幅改善

R8 priority 10 条人工判断中，ER 仅 1/10 认可应得 2，IP 0/10 认可应得 2。`deepseek-chat` baseline 在 20 个 ER/IP 标签里只匹配 10 个；R10 的 `deepseek-v4-pro` JSON smoke 匹配 11 个。新模型解决了部分 IP 偏宽，但 ER 仍明显偏宽，不能单靠模型升级解决。

### 阻塞点 2：F4 已切新模型，但 F9 仍不能启动

F4 已正式改为 critic 专用模型配置，但当前只完成了 10 条 smoke 级验证。正式人工 F9 仍不能启动；需要先决定是否扩大 v4-pro 复评，还是回到 F3 生成策略修“语义重复、无安慰、像复盘”的候选质量问题。

当前存在三种可能：

| 可能性 | 含义 | 下一步 |
|---|---|---|
| A：扩大模型验证 | v4-pro smoke 有效但提升很小 | 跑 `CRITIC_SAMPLE_COUNT=3` 的 priority 10 完整对照，再判断是否值得大规模使用 |
| B：回修 F3 | 人工认为候选普遍质量差，模型只小幅改善 | 优先改生成策略，减少复述/分析/说教式候选 |
| C：混合路线 | v4-pro 作为 F4 复核有价值但成本高 | 用 v4-pro 复核高风险/高分样本，不作为所有候选的实时主 judge |

### 阻塞点 3：正式人工 F9 不能启动

正式人工 F9 的前提是候选质量、F4 judge 口径和人工锚点都足够明确。priority 10 条已经显示 F3/F4 偏差较大，因此不能把任一 rerun 包直接作为正式人工 F9 入口。

---

## 下一步决策

下一步不是继续泛泛调 prompt，也不是让人工继续看完 30 条 backup，而是在 R10 基础上做一次决策：

1. 如果要继续模型路线：跑 priority 10 的 `CRITIC_SAMPLE_COUNT=3` 完整 v4-pro 对照，确认 smoke 的 11/20 是否稳定。
2. 如果接受 smoke 已足够判断：转向 F3 生成策略，减少“复述 + 加深情绪 + 分析提问”的默认生成模式。
3. 如果担心成本：把 v4-pro 定位成离线复核模型，而不是实时全量 judge。
4. 在这个分支未决前，不启动正式人工 F9。

人工判断仍不可替代；R9 只用已有 priority 人标作为锚点，不由脚本替人工新增判断。

---

## 不能做的事

1. 不能因为主包曾经单次 PASS，就进入正式人工 F9。
2. 不能为了通过 `32/40`，故意让 F3 生成更差的候选。
3. 不能只看 low-score review queue；它覆盖的是“被降分是否误伤”，不覆盖“高分是否漏判”。
4. 不能由脚本直接判定“阈值错了”或“F4 错了”。
5. 不能把 post-erip 三次 FAIL 解释成 fallback 或网络问题；有效联网重跑显示 fallback 为 0，主因是 ER/IP=2 过高。

---

## 文档阅读顺序

建议按这个顺序看：

1. `docs/corpus/f9/f9-mainline.md`：主线、轮次、当前阻塞和下一步。
2. `docs/corpus/f9/README.md`：当前产物路径和 gate 状态索引。
3. `docs/corpus/f9/f4-fix-execution-summary.md`：每轮执行细节、测试命令和 validation 指标。
4. `docs/corpus/f9/f9-stability-gate-plan.md`：stability gate 的执行任务列表。
5. `docs/corpus/f9/f3-fix-plan.md` / `docs/corpus/f9/f4-fix-plan.md`：需要追溯具体 prompt 或 cap 设计时再看。
