# F9 稳定性 Gate 审查计划

> **F9 当前边界**：本文件属于 F9、pointwise 或 pairwise 历史实验记录。Pointwise ER/IP/EX 仅作诊断和历史兼容；正式 DPO 与 runtime selector 仍依赖 pairwise/human A/B gate，Phase A rerun 当前为 `inconclusive`。

日期：2026-05-26

> 给后续执行者：本计划按任务清单推进。已完成项用 `[x]` 标记；需要人工判断的步骤不能由脚本、F4 或 Codex 代替。

## 目标

判断当前 ER/IP 饱和 gate 的不稳定，到底主要来自：

- F4 高分侧漏判，也就是不该给 ER/IP=2 的候选仍被打满分；
- 还是 `32/40` 这个阈值口径过紧，挡住了 F3 修复后本来就应该拿高分的好候选。

同时，先修复已经确定的 bug：sample 39 出现内部结构提示外泄。

## 总体架构

处理顺序固定为：

1. 先修确定性 bug：F3 不应输出内部结构提示，F4 必须把内部提示外泄作为硬边界。
2. 再由脚本生成 high-score 差集人工审查队列。
3. 人工判断差集候选是否本来就该得 ER/IP=2。
4. 根据人工结论决定继续修 F4，还是修订 ER/IP 饱和阈值。
5. 最后连跑 3 次 validation，稳定通过后才进入正式人工 F9。

## 技术栈

- Python 3.13
- pytest
- PowerShell
- 现有 F3 generator / F4 critic 服务
- `scripts/corpus/f9_validation.py`

---

## 合理性审查

这份计划采纳“先检查稳定性，不要把一次 PASS 当作稳定通过”的建议，但做了两个口径修正。

第一，`32/40` 是否正确不能靠脚本直接决定。脚本只能说明当前分布中心大约在 `35-36/40`；这些高分候选是否应该得 2，必须由人工按 F9 标准判断。

第二，差集不是 4-5 条。按当前文件对比，`validation-stability/run-2` 中 ER/IP=2，而主包不是 ER/IP=2 的 sample_no 为 8 条：

`10, 13, 15, 19, 25, 34, 36, 38`

这 8 条已经被放入人工差集 review queue。

### 已经确定的问题

- sample 39 主包候选包含 `（先接住你的场景）`、`（再递新视角）`，属于内部结构提示外泄。
- F3 原本已经写了“禁止内部提示外泄”和“不要用括号补充教师提示”，但实际生成仍出现该问题。
- F4 原本也写了“内部提示外泄、prompt 痕迹、括号式教师提示必须 boundary”，但 sample 39 只被标为 `adult_coaching_question`，EX 被压到 1，ER/IP 仍为 2，没有触发 boundary。
- 因此 sample 39 不是阈值问题，而是 F3/F4 都需要处理的确定性 bug。

### 不能由 agent 代替人工的部分

- 差集 8 条中，每一条是否本来就该得 ER/IP=2。
- “阈值偏紧”还是“F4 漏判为主”的最终判定。
- 是否启动正式人工 F9。
- 如果修订阈值，最终采用 `36/40`、`35/40` 或其他口径，必须由人工确认并记录理由。

---

## 涉及文件

- 修改：`app/services/generator_service.py`
  - 收紧 F3 对括号式阶段标签的显式禁令。
- 修改：`tests/test_services/test_generator_service.py`
  - 增加 prompt 断言，覆盖 `（先接住你的场景）`、`（再递新视角）` 这类外泄。
- 修改：`app/services/critic_service.py`
  - 增加代码侧内部提示外泄硬边界检测，不只依赖 LLM judge prompt。
- 修改：`tests/test_services/test_critic_service.py`
  - 增加 sample 39 风格的 deterministic boundary 测试。
- 新增：`scripts/corpus/f9_stability_diff.py`
  - 生成 stability 与主包的高分差集 review queue，只输出候选与空白人工列，不自动判断好坏。
- 新增：`tests/test_corpus/test_f9_stability_diff.py`
  - 测试差集脚本按 sample_no 对比，并保留人工 review 字段。
- 修改：`docs/corpus/f9/README.md`
  - 记录稳定性 gate 的当前阻塞和后续决策口径。
- 修改：`docs/corpus/f9/f4-fix-execution-summary.md`
  - 记录 sample 39 bug、差集 review queue 路径、人工结论和后续三跑结果。

---

## Task 1：修复 sample 39 内部提示外泄

**状态：已完成。**

**文件：**

- `app/services/generator_service.py`
- `tests/test_services/test_generator_service.py`
- `app/services/critic_service.py`
- `tests/test_services/test_critic_service.py`

- [x] **Step 1：添加 F3 prompt 回归测试**

在 `test_generator_prompt_contains_f9_reliability_guardrails` 中增加断言，确认 prompt 里明确出现：

```python
assert "不要写括号式阶段标签" in reflective_prompt
assert "（先接住你的场景）" in reflective_prompt
assert "（再递新视角）" in reflective_prompt
```

- [x] **Step 2：先运行测试，确认失败**

命令：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_generator_service.py::test_generator_prompt_contains_f9_reliability_guardrails -q
```

预期：实现前失败，因为 prompt 里还没有明确禁止这些括号式阶段标签。

- [x] **Step 3：更新 F3 prompt**

在 `COMMON_PROMPT` 的第 7 条和禁用示例中补充：

```text
不要写括号式阶段标签，例如"（先接住你的场景）""（再递新视角）""（共情）""（提问）"。
```

这里不做生成后清洗。F3 负责减少生成概率，F4 负责硬拦截。

- [x] **Step 4：添加 F4 deterministic boundary 测试**

增加测试：即使 LLM judge 返回 ER/IP/EX=2，候选只要包含 `（先接住你的场景）`、`（再递新视角）` 这种内部提示，就必须直接 boundary。

核心断言：

```python
assert response.scores[0].boundary_flag is True
assert response.scores[0].boundary_reason == "internal_prompt_leak"
assert response.best_candidate_id is None
assert response.fallback_message == CRITIC_FALLBACK_MESSAGE
```

- [x] **Step 5：先运行测试，确认失败**

命令：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_critic_service.py::test_prompt_stage_labels_force_boundary_without_llm -q
```

预期：实现前失败，因为 F4 当时只依赖 LLM judge 自己识别 boundary。

- [x] **Step 6：实现代码侧内部提示外泄检测**

在 `app/services/critic_service.py` 中新增：

- `INTERNAL_PROMPT_LEAK_REASON = "internal_prompt_leak"`
- `PROMPT_LEAK_MARKERS`
- `BRACKETED_PROMPT_LEAK_RE`
- `_internal_prompt_leak_reason()`

并在 `_score_candidate()` 开头做 preflight 检测。命中后直接返回：

```python
CandidateScore(
    candidate_id=candidate.candidate_id,
    epitome=EpitomeScore(ER=0, IP=0, EX=0),
    casel={},
    boundary_flag=True,
    boundary_reason="internal_prompt_leak",
    weighted_total=0.0,
    rationale="internal_prompt_leak",
)
```

- [x] **Step 7：验证目标测试通过**

命令：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_generator_service.py tests\test_services\test_critic_service.py -q
```

当前结果：通过。

---

## Task 2：生成只供人工判断的 high-score 差集 review queue

**状态：已完成。**

**文件：**

- `scripts/corpus/f9_stability_diff.py`
- `tests/test_corpus/test_f9_stability_diff.py`
- `docs/corpus/f9/validation-stability/run-2/f9_high_score_diff_review_queue.csv`

- [x] **Step 1：添加脚本单元测试**

测试目标：

- 主包中 sample 1 是 ER/IP=1；
- stability run 中 sample 1 是 ER/IP=2；
- 主包和 stability run 中 sample 2 都是 ER/IP=2；
- 输出只包含 sample 1；
- 人工列必须为空。

关键断言：

```python
assert output_rows[0]["sample_no"] == "1"
assert output_rows[0]["human_er_should_be_2"] == ""
assert output_rows[0]["human_ip_should_be_2"] == ""
assert output_rows[0]["human_notes"] == ""
```

- [x] **Step 2：实现脚本**

新增 `scripts/corpus/f9_stability_diff.py`。

脚本输入：

```powershell
C:\Python313\python.exe scripts\corpus\f9_stability_diff.py `
  --main docs\corpus\f9\validation\rerun\f9_rerun_selected_scores.csv `
  --stability docs\corpus\f9\validation-stability\run-2\rerun\f9_rerun_selected_scores.csv `
  --output docs\corpus\f9\validation-stability\run-2\f9_high_score_diff_review_queue.csv
```

输出列：

```text
sample_no,
scenario, student_text,
main_candidate_id, main_orientation, main_F4_ER, main_F4_IP, main_F4_EX,
stability_candidate_id, stability_orientation, stability_F4_ER, stability_F4_IP, stability_F4_EX,
stability_rationale, stability_candidate_text,
human_er_should_be_2, human_ip_should_be_2, human_issue_type, human_notes
```

脚本不能推断 `human_*` 字段。

- [x] **Step 3：运行脚本测试**

命令：

```powershell
C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_stability_diff.py -q
```

当前结果：通过。

- [x] **Step 4：生成实际 review queue**

已生成：

```text
docs/corpus/f9/validation-stability/run-2/f9_high_score_diff_review_queue.csv
```

当前队列共 8 行：

`10, 13, 15, 19, 25, 34, 36, 38`

队列已补充 `scenario` 和 `student_text`：

- `scenario`：该样本所属情境；
- `student_text`：初中生原话，用来判断候选是否真的接住了孩子刚说的内容。

人工列仍为空。

- [x] **Step 5：修复 Excel 打开乱码问题**

Windows Excel 双击打开 CSV 时容易按本地编码猜测，纯 UTF-8 中文会乱码。脚本已改为使用 `utf-8-sig` 写出 CSV，让 Excel 能识别 UTF-8 BOM。

当前原路径文件已重新生成，验证前三字节为：

```text
EF BB BF
```

---

## Task 3：人工差集审查决策点

**状态：当前正在这里。**

**文件：**

人工需要填写：

```text
docs/corpus/f9/validation-stability/run-2/f9_high_score_diff_review_queue.csv
```

人工填写后，需要更新：

```text
docs/corpus/f9/f4-fix-execution-summary.md
```

### 当前 Task 3 要做什么

这一步不是让你重新标完整 F9，也不是让你看所有 40 条。你只需要看差集队列里的 8 条。

这 8 条的含义是：

- 在主包里，它们不是 ER/IP 双 2；
- 但在 `validation-stability/run-2` 里，它们变成了 ER/IP 双 2；
- 这些“多出来的高分”正是判断 `32/40` 阈值是否合理的关键证据。

审查时先看 `student_text`，再看 `stability_candidate_text` 和 `stability_rationale`。判断重点是：候选是否具体接住了这句初中生原话，还是只是用了模板化承接、成人化分析或强行正向重构。

人工要判断的是：

1. 这条候选在 ER 上是否真的该得 2？
2. 这条候选在 IP 上是否真的该得 2？
3. 如果不该得 2，问题类型是什么？
4. 简短写下判断理由。

### 需要人工填写的列

```text
human_er_should_be_2: yes/no
human_ip_should_be_2: yes/no
human_issue_type: good_high_score / template_low_information / adult_coaching / prompt_leak / forced_positive_reframe / other
human_notes: 简短理由
```

建议填写口径：

- `good_high_score`：这条确实具体承接、理解准确，ER/IP=2 基本合理。
- `template_low_information`：看似有承接，但主要靠万能句、兜底安抚、空泛复述或模板化收束。
- `adult_coaching`：像老师/咨询师在分析、训练、引导复盘，学生读起来有被带着反思的压力。
- `prompt_leak`：出现内部结构提示、括号式阶段标签、给老师/评审/开发者看的元话术。
- `forced_positive_reframe`：把痛苦、愤怒、自责、不信任过早改写成优点、清醒、判断力、懂事、有主见。
- `other`：不属于上面几类，但人工认为 ER/IP=2 不合理。

### agent 不能做什么

Codex 可以帮你解释列含义、整理你填完后的统计结果，但不能替你填 `human_*` 列。

### Step 1：人工审查 8 行差集队列

- [ ] **人工填写 8 行的 `human_*` 列**

### Step 2：根据人工结果判断 A/B/mixed

- [ ] **解释人工填写后的队列**

决策矩阵：

- 如果任何行是 `prompt_leak`，先保持阈值不变，继续修 prompt leak。
- 如果多行是 `adult_coaching`、`template_low_information` 或 `forced_positive_reframe`，同时 F4 给了 ER/IP=2，则倾向 A：F4 高分侧仍偏宽。
- 如果多数行是 `good_high_score`，且人工认为 ER/IP 确实应该是 2，则倾向 B：`32/40` 对修复后的 generator 分布太紧。
- 如果两类都有，则按 mixed 处理：先修具体漏判，再重跑，再讨论阈值。

最终 A/B/mixed 结论属于人工决策，必须记录进 summary。

---

## Task 4：如果结论是 A 或 mixed，继续修 F4 高分侧漏判

**状态：待 Task 3 人工结论。**

**文件：**

- `app/services/critic_service.py`
- `tests/test_services/test_critic_service.py`
- 可能涉及 `scripts/corpus/f9_validation.py`
- 可能涉及 `tests/test_corpus/test_f9_validation.py`

- [ ] **Step 1：只为人工确认的漏判类型添加测试**

不要为了压低 ER/IP 数量而写测试。只能针对人工确认的问题类型补测试。

例子：

```python
def test_f9_template_with_concrete_preface_still_caps_er_ip():
    capped = CriticService._apply_f9_score_caps({
        "ER": 2,
        "IP": 2,
        "EX": 0,
        "casel": {},
        "boundary_flag": False,
        "boundary_reason": "",
        "rationale": "具体复述后接万能兜底收束。",
        "audit_tags": ["template_low_information"],
    })
    assert capped["ER"] == 1
    assert capped["IP"] == 1
```

- [ ] **Step 2：只围绕人工确认的漏判收紧 F4 prompt/cap**

目标是提高判断正确性，不是为了让 `rerun_ER_2 <= 32` 人为过关。

- [ ] **Step 3：运行目标测试**

命令：

```powershell
C:\Python313\python.exe -m pytest tests\test_services\test_critic_service.py tests\test_corpus\test_f9_validation.py -q
```

---

## Task 5：如果结论是 B，修订阈值并记录依据

**状态：待 Task 3 人工结论。**

**文件：**

- `scripts/corpus/f9_validation.py`
- `tests/test_corpus/test_f9_validation.py`
- `docs/corpus/f9/README.md`
- `docs/corpus/f9/f4-fix-execution-summary.md`

- [ ] **Step 1：人工批准新阈值**

Codex 可以汇总证据，但新阈值数字必须由人工批准。

候选口径：

- 如果 F4 漏判占主导，保留旧阈值 `32/40`。
- 如果额外高分大多是合理好候选，可以考虑放宽到 `36/40`。
- 如果采用中间值，必须写清楚理由。

- [ ] **Step 2：更新 validation 常量和报告文案**

当前代码逻辑是：

```python
rerun_two_max = _maximum_count(rerun_total, 0.8)
```

如果人工批准新阈值，需要修改比例，并把报告文案从“避免接近满分饱和”改成新的 gate 口径说明。

- [ ] **Step 3：更新测试**

所有围绕旧 `0.8` 阈值的 PASS/FAIL 测试，都要改成新阈值语义。

---

## Task 6：正式 F9 前的三次稳定性验证

**状态：待 Task 4 或 Task 5 完成。**

**输出目录：**

- `docs/corpus/f9/validation-stability/postfix-run-1/`
- `docs/corpus/f9/validation-stability/postfix-run-2/`
- `docs/corpus/f9/validation-stability/postfix-run-3/`

- [ ] **Step 1：连续运行三次独立 validation**

命令：

```powershell
$env:PYTHONPATH='.'
$env:PYTHONIOENCODING='utf-8'
C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation-stability\postfix-run-1
C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation-stability\postfix-run-2
C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation-stability\postfix-run-3
```

- [ ] **Step 2：检查 gate 指标**

每次都必须满足当前人工批准的 gate：

- 旧坏候选通过率在阈值内。
- 旧坏候选 ER/IP 同时 2/2 在阈值内。
- sample-specific hard flags = 0。
- global quality probes 在阈值内。
- generator fallback rows = 0。
- rerun ER/IP=2 数量在批准阈值内。

- [ ] **Step 3：决定是否进入正式人工 F9**

只有三次都通过当前批准的 gate，才能把 `f9_rerun_blind_annotation.csv` 作为正式人工 F9 入口。

如果任何一次失败，不进入正式人工 F9；根据失败类型回到 Task 3 或 Task 4。

---

## Task 7：收紧 F4 ER/IP 高档门槛

**目标：** 解决 high-score 差集人工复核暴露的 ER/IP=2 边界过松问题。该任务先于新的三次 stability validation 执行。

**采纳理由：**

- 8 条差集不是同一候选文本被重复打分，因此不能直接证明 F4 对同一文本随机抖动；但它们说明 ER/IP 的 1/2 档位缺少稳定、可执行门槛。
- 人工复核中，sample 10/19 认可高分；sample 13/15/25/34/36/38 不认可高分，主要问题是候选只是在分析或复述情绪，没有让孩子感到被陪伴，或把孩子已经明说的情绪当成隐含理解。
- 该问题属于 ER/IP 高档正向定义过松，不是新的负向模式；因此不新增 audit tag，不调整 cap 逻辑，也不调整 `32/40` 阈值。

**执行内容：**

- [x] 更新 `docs/specs/f4-critic-epitome-codex-spec.md`：
  - ER=1：准确说出、分析或深化情绪，但像旁观者描述，没有"有人在陪我、在乎我"的感觉。
  - ER=2：既贴合接住情绪，又让孩子感到有人陪着他、关心他。
  - IP=1：只复述孩子已经明说的事实或情绪，例如"气死了""是不是我哪里不好"。
  - IP=2：准确点出孩子没有明说、但藏在话里的情绪或担忧。
- [x] 同步更新 `app/services/critic_service.py` 的 F4 runtime prompt。
- [x] 更新 `tests/test_services/test_critic_service.py`，断言 prompt 包含"旁观者在描述他的状态""有人在陪我、在乎我""气死了""是不是我哪里不好""孩子没有明说、但藏在话里的情绪或担忧"。
- [x] 运行本地测试：
  - `C:\Python313\python.exe -m pytest tests\test_services\test_critic_service.py -q`
  - `C:\Python313\python.exe -m pytest -q`
- [x] 本地测试通过后，执行三次 post-erip validation：
  - `docs/corpus/f9/validation-stability/post-erip-run-1/`
  - `docs/corpus/f9/validation-stability/post-erip-run-2/`
  - `docs/corpus/f9/validation-stability/post-erip-run-3/`

**验收观察：**

- `rerun_ER_2` / `rerun_IP_2` 是否稳定，不再靠单次采样运气过 gate。
- sample 10/19 是否仍能保留 ER/IP=2；如被误降，需要回调 ER/IP 定义措辞。
- 如果三次 validation 后 ER/IP=2 中心仍稳定高于 `32/40`，才重新讨论阈值是否需要修订。

**执行结果：**

- 本地测试通过：
  - `C:\Python313\python.exe -m pytest tests\test_services\test_critic_service.py -q`：23 passed
  - `C:\Python313\python.exe -m pytest -q`：102 passed
- 先在沙箱内运行三次 validation 时出现 `generator_fallback_rows=60` 与全量 `llm_failure`，诊断为沙箱网络无法连接 DeepSeek，不作为有效稳定性证据。
- 联网后以相同 prompt/temperature、`LLM_TIMEOUT=60` 覆盖重跑三次 post-erip validation，产物路径：
  - `docs/corpus/f9/validation-stability/post-erip-run-1/`
  - `docs/corpus/f9/validation-stability/post-erip-run-2/`
  - `docs/corpus/f9/validation-stability/post-erip-run-3/`

| run | decision | rerun_ER_2 | rerun_IP_2 | generated_flags | rerun_flags | generated_global | rerun_global | fallback |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| post-erip-run-1 | FAIL | 40/40 | 40/40 | 0 | 0 | 1/20 | 2/40 | 0 |
| post-erip-run-2 | FAIL | 36/40 | 37/40 | 0 | 0 | 0/20 | 2/40 | 0 |
| post-erip-run-3 | FAIL | 38/40 | 38/40 | 1 | 0 | 1/20 | 1/40 | 0 |

**结论：**

- F4 ER/IP 档位定义已收紧并进入运行时 prompt，但三次 validation 仍稳定 FAIL；当前主要阻塞仍是 rerun ER/IP=2 超过 `32/40`，不是 fallback 或 hard flags。
- 高分饱和没有被本轮定义收紧解决；run-1 甚至回到 40/40，说明仅改 prompt 档位定义不足以稳定 F4 高分侧。
- sample 19 在三次 rerun 中均保持 ER/IP=2；sample 10 在 run-1/run-3 为 2/2，在 run-2 被 `template_low_information` cap 到 1/1。由于三次候选文本不同，这不等同于同一正向候选被误杀，但说明 sample 10 不适合作为无条件稳定正向锚点，需要后续按候选文本人工复核。
- 下一步不应进入正式人工 F9；需要回到 F4 高分侧漏判/阈值口径分支。该判断已由 Task 8 修订：不再优先抽查 post-erip-run-1 的 40/40 上沿包，而是先固定 post-erip-run-2 候选复评并生成 run-2 双侧人工校准队列。

---

## Task 8：R8 固定候选复评与 F9 Gate 重新定位

**目标：** 隔离 F3 高温生成批次方差和 F4 judge 残余抖动，避免继续用完整 validation 的高分比例直接推断 F4 prompt 是否还要全局收紧。

**对 Task 7 结论的修订：**

- Task 7 的三次 `post-erip` validation 每次都会重新生成 F3 候选，因此 40/40、36/37、38/38 不能直接证明 F4 对同一候选不稳定。
- F4 代码中已经默认 `CRITIC_SAMPLE_COUNT=3` 并取中位数；R8 不是补做 median，而是诊断 median 前后的稳定性。
- 下一步不再优先抽查 `post-erip-run-1` 的 40/40 上沿包；改用 `post-erip-run-2` 作为代表性固定候选包，并同时保留 ER/IP=2 与非 2 侧。

**执行内容：**

- [x] 新增固定候选复评脚本 `scripts/corpus/f9_fixed_candidate_rescore.py`。
  - 输入：`docs/corpus/f9/validation-stability/post-erip-run-2/rerun/f9_rerun_selected_scores.csv`
  - 输出：逐轮复评分数、原始分数、是否变化、是否在 1/2 档抖动。
  - CSV 使用 `utf-8-sig`，便于 Excel 直接打开。
- [x] 新增 run-2 人工校准队列脚本 `scripts/corpus/f9_high_score_calibration_queue.py`。
  - 队列前部放 R6 已人工标注的 8 条校准样例。
  - 队列后部放 run-2 的 40 条候选，保留 ER/IP=2 与未给 2 的两侧。
  - 人工列保持空白，脚本不替人工判断“是否应得 2”。
- [x] 新增优先人工队列脚本 `scripts/corpus/f9_priority_review_queue.py`。
  - 保留 8 条 calibration。
  - 从 40 条 review 中选 10 条 priority，剩余 30 条标为 backup。
  - priority 优先包含固定复评边缘样本、非双 2 误杀检查样本、以及含风险探针的高分样本。
- [x] 新增单元测试：
  - `tests/test_corpus/test_f9_fixed_candidate_rescore.py`
  - `tests/test_corpus/test_f9_high_score_calibration_queue.py`
  - `tests/test_corpus/test_f9_priority_review_queue.py`

**执行命令：**

```powershell
C:\Python313\python.exe scripts\corpus\f9_fixed_candidate_rescore.py --input-scores docs\corpus\f9\validation-stability\post-erip-run-2\rerun\f9_rerun_selected_scores.csv --output-dir docs\corpus\f9\validation-stability\r8-fixed-rescore\count1 --critic-sample-count 1 --repeats 3

C:\Python313\python.exe scripts\corpus\f9_fixed_candidate_rescore.py --input-scores docs\corpus\f9\validation-stability\post-erip-run-2\rerun\f9_rerun_selected_scores.csv --output-dir docs\corpus\f9\validation-stability\r8-fixed-rescore\count3 --critic-sample-count 3 --repeats 3

C:\Python313\python.exe scripts\corpus\f9_high_score_calibration_queue.py --input-scores docs\corpus\f9\validation-stability\post-erip-run-2\rerun\f9_rerun_selected_scores.csv --calibration docs\corpus\f9\validation-stability\run-2\f9_high_score_diff_review_queue.csv --output docs\corpus\f9\validation-stability\post-erip-run-2\f9_high_score_calibration_queue.csv

C:\Python313\python.exe scripts\corpus\f9_priority_review_queue.py --queue docs\corpus\f9\validation-stability\post-erip-run-2\f9_high_score_calibration_queue.csv --count1-summary docs\corpus\f9\validation-stability\r8-fixed-rescore\count1\f9_fixed_candidate_rescore_summary.csv --count3-summary docs\corpus\f9\validation-stability\r8-fixed-rescore\count3\f9_fixed_candidate_rescore_summary.csv --output docs\corpus\f9\validation-stability\post-erip-run-2\f9_priority_review_queue.csv --priority-limit 10
```

**R8 判断规则：**

- 若 `count=1` 抖动明显、`count=3` 稳定：说明 median 已压住 F4 judge 抖动，R7 的完整 validation 波动主要来自 F3 高温生成批次差异。
- 若 `count=3` 固定候选仍明显抖动：先评估 `CRITIC_SAMPLE_COUNT=5` 或更强评分锚点，不进入正式人工 F9。
- 若固定候选复评稳定，但人工校准发现大量 2 分不成立：只定点修具体漏判模式，不再泛泛收紧 ER/IP 定义。
- 若固定候选复评稳定，且人工认为多数 2 分成立：`32/40` 更可能是过紧经验 gate，应讨论降级为诊断项，并重新设计正式 F9 分层抽样。

**执行前约束（已完成脚本执行，保留为决策记录）：**

- 在固定候选复评和人工队列生成前，不改 F3/F4 prompt。
- 在固定候选复评和人工队列生成前，不改 `32/40` gate。
- 在固定候选复评和人工队列生成前，不把任何 rerun 包作为正式人工 F9 入口。

**执行结果：**

- 新增脚本和测试已通过：
  - `C:\Python313\python.exe -m pytest tests\test_corpus\test_f9_fixed_candidate_rescore.py tests\test_corpus\test_f9_high_score_calibration_queue.py -q`：5 passed
  - `C:\Python313\python.exe -m pytest -q`：107 passed
- `count=1` 复评产物：
  - `docs/corpus/f9/validation-stability/r8-fixed-rescore/count1/f9_fixed_candidate_rescore_runs.csv`
  - `docs/corpus/f9/validation-stability/r8-fixed-rescore/count1/f9_fixed_candidate_rescore_summary.csv`
  - 40 条 summary、120 条 run rows、`llm_failure=0`。
  - ER 1/2 flip：1 条；IP 1/2 flip：2 条；ER unstable：0 条；IP unstable：1 条。
- `count=3` 复评产物：
  - `docs/corpus/f9/validation-stability/r8-fixed-rescore/count3/f9_fixed_candidate_rescore_runs.csv`
  - `docs/corpus/f9/validation-stability/r8-fixed-rescore/count3/f9_fixed_candidate_rescore_summary.csv`
  - 40 条 summary、120 条 run rows、`llm_failure=0`。
  - ER 1/2 flip：1 条；IP 1/2 flip：1 条；ER unstable：0 条；IP unstable：1 条。
- 人工校准队列：
  - `docs/corpus/f9/validation-stability/post-erip-run-2/f9_high_score_calibration_queue.csv`
  - 48 行：8 条 calibration + 40 条 review。
  - review 中 36 条为 `ER_IP_2`，3 条为 `ER_IP_not_2`，1 条为 `ER_not_2`。
- 优先人工队列：
  - `docs/corpus/f9/validation-stability/post-erip-run-2/f9_priority_review_queue.csv`
  - 48 行：8 条 calibration + 10 条 priority + 30 条 backup。
  - 第一轮人工只填写 10 条 `review_bucket=priority` 的 review；backup 暂不处理。

**R8 后续判断：**

- 固定候选复评没有出现网络或 fallback 失败，数据可用于下一步判断。
- `count=3` 下仍有少量边缘波动，但不支持继续做第 8 轮全局 prompt 收紧。
- 下一步必须由人工先填写优先队列中的 10 条 priority review，再决定是定点修 F4、补看 backup、调整 gate 口径，还是进入正式 F9 分层抽样设计。
- R8 第一轮人工校准完成前，仍不改 F3/F4 prompt、不改 `32/40` gate、不启动正式人工 F9。
