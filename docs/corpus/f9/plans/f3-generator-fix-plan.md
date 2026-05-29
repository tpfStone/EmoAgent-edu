# F3 F9 生成器修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 F3 生成器在 F9 validation 中暴露的品质化总结、强行正向重构、样本级事实/动机补全残留，让 F9 automatic gate 对 F3 质量有更有效的判断力。

**Architecture:** 保留现有两取向 F3 生成架构，只收紧 generator prompt 和 validation gate。F4 critic 已经通过本轮指标，不把 F3 修复扩散到 `critic_service.py`；validation 增加样本级 hard regression flags 与全局 quality probes 的分离统计，并输出 ER/IP 降分样本的人工抽查队列。

**Tech Stack:** Python 3.13, pytest, existing `GeneratorService`, existing `scripts/corpus/f9_validation.py`, DeepSeek validation run.

---

## 0. 合理性审查结论

本轮建议采纳，但按以下约束落地：

1. **采纳 B，不采纳 A/C。**
   - 不只改 prompt 禁用 `说明你`，因为容易换成 `这说明你`、`可见你` 等变体。
   - 暂不把 gate 改成 F4 `audit_tags` 驱动，因为当前 `audit_tags` 只在 rationale 中诊断性呈现，改成结构化 gate 范围偏大。
   - 采用“样本级 hard flags 保留 + 新增全局 quality probes + F3 prompt 修复”的中间方案。

2. **检测规则 gate 阈值明确分离。**
   - `detected_flags` 继续表示 sample-specific hard regression flags。
   - `global_quality_flags` 新增表示跨样本品质化总结/强行重构探针。
   - 两者不合并统计，报告和 gate 分开显示。

3. **Prompt 修改范围明确。**
   - 修改 F3 generator 侧：`app/services/generator_service.py`。
   - 同步修改 F3 spec：`docs/specs/f3-multi-orientation-generator.md`。
   - 不修改 F4 critic：`app/services/critic_service.py`，除非后续 validation 显示 F4 本身回归。

4. **矫枉过正抽查由脚本辅助输出。**
   - 脚本输出待抽查 CSV。
   - 人工只判断脚本列出的行，不从大 CSV 中手工查找，避免漏检。

---

## 1. Gate 约束

### 1.1 Sample-Specific Hard Flags

现有 `SAMPLE_PROHIBITED_PATTERNS` 保留为样本级 hard regression gate：

```python
SAMPLE_PROHIBITED_PATTERNS = {
    3: ["说明你很在乎", "先停在这儿也没关系", "先停在这也没关系"],
    11: ["唯一的空档"],
    16: ["别人可能", "省力的方法"],
    19: ["没顾上看你"],
    22: ["有主见"],
    25: ["我懂", "换个角度", "说明你"],
    27: ["坐得近", "话题没兴趣"],
    31: ["班主任觉得", "扛得住"],
    40: ["轻轻递给你一个视角", "递给你一个视角"],
}
```

阈值：

- `generated_detected_flags = 0`
- `rerun_detected_flags = 0`

解释：

- sample 11/27 这类事实补全仍然由 F3 hard regression gate 阻断生成残留。
- F4 对普通事实补全只降 ER/IP、不自动 boundary；这两套约束不冲突。

### 1.2 Global Quality Probes

新增全局探针，用于捕获跨样本反复出现的品质化总结和强行正向重构：

```python
GLOBAL_QUALITY_PROBES = [
    "说明你",  # 覆盖“这说明你”
    "可见你",
    "从这里能看出",
    "这本身说明",
    "这本身就说明",
    "这本身就是",
    "挺难得",
    "很有数",
    "很有主见",
    "判断力",
]
```

统计口径：

- 以“命中行数”作为 gate 口径，不以单行命中的 pattern 数量作为 gate 口径。
- 单行同时命中 `说明你`、`挺难得`、`很有数`，gate 只计 1 行。
- 报告中仍展示具体 flags，便于定位。

阈值：

- `generated_global_quality_flagged_rows <= 2/20`
- `rerun_global_quality_flagged_rows <= 4/40`

解释：

- 不设为 0，避免偶发自然表达让 gate 过脆。
- 设为 10% 上限，能阻断当前“品质化总结成为默认倾向”的问题。
- sample-specific hard flags 仍必须为 0；global probes 的预算不能豁免 sample 25 的 `contains:说明你` hard flag。

---

## 2. 文件改动范围

修改：

- `scripts/corpus/f9_validation.py`
  - 新增 global quality probes。
  - 将 sample-specific flags 与 global quality flags 分列输出。
  - gate 分别统计 hard flags 和 global quality flagged rows。
  - 输出 ER/IP 降分样本人工抽查队列。

- `tests/test_corpus/test_f9_validation.py`
  - 覆盖 sample-specific hard flags。
  - 覆盖 global quality probes。
  - 覆盖 hard flags 与 global flags 的 gate 分离。
  - 覆盖人工抽查队列输出。

- `app/services/generator_service.py`
  - 收紧 F3 共同 prompt。
  - 弱化“必须以具体肯定开头”的倾向，改成“具体承接优先”。
  - 禁止未充分承接前把痛苦、愤怒、自责、不信任品质化。
  - 从引导反思型允许表达中移除 `换个角度看`。

- `tests/test_services/test_generator_service.py`
  - 覆盖新的 F3 prompt guardrails。
  - 覆盖 `换个角度看` 不再作为推荐表达出现在 prompt 中。

- `docs/specs/f3-multi-orientation-generator.md`
  - 同步 F3 prompt 约束。
  - 明确品质化总结不是默认共情策略。

- `docs/corpus/f9/pointwise-diagnostics/execution-summary.md`
  - 在下一步计划中指向本计划，并修正“sample 25”表述为“sample 25 暴露的 F3 品质化总结/强行正向重构模式”。

新增：

- `docs/corpus/f9/validation/rerun/f9_low_score_review_queue.csv`
  - validation 脚本运行时生成。
  - 不手写。

---

## 3. Task 1: 先写 validation 失败测试

**Files:**
- Modify: `tests/test_corpus/test_f9_validation.py`

- [ ] **Step 1: 扩展 import**

在文件顶部 import 中加入新函数和常量：

```python
from scripts.corpus.f9_validation import (
    GENERATED_GLOBAL_QUALITY_FLAG_MAX,
    GOLDEN_SAMPLE_NOS,
    RERUN_GLOBAL_QUALITY_FLAG_MAX,
    F9_BLIND_COLUMNS,
    _score_fieldnames,
    build_report,
    detect_f3_global_quality_flags,
    detect_f3_regression_flags,
    f4_expectation_passed,
    load_cases,
    low_score_review_rows,
    make_blind_row,
)
```

- [ ] **Step 2: 更新 `_report_row` helper**

将 `_report_row` 增加 `global_flags` 参数，并写入 `global_quality_flags`：

```python
def _report_row(
    sample_no: int,
    *,
    candidate_id: str = "c1",
    er: int = 2,
    ip: int = 2,
    ex: int = 0,
    flags: str = "",
    global_flags: str = "",
    f3_pass: str = "true",
    f4_pass: str = "true",
    boundary: str = "false",
) -> dict[str, str]:
    row = {field: "" for field in _score_fieldnames()}
    row.update(
        {
            "sample_no": str(sample_no),
            "source": "test",
            "candidate_id": candidate_id,
            "detected_flags": flags,
            "global_quality_flags": global_flags,
            "f3_regression_pass": f3_pass,
            "F4_ER": str(er),
            "F4_IP": str(ip),
            "F4_EX": str(ex),
            "boundary_flag": boundary,
            "f4_expectation_pass": f4_pass,
        }
    )
    return row
```

- [ ] **Step 3: 新增 sample-specific hard flag 测试**

```python
def test_detect_f3_regression_flags_keeps_sample_specific_fact_completion_rules():
    flags = detect_f3_regression_flags(
        27,
        "他们也许只是跟坐得近的人一组，那个话题你刚好没兴趣。",
    )

    assert "contains:坐得近" in flags
    assert "contains:话题没兴趣" in flags
```

- [ ] **Step 4: 新增 global quality probes 测试**

```python
def test_detect_f3_global_quality_flags_matches_quality_reframe_patterns():
    flags = detect_f3_global_quality_flags(
        "这说明你很有数，也挺难得，能看出你有判断力。"
    )

    assert "global_contains:说明你" in flags
    assert "global_contains:挺难得" in flags
    assert "global_contains:很有数" in flags
    assert "global_contains:判断力" in flags
```

- [ ] **Step 5: 新增 gate 分离统计失败测试**

```python
def test_build_report_applies_separate_global_quality_thresholds():
    generated_rows = [
        *[
            _report_row(
                i,
                global_flags="global_contains:说明你",
                f3_pass="false",
            )
            for i in range(1, GENERATED_GLOBAL_QUALITY_FLAG_MAX + 2)
        ],
        *[
            _report_row(i)
            for i in range(GENERATED_GLOBAL_QUALITY_FLAG_MAX + 2, 21)
        ],
    ]
    old_rows = [
        _report_row(i, er=1, ip=1, f4_pass="true")
        for i in range(1, 11)
    ]
    rerun_rows = [
        *[
            _report_row(
                i,
                er=1,
                ip=1,
                global_flags="global_contains:挺难得",
                f3_pass="false",
            )
            for i in range(1, RERUN_GLOBAL_QUALITY_FLAG_MAX + 2)
        ],
        *[
            _report_row(i, er=1, ip=1)
            for i in range(RERUN_GLOBAL_QUALITY_FLAG_MAX + 2, 41)
        ],
    ]

    report = build_report(generated_rows, old_rows, rerun_rows, _manifest())

    assert "- decision: FAIL" in report
    assert (
        f"generated_global_quality_flagged_rows: "
        f"{GENERATED_GLOBAL_QUALITY_FLAG_MAX + 1}/20 "
        f"(上限: <= {GENERATED_GLOBAL_QUALITY_FLAG_MAX}/20)"
    ) in report
    assert (
        f"rerun_global_quality_flagged_rows: "
        f"{RERUN_GLOBAL_QUALITY_FLAG_MAX + 1}/40 "
        f"(上限: <= {RERUN_GLOBAL_QUALITY_FLAG_MAX}/40)"
    ) in report
```

- [ ] **Step 6: 新增 gate 预算内通过测试**

```python
def test_build_report_allows_small_global_quality_probe_budget():
    generated_rows = [
        *[
            _report_row(
                i,
                er=1,
                ip=1,
                global_flags="global_contains:说明你",
                f3_pass="false",
            )
            for i in range(1, GENERATED_GLOBAL_QUALITY_FLAG_MAX + 1)
        ],
        *[
            _report_row(i, er=1, ip=1)
            for i in range(GENERATED_GLOBAL_QUALITY_FLAG_MAX + 1, 21)
        ],
    ]
    old_rows = [
        _report_row(i, er=1, ip=1, f4_pass="true")
        for i in range(1, 11)
    ]
    rerun_rows = [
        *[
            _report_row(
                i,
                er=1,
                ip=1,
                global_flags="global_contains:挺难得",
                f3_pass="false",
            )
            for i in range(1, RERUN_GLOBAL_QUALITY_FLAG_MAX + 1)
        ],
        *[
            _report_row(i, er=1, ip=1)
            for i in range(RERUN_GLOBAL_QUALITY_FLAG_MAX + 1, 41)
        ],
    ]

    report = build_report(generated_rows, old_rows, rerun_rows, _manifest())

    assert "- decision: PASS" in report
```

- [ ] **Step 7: 新增人工抽查队列测试**

```python
def test_low_score_review_rows_lists_targeted_er_ip_drops():
    rows = [
        _report_row(16, er=2, ip=2, ex=2),
        _report_row(25, candidate_id="c2", er=1, ip=1, ex=0),
        _report_row(35, candidate_id="c1", er=2, ip=1, ex=1),
        _report_row(1, candidate_id="c1", er=1, ip=1, ex=1),
    ]

    queue = low_score_review_rows(rows)

    assert [(row["sample_no"], row["candidate_id"]) for row in queue] == [
        ("25", "c2"),
        ("35", "c1"),
    ]
```

- [ ] **Step 8: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_corpus\test_f9_validation.py -q
```

Expected:

- FAIL because `detect_f3_global_quality_flags`, `low_score_review_rows`, and new report fields are not implemented.

---

## 4. Task 2: 实现 validation probes、gate 和抽查队列

**Files:**
- Modify: `scripts/corpus/f9_validation.py`
- Test: `tests/test_corpus/test_f9_validation.py`

- [ ] **Step 1: 新增常量**

放在 `SAMPLE_PROHIBITED_PATTERNS` 后：

```python
GLOBAL_QUALITY_PROBES = [
    "说明你",
    "可见你",
    "从这里能看出",
    "这本身说明",
    "这本身就说明",
    "这本身就是",
    "挺难得",
    "很有数",
    "很有主见",
    "判断力",
]

GENERATED_GLOBAL_QUALITY_FLAG_MAX = 2
RERUN_GLOBAL_QUALITY_FLAG_MAX = 4

LOW_SCORE_REVIEW_SAMPLE_NOS = {3, 6, 14, 19, 22, 25, 27, 35, 36}
LOW_SCORE_REVIEW_COLUMNS = [
    "sample_no",
    "candidate_id",
    "orientation",
    "F4_ER",
    "F4_IP",
    "F4_EX",
    "detected_flags",
    "global_quality_flags",
    "rationale",
    "候选文本",
]
```

- [ ] **Step 2: 新增 global probe 函数**

放在 `detect_f3_regression_flags()` 后：

```python
def detect_f3_global_quality_flags(text: str) -> list[str]:
    return [
        f"global_contains:{pattern}"
        for pattern in GLOBAL_QUALITY_PROBES
        if pattern in text
    ]
```

- [ ] **Step 3: 修改 `_score_row()`**

在 `_score_row()` 中先计算两类 flags：

```python
sample_flags = detect_f3_regression_flags(case.sample_no, text)
global_flags = detect_f3_global_quality_flags(text)
```

并将返回 dict 中相关字段改为：

```python
"detected_flags": ";".join(sample_flags),
"global_quality_flags": ";".join(global_flags),
"f3_regression_pass": str(
    not sample_flags
    and not global_flags
    and text != GENERATOR_FALLBACK_TEXT
).lower(),
```

- [ ] **Step 4: 修改 `_score_fieldnames()`**

在 `"detected_flags"` 后新增字段：

```python
"global_quality_flags",
```

- [ ] **Step 5: 新增抽查队列函数**

放在 `_score_fieldnames()` 后：

```python
def low_score_review_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    review_rows: list[dict[str, str]] = []
    for row in rows:
        sample_no = int(row["sample_no"])
        if sample_no not in LOW_SCORE_REVIEW_SAMPLE_NOS:
            continue
        if str(row["F4_ER"]) == "2" and str(row["F4_IP"]) == "2":
            continue
        review_rows.append(
            {column: row.get(column, "") for column in LOW_SCORE_REVIEW_COLUMNS}
        )
    return review_rows
```

- [ ] **Step 6: 在 validation run 中写出抽查队列**

在 `rerun_scores_path` 附近新增：

```python
review_queue_path = rerun_output / "f9_low_score_review_queue.csv"
```

在写出 `rerun_scores_path` 后新增：

```python
review_queue_rows = low_score_review_rows(rerun_score_rows)
_write_csv(review_queue_path, LOW_SCORE_REVIEW_COLUMNS, review_queue_rows)
```

在 manifest 中新增：

```python
"low_score_review_queue_path": str(review_queue_path),
"low_score_review_queue_rows": len(review_queue_rows),
```

在 return dict 中新增：

```python
"low_score_review_queue": review_queue_path,
```

- [ ] **Step 7: 修改 `_gate_assessment()` 参数和逻辑**

函数签名增加：

```python
generated_global_quality_flags: list[dict[str, str]],
rerun_global_quality_flags: list[dict[str, str]],
```

在 blocking reasons 中保留 hard flags 的 0 阈值，并新增 global 阈值：

```python
if len(generated_global_quality_flags) > GENERATED_GLOBAL_QUALITY_FLAG_MAX:
    blocking_reasons.append(
        "F3 golden 全局品质化总结探针命中 "
        f"{len(generated_global_quality_flags)}/{len(generated_rows)}，"
        f"高于 {GENERATED_GLOBAL_QUALITY_FLAG_MAX}/{len(generated_rows)} 上限。"
    )
if len(rerun_global_quality_flags) > RERUN_GLOBAL_QUALITY_FLAG_MAX:
    blocking_reasons.append(
        "重跑样本全局品质化总结探针命中 "
        f"{len(rerun_global_quality_flags)}/{len(rerun_rows)}，"
        f"高于 {RERUN_GLOBAL_QUALITY_FLAG_MAX}/{len(rerun_rows)} 上限。"
    )
```

在 return dict 中新增：

```python
"generated_global_quality_flag_count": len(generated_global_quality_flags),
"generated_global_quality_flag_max": GENERATED_GLOBAL_QUALITY_FLAG_MAX,
"rerun_global_quality_flag_count": len(rerun_global_quality_flags),
"rerun_global_quality_flag_max": RERUN_GLOBAL_QUALITY_FLAG_MAX,
```

- [ ] **Step 8: 修改 `build_report()`**

新增两类 rows：

```python
generated_global_quality_flags = [
    row for row in generated_rows if row["global_quality_flags"]
]
rerun_global_quality_flags = [
    row for row in rerun_rows if row["global_quality_flags"]
]
review_queue = low_score_review_rows(rerun_rows)
```

调用 `_gate_assessment()` 时传入新增参数。

在 Gate Decision 中新增：

```python
f"- generated_global_quality_flagged_rows: "
f"{gate['generated_global_quality_flag_count']}/{len(generated_rows)} "
f"(上限: <= {gate['generated_global_quality_flag_max']}/{len(generated_rows)})",
f"- rerun_global_quality_flagged_rows: "
f"{gate['rerun_global_quality_flag_count']}/{gate['rerun_total']} "
f"(上限: <= {gate['rerun_global_quality_flag_max']}/{gate['rerun_total']})",
```

在 Automatic Gate Criteria 中新增：

```python
"- F3 全局品质化总结探针在 golden generated rows 中最多 2/20，在 rerun selected rows 中最多 4/40。",
"- 样本级 hard regression flags 与全局 quality probes 分开统计；hard flags 必须为 0。",
```

在 F9 Rerun Package 中新增：

```python
f"- low_score_review_queue_path: `{manifest['low_score_review_queue_path']}`",
f"- low_score_review_queue_rows: {len(review_queue)}",
```

新增报告章节：

```python
if generated_global_quality_flags:
    lines.extend([
        "",
        "## Generated Global Quality Flagged Rows",
        "",
        "| sample_no | candidate_id | flags |",
        "|---:|---|---|",
    ])
    for row in generated_global_quality_flags:
        lines.append(
            f"| {row['sample_no']} | {row['candidate_id']} | {row['global_quality_flags']} |"
        )
if rerun_global_quality_flags:
    lines.extend([
        "",
        "## Rerun Global Quality Flagged Rows",
        "",
        "| sample_no | candidate_id | flags |",
        "|---:|---|---|",
    ])
    for row in rerun_global_quality_flags:
        lines.append(
            f"| {row['sample_no']} | {row['candidate_id']} | {row['global_quality_flags']} |"
        )
if review_queue:
    lines.extend([
        "",
        "## Manual Low-Score Review Queue",
        "",
        "| sample_no | candidate_id | F4_ER | F4_IP | F4_EX |",
        "|---:|---|---:|---:|---:|",
    ])
    for row in review_queue:
        lines.append(
            f"| {row['sample_no']} | {row['candidate_id']} | {row['F4_ER']} | {row['F4_IP']} | {row['F4_EX']} |"
        )
```

- [ ] **Step 9: 运行 validation 单测**

Run:

```powershell
python -m pytest tests\test_corpus\test_f9_validation.py -q
```

Expected:

- PASS.

---

## 5. Task 3: 先写 F3 prompt 失败测试

**Files:**
- Modify: `tests/test_services/test_generator_service.py`

- [ ] **Step 1: 增强 `test_generator_prompt_contains_f9_reliability_guardrails`**

在已有断言后增加：

```python
assert "不要用“说明你”“可见你”“这本身”把孩子的痛苦总结成品质、能力或优点" in empathic_prompt
assert "肯定只能落在孩子明确说出的动作、感受或表达本身" in empathic_prompt
assert "不要把抱怨、愤怒、自责、沉默、反复确认改写成判断力、懂事、很有数或有主见" in reflective_prompt
assert "换个角度看" not in reflective_prompt
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_services\test_generator_service.py -q
```

Expected:

- FAIL because current prompt still lacks the exact strengthened guardrails and still includes `换个角度看`.

---

## 6. Task 4: 实现 F3 prompt 修复

**Files:**
- Modify: `app/services/generator_service.py`
- Modify: `docs/specs/f3-multi-orientation-generator.md`
- Test: `tests/test_services/test_generator_service.py`

- [ ] **Step 1: 修改 `COMMON_PROMPT` 中原则 2**

把当前原则 2：

```text
2. 多用真诚、具体的肯定。可以用温和、具体的肯定开头，让孩子先觉得自己身上有被看见的闪光点；不要把"哇"或"其实你"作为默认开头，只有语境特别自然时才偶尔使用，更多时候直接从孩子说的具体内容切入。
```

改为：

```text
2. 优先具体承接孩子说出的场景和感受，不强求以夸奖开头。可以轻轻肯定孩子愿意说出来、把事情讲清楚、能觉察到自己的感受；不要把"哇"、"其实你"或品质化夸奖作为默认开头，更多时候直接从孩子说的具体内容切入。
```

- [ ] **Step 2: 替换 `F9_RELIABILITY_GUARDRAILS`**

将整个常量替换为：

```python
F9_RELIABILITY_GUARDRAILS = """【F9 信度修订后的额外约束】
- 先承接，再理解；不要用“说明你”“可见你”“这本身”把孩子的痛苦总结成品质、能力或优点。
- 未充分承接情绪前，不要把痛苦、自责、愤怒、不信任、沉默或反复确认改写成判断力、懂事、很有数、有主见或在乎别人。
- 肯定只能落在孩子明确说出的动作、感受或表达本身，例如“你把这件事说得很具体”“你把那股不公平感讲出来了”；不要替孩子下人格结论。
- 轻量稳定感可以使用，但前面必须已经具体回应当前倾诉；不要用“说明你很在乎”“你已经很不容易”“先缓一缓也没关系”替代真正回应。
- 可以使用具体、低压、学生能直接回答的二选一问题，例如“是更气那句话，还是更难受他没站你这边”；但二选一问题的前提不能替第三方解释动机，也不能替学生下人格或关系结论。
- 涉及朋友、同学、家长、老师时，只说孩子感受到的影响和可控边界，不替对方找理由，不把冲动断关系、报复、羞辱包装成“有主见”。
"""
```

- [ ] **Step 3: 修改共情型取向开头规则**

把共情型第一条：

```text
- 以一句具体的肯定开头，夸到他话里那个具体的点上，不要空夸；开头要按语境自然变化，不要把"哇"或"其实你"作为默认开头。
```

改为：

```text
- 以一句具体承接开头，先接住他话里最具体的情绪、场景或不公平感；可以轻轻肯定“愿意说出来”或“把事情讲清楚”，但不要开头就评价他的品质、能力或人格。
```

- [ ] **Step 4: 修改引导反思型取向开头和新视角规则**

把引导反思型相关两条：

```text
- 同样以一句具体肯定开头，但接情绪只用一句话带过，不要展开。
- 重心放在自然地给孩子打开一个新角度：不要固定使用任何引导套话，尤其不要反复使用"我想轻轻递给你一个想法"。可以根据语境选择更自然的承接方式，例如直接补出一个可能性、轻轻转折、把两种感受并列，或用"也许""有时候""换个角度看""我注意到"这类低压力表达。重点是让孩子感觉视角被轻轻打开，而不是听到一段固定话术。
```

改为：

```text
- 同样以一句具体承接开头，但接情绪只用一句话带过，不要展开，也不要先把孩子夸成懂事、有判断力、很有数或有主见。
- 重心放在自然地给孩子打开一个新角度：不要固定使用任何引导套话，尤其不要反复使用"我想轻轻递给你一个想法"、"换个角度看"、"不过你有没有注意到"。可以根据语境选择更自然的承接方式，例如把两种感受并列、回到孩子的需要或可控边界，或用一个低压力二选一问题。重点是让孩子感觉视角被轻轻打开，而不是听到一段固定话术。
```

- [ ] **Step 5: 同步 F3 spec**

在 `docs/specs/f3-multi-orientation-generator.md` 中同步以上三处文字：

- 共同约束原则 2。
- F9 信度约束。
- 两个取向的开头和引导规则。

- [ ] **Step 6: 运行 generator 单测**

Run:

```powershell
python -m pytest tests\test_services\test_generator_service.py -q
```

Expected:

- PASS.

---

## 7. Task 5: 更新执行总结文档

**Files:**
- Modify: `docs/corpus/f9/pointwise-diagnostics/execution-summary.md`

- [ ] **Step 1: 修正下一步计划**

将当前“修复 F3 sample 25 generation 残留”改为：

```markdown
1. 按 `docs/corpus/f9/plans/f3-generator-fix-plan.md` 修复 F3 生成器问题。范围不是只替换 sample 25 的 `说明你` 字符串，而是修复 sample 25 暴露出的品质化总结、强行正向重构和固定转折模板。
2. 扩展 F9 validation：
   - sample-specific hard flags 继续要求 generated/rerun 均为 0。
   - global quality probes 单独统计，generated 上限 2/20，rerun 上限 4/40。
   - 输出 `f9_low_score_review_queue.csv`，作为正式人工 F9 前的抽查清单。
```

- [ ] **Step 2: 校验文档关键字**

Run:

```powershell
rg -n "f3-generator-fix-plan|global quality|f9_low_score_review_queue|2/20|4/40|sample 25" docs\corpus\f9\pointwise-diagnostics\execution-summary.md
```

Expected:

- 输出包含上述关键约束。

---

## 8. Task 6: 运行本地测试

**Files:**
- No edits.

- [ ] **Step 1: 运行 validation 单测**

Run:

```powershell
python -m pytest tests\test_corpus\test_f9_validation.py -q
```

Expected:

- PASS.

- [ ] **Step 2: 运行 generator 单测**

Run:

```powershell
python -m pytest tests\test_services\test_generator_service.py -q
```

Expected:

- PASS.

- [ ] **Step 3: 运行全量测试**

Run:

```powershell
python -m pytest -q
```

Expected:

- PASS.

---

## 9. Task 7: 重跑 F9 validation

**Files:**
- Generated:
  - `docs/corpus/f9/validation/f9_validation_report.md`
  - `docs/corpus/f9/validation/golden/f9_golden_generated_scores.csv`
  - `docs/corpus/f9/validation/rerun/f9_rerun_selected_scores.csv`
  - `docs/corpus/f9/validation/rerun/f9_low_score_review_queue.csv`
  - `docs/corpus/f9/validation/rerun/f9_rerun_manifest.json`

- [ ] **Step 1: 运行真实 validation**

Run:

```powershell
$env:PYTHONPATH='.'
$env:PYTHONIOENCODING='utf-8'
C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation
```

Expected:

- DeepSeek 可用时生成新 validation artifacts。
- 如果普通 sandbox 出现 `Connection error`，需要用授权网络重跑同一命令。

- [ ] **Step 2: 查看 gate decision**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
C:\Python313\python.exe -c "from pathlib import Path; text=Path('docs/corpus/f9/validation/f9_validation_report.md').read_text(encoding='utf-8'); start=text.index('## Gate Decision'); end=text.index('## Automatic Gate Criteria'); print(text[start:end])"
```

Expected gate:

- `generated_detected_flags: 0`
- `rerun_detected_flags: 0`
- `generated_global_quality_flagged_rows <= 2/20`
- `rerun_global_quality_flagged_rows <= 4/40`
- `generator_fallback_rows: 0`
- 旧坏候选 F4 指标仍在 F4 plan 的通过阈值内。

- [ ] **Step 3: 如果 gate 失败，按原因回退**

失败处理：

- 如果 `generated_detected_flags` 或 `rerun_detected_flags` 非 0，优先修 F3 prompt，不改 F4。
- 如果 global quality probes 超阈值，抽查命中行文本，继续收紧 F3 prompt 的“品质化总结/强行重构”规则。
- 如果旧坏候选 F4 指标回归，回到 F4 plan 检查 critic prompt/cap，不在 F3 plan 中混改。

---

## 10. Task 8: 人工 F9 前置抽查

**Files:**
- Read: `docs/corpus/f9/validation/rerun/f9_low_score_review_queue.csv`
- Read: `docs/corpus/f9/validation/rerun/f9_rerun_selected_scores.csv`
- Optional Create: `docs/corpus/f9/validation/rerun/f9_low_score_manual_review.md`

- [ ] **Step 1: 查看脚本输出的抽查队列**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
C:\Python313\python.exe -c "import csv; rows=list(csv.DictReader(open('docs/corpus/f9/validation/rerun/f9_low_score_review_queue.csv', encoding='utf-8-sig'))); [print(r['sample_no'], r['candidate_id'], r['F4_ER'], r['F4_IP'], r['F4_EX'], r['global_quality_flags']) for r in rows]"
```

Expected:

- 输出待人工判断的 ER/IP 降分行。
- sample 16 不应进入队列；它是低压二选一正向对照。

- [ ] **Step 2: 人工判断队列行**

人工逐行判断：

- 该行 ER/IP 被压到 1 是否合理。
- 是否因为 `template_low_information`、`forced_positive_reframe`、`unsupported_fact_completion`、`third_party_excuse` 等已知 F9 风险而降分。
- 是否存在“本应 ER=2/IP=2，但被 prompt 或 cap 误伤”的情况。

- [ ] **Step 3: 记录人工结论**

如果创建人工结论文档，使用以下格式：

```markdown
# F9 Low-Score Manual Review

## Review Scope

- Source: `docs/corpus/f9/validation/rerun/f9_low_score_review_queue.csv`
- Purpose: 检查 F4 修复后是否存在 ER/IP 矫枉过正。

## Rows

| sample_no | candidate_id | F4_ER | F4_IP | 判断 | 原因 |
|---:|---|---:|---:|---|---|
| 25 | c2 | 1 | 1 | 合理 | 强行把考试愤怒重构成“心里有数”。 |
```

验收：

- 若人工抽查未发现明显误伤，可进入正式人工 F9。
- 若发现明显误伤，先回到 F4 cap/prompt 规则，不直接放宽 F3 generator。

---

## 11. Final Acceptance

本计划完成的验收条件：

- `python -m pytest tests\test_corpus\test_f9_validation.py -q` 通过。
- `python -m pytest tests\test_services\test_generator_service.py -q` 通过。
- `python -m pytest -q` 通过。
- F9 validation report 中：
  - `generated_detected_flags: 0`
  - `rerun_detected_flags: 0`
  - `generated_global_quality_flagged_rows <= 2/20`
  - `rerun_global_quality_flagged_rows <= 4/40`
  - `generator_fallback_rows: 0`
- `docs/corpus/f9/validation/rerun/f9_low_score_review_queue.csv` 已生成。
- 正式人工 F9 启动前，已人工抽查 low-score review queue。
