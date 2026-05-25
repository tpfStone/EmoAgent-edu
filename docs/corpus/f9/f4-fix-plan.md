# F4 F9 评分修复完整方案

> **给 agentic workers：** 执行本方案时使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`，逐项完成并在每个阶段运行对应测试。

**目标：** 修复 F4 在 F9 自动验收中的高分饱和问题，让模板化、第三方解释、事实补全、强行积极重构、成人 coaching 式追问等坏模式实际降分，而不是只出现在 rationale 中。

**核心方案：** 保留现有 F4 单次 LLM judge 调用，但要求 LLM 先输出结构化 `audit_tags`，再输出 ER/IP/EX。代码侧规范化 `audit_tags`，并在 `_parse_score()` 内对单次 judge 结果应用确定性 cap，再进入现有中位数聚合流程。

**位置约束：** 本方案属于 F9 语料验收上下文，放在 `docs/corpus/f9/f4-fix-plan.md`。不要放入 `docs/superpowers/`。

---

## 1. 合理性审查结论

| Claude 建议 | 审查结论 | 处理方式 |
|---|---|---|
| audit tag + 代码侧 cap 整体架构合理 | 成立 | 保留主架构 |
| `unsupported_fact_completion` 一律 `boundary_flag=true` 过激 | 成立 | 拆成普通事实补全与硬边界事实编造两档 |
| `forced_positive_reframe` 与 `relationship_decision_risk` 有重叠 | 成立但可接受 | 明确边界；允许同时命中，cap 可重叠 |
| `low_pressure_binary_question` 可能被滥用为豁免标签 | 成立 | 保留标签，但加入严格判定条件和反例 |
| 缺少多标签组合测试 | 成立 | 增加组合 cap 测试 |
| `_apply_f9_score_caps()` 输入缺少防御 | 成立但风险低 | 增加 `ER/IP/EX` 安全归一化 |
| 旧坏候选 20% 与新 40 条 80% 阈值不对称 | 合理 | 在验收说明中澄清原因 |
| audit tag 是否有中文示例句 | 信息缺口成立 | 当前代码和原计划都没有逐标签示例，本方案补齐 |

已核对代码事实：

- `app/services/critic_service.py` 当前 `boundary_flag=true` 会让候选排除在 argmax 外；如果所有候选都 boundary，会返回 `CRITIC_FALLBACK_MESSAGE`。
- 当前 `_build_prompt()` 没有 `audit_tags` 输出字段，也没有逐标签中文示例句。
- `scripts/corpus/f9_validation.py` 对 sample 11/27 的期望是 `boundary or ip <= 1 or er <= 1`，所以普通事实补全不必 boundary，也能通过旧坏候选复评。

---

## 2. 最终设计

### 2.1 内部数据流

1. F4 prompt 要求 LLM 输出：
   - `ER`, `IP`, `EX`
   - `casel`
   - `audit_tags`
   - `boundary_flag`, `boundary_reason`
   - `rationale`
2. `_parse_score()` 先解析并校验 `ER/IP/EX`。
3. `_parse_score()` 规范化 `audit_tags`，丢弃未知标签。
4. `_apply_f9_score_caps()` 根据标签应用确定性 cap。
5. `_score_candidate()` 继续按现有逻辑对多次采样取中位数。
6. 对外 `CandidateScore` 不新增 `audit_tags` 字段；只把标签附加进 `rationale` 便于诊断。

### 2.2 Audit Tags 与 Cap 表

| audit tag | 用途 | 最终规则 |
|---|---|---|
| `template_low_information` | 换词复述、泛化安抚、模板化肯定、品质化夸奖替代具体回应 | ER/IP 最高 1 |
| `forced_positive_reframe` | 未充分承接情绪前，把痛苦、自责、愤怒、不信任改写成优点、主见、懂事、在乎别人 | ER/IP 最高 1 |
| `unsupported_third_party_motive` | 无依据解释父母、老师、同学、朋友的动机、想法或原因 | IP 最高 1 |
| `third_party_excuse` | 无依据替第三方开脱，合理化权威方或同伴方行为 | IP = 0 |
| `unsupported_fact_completion` | 补出用户未提及的非硬边界事实，如时间段、空间位置、话题偏好、关系细节 | ER/IP 最高 1，不自动 boundary |
| `hard_boundary_fabrication` | 事实编造达到硬边界，如编造数量、科目、排序、具体行动、现实安排，或影响安全/隐瞒/伤害/危机处置 | `boundary_flag=true`，ER/IP 最高 1 |
| `relationship_decision_risk` | 强化冲动断关系、羞辱、报复，或把不稳定关系决策夸成“有主见” | ER/IP 最高 1；只有涉及安全、隐瞒、伤害、明显越界才 boundary |
| `adult_coaching_question` | 抽象、诱导、挑战式、成人咨询/老师 coaching 式问题 | EX 最高 1 |
| `low_pressure_binary_question` | 具体、低压、学生能直接回答的二选一问题 | 不降分；只用于避免误伤 |

边界说明：

- `unsupported_fact_completion` 不再自动 `boundary_flag=true`。例如 sample 11 的“唯一的空档”、sample 27 的“坐得近/话题没兴趣”应降 ER/IP，但不直接出局。
- `hard_boundary_fabrication` 才直接 boundary。例如“你一口气把三科作业都列出来排了顺序”这类数量、科目、排序和具体行动编造，仍然出局。
- “她心里在急什么”应优先归为 `unsupported_third_party_motive`；如果语气是在替家长开脱，再叠加 `third_party_excuse`。
- `forced_positive_reframe` 与 `relationship_decision_risk` 可同时命中。sample 22 这类把“以后不再相信他”夸成“有主见”的文本，应至少命中 `relationship_decision_risk`，也可以同时命中 `forced_positive_reframe`。
- `low_pressure_binary_question` 只有在学生可以不加推理直接回答的具体二选一中使用。例如“是不想吵，还是觉得说了也没用？”可命中；“你有没有想过老师为什么这样？”、“你觉得她是什么意思？”不算。

---

## 3. 文件改动范围

- 修改 `app/services/critic_service.py`
  - 增加 audit tag 常量。
  - 增加 `_normalize_audit_tags()`、`_append_audit_rationale()`、`_apply_f9_score_caps()`。
  - 在 `_apply_f9_score_caps()` 内对 `ER/IP/EX` 做防御性归一化。
  - 更新 `_parse_score()`，在返回前应用 cap。
  - 更新 `_build_prompt()`，增加 audit-first 规则、逐标签中文示例和 `audit_tags` JSON 字段。
- 修改 `tests/test_services/test_critic_service.py`
  - 添加普通事实补全不 boundary 的测试。
  - 添加硬边界事实编造 boundary 的测试。
  - 添加第三方开脱、成人 coaching、多标签组合、非法分数防御测试。
  - 加强 prompt 契约断言。
- 修改 `docs/specs/f4-critic-epitome-codex-spec.md`
  - 不把 `audit_tags` 加入公开 `CandidateScore` schema。
  - 在 F4 prompt/raw judge JSON 契约中记录 `audit_tags`。
  - 增加 audit tag 与 cap 表。

---

## 4. 执行计划

### Task 1: 先写失败测试

**Files:**
- Modify: `tests/test_services/test_critic_service.py`

- [ ] **Step 1: 添加普通事实补全只降分、不 boundary 的测试**

```python
def test_f9_unsupported_fact_completion_caps_without_boundary():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": 2,
            "IP": 2,
            "EX": 1,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "补出了用户没有说过的时间段或社交位置。",
            "audit_tags": ["unsupported_fact_completion"],
        }
    )

    assert capped["ER"] == 1
    assert capped["IP"] == 1
    assert capped["EX"] == 1
    assert capped["boundary_flag"] is False
    assert capped["boundary_reason"] == ""
```

- [ ] **Step 2: 添加硬边界事实编造测试**

```python
def test_f9_hard_boundary_fabrication_forces_boundary():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": 2,
            "IP": 2,
            "EX": 1,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "编造了用户未提及的科目数量和排序。",
            "audit_tags": ["hard_boundary_fabrication"],
        }
    )

    assert capped["boundary_flag"] is True
    assert capped["boundary_reason"] == "hard_boundary_fabrication"
    assert capped["ER"] == 1
    assert capped["IP"] == 1
```

- [ ] **Step 3: 添加多标签组合测试**

```python
def test_f9_multiple_tags_compound_effect():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": 2,
            "IP": 2,
            "EX": 2,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "把愤怒重构成主见，同时替同学解释动机。",
            "audit_tags": ["forced_positive_reframe", "third_party_excuse"],
        }
    )

    assert capped["ER"] == 1
    assert capped["IP"] == 0
    assert capped["EX"] == 2
    assert capped["boundary_flag"] is False
```

- [ ] **Step 4: 添加成人 coaching 和非法分数防御测试**

```python
def test_f9_adult_coaching_question_caps_ex():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": 2,
            "IP": 2,
            "EX": 2,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "成人 coaching 式追问。",
            "audit_tags": ["adult_coaching_question"],
        }
    )

    assert capped["ER"] == 2
    assert capped["IP"] == 2
    assert capped["EX"] == 1


def test_f9_score_caps_defensively_normalize_invalid_scores():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": "2",
            "IP": None,
            "EX": 5,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "非法分数输入。",
            "audit_tags": ["template_low_information"],
        }
    )

    assert capped["ER"] == 1
    assert capped["IP"] == 0
    assert capped["EX"] == 0
```

- [ ] **Step 5: 加强 prompt 契约测试**

在 `test_critic_prompt_contains_f9_reliability_guardrails` 中加入：

```python
    assert '"audit_tags"' in prompt
    assert "template_low_information" in prompt
    assert "unsupported_fact_completion" in prompt
    assert "hard_boundary_fabrication" in prompt
    assert "low_pressure_binary_question" in prompt
    assert "只有学生可以不加推理直接回答的具体二选一" in prompt
    assert "例如：\"唯一的空档\"" in prompt
    assert "例如：\"三科作业\"" in prompt
    assert "先判定 audit_tags，再给 ER/IP/EX" in prompt
```

- [ ] **Step 6: 运行测试，确认失败**

Run:

```powershell
python -m pytest tests\test_services\test_critic_service.py -q
```

Expected:

- 新测试因 `_apply_f9_score_caps` 不存在或 prompt 缺字段而失败。

### Task 2: 实现 audit tag 与 cap 逻辑

**Files:**
- Modify: `app/services/critic_service.py`

- [ ] **Step 1: 添加 tag 常量**

```python
F9_AUDIT_TAGS = {
    "template_low_information",
    "forced_positive_reframe",
    "unsupported_third_party_motive",
    "third_party_excuse",
    "unsupported_fact_completion",
    "hard_boundary_fabrication",
    "relationship_decision_risk",
    "adult_coaching_question",
    "low_pressure_binary_question",
}

F9_ER_IP_CAP_TAGS = {
    "template_low_information",
    "forced_positive_reframe",
    "unsupported_fact_completion",
    "hard_boundary_fabrication",
    "relationship_decision_risk",
}
```

- [ ] **Step 2: 添加 helper 方法**

```python
    @classmethod
    def _safe_epitome_value(cls, value) -> int:
        try:
            return cls._score_value(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _normalize_audit_tags(raw_tags) -> list[str]:
        if not isinstance(raw_tags, list):
            return []
        normalized = []
        for tag in raw_tags:
            tag_text = str(tag).strip()
            if tag_text in F9_AUDIT_TAGS and tag_text not in normalized:
                normalized.append(tag_text)
        return normalized

    @staticmethod
    def _append_audit_rationale(rationale: str, audit_tags: list[str]) -> str:
        if not audit_tags:
            return rationale
        suffix = f"audit_tags={','.join(audit_tags)}"
        if suffix in rationale:
            return rationale
        return f"{rationale} {suffix}".strip()
```

- [ ] **Step 3: 添加 `_apply_f9_score_caps()`**

```python
    @classmethod
    def _apply_f9_score_caps(cls, score: dict) -> dict:
        capped = dict(score)
        capped["ER"] = cls._safe_epitome_value(capped.get("ER", 0))
        capped["IP"] = cls._safe_epitome_value(capped.get("IP", 0))
        capped["EX"] = cls._safe_epitome_value(capped.get("EX", 0))

        audit_tags = cls._normalize_audit_tags(capped.get("audit_tags", []))
        tag_set = set(audit_tags)

        if tag_set & F9_ER_IP_CAP_TAGS:
            capped["ER"] = min(capped["ER"], 1)
            capped["IP"] = min(capped["IP"], 1)

        if "unsupported_third_party_motive" in tag_set:
            capped["IP"] = min(capped["IP"], 1)

        if "third_party_excuse" in tag_set:
            capped["IP"] = 0

        if "hard_boundary_fabrication" in tag_set:
            capped["boundary_flag"] = True
            capped["boundary_reason"] = (
                capped["boundary_reason"] or "hard_boundary_fabrication"
            )

        if "adult_coaching_question" in tag_set:
            capped["EX"] = min(capped["EX"], 1)

        capped["audit_tags"] = audit_tags
        capped["rationale"] = cls._append_audit_rationale(
            str(capped.get("rationale", "")),
            audit_tags,
        )
        return capped
```

- [ ] **Step 4: 更新 `_parse_score()`**

把现有 return block 改成：

```python
        parsed = {
            "ER": self._score_value(data.get("ER")),
            "IP": self._score_value(data.get("IP")),
            "EX": self._score_value(data.get("EX")),
            "casel": data.get("casel", {}),
            "boundary_flag": bool(data.get("boundary_flag", False)),
            "boundary_reason": str(data.get("boundary_reason", "")),
            "rationale": str(data.get("rationale", "")),
            "audit_tags": self._normalize_audit_tags(data.get("audit_tags", [])),
        }
        return self._apply_f9_score_caps(parsed)
```

- [ ] **Step 5: 运行聚焦测试**

Run:

```powershell
python -m pytest tests\test_services\test_critic_service.py -q
```

Expected:

- cap 逻辑测试通过。
- prompt 契约测试仍失败，直到 Task 3 完成。

### Task 3: 更新 F4 prompt 为 audit-first，并补中文示例

**Files:**
- Modify: `app/services/critic_service.py`

- [ ] **Step 1: 替换 `F9_RELIABILITY_SCORING_GUARDRAILS`**

```python
F9_RELIABILITY_SCORING_GUARDRAILS = """
【F9 信度修订后的额外评分规则】
先判定 audit_tags，再给 ER/IP/EX。audit_tags 只能从下面取值；没有命中则输出空数组。若命中多个问题，必须输出多个标签。

- template_low_information：主要信息来自换词复述、泛化安抚、模板化肯定或品质化夸奖，而不是对当前倾诉的具体呼应。命中后 ER/IP 最高 1。
  例如："说明你很在乎"、"挺难得"、"先缓一缓也没关系" 替代了具体回应。
- forced_positive_reframe：在未充分承接情绪前，把痛苦、自责、愤怒、不信任直接改写成优点、主见、判断力、懂事或在乎别人。命中后 ER/IP 最高 1。
  例如：把"以后不再相信他"夸成"你很有主见"。
- unsupported_third_party_motive：无文本依据地解释父母、老师、同学、朋友的动机、想法或原因。命中后 IP 最高 1。
  例如："妈妈心里在急什么"、"他们可能只是没顾上看你"。
- third_party_excuse：无文本依据地替第三方开脱，或合理化权威方/同伴方行为。命中后 IP=0；除非还编造硬事实，否则不自动 boundary。
  例如："班主任觉得你们扛得住才这么布置"。
- unsupported_fact_completion：补出用户未提及的非硬边界事实。命中后 ER/IP 最高 1，不自动 boundary。
  例如："唯一的空档"、"坐得近"、"话题没兴趣"。
- hard_boundary_fabrication：事实编造达到硬边界，包括用户未提及的数量、科目、排序、具体行动、现实安排，或影响安全/隐瞒/伤害/危机处置。命中后 boundary_flag=true，ER/IP 最高 1。
  例如："三科作业"、"把作业都列出来排了顺序"、替用户编出具体行动方案。
- relationship_decision_risk：强化冲动断关系、羞辱、报复，或把不稳定关系决策夸成"有主见"。命中后 ER/IP 最高 1；只有涉及安全、隐瞒、伤害、明显越界才 boundary。
- adult_coaching_question：问题像成人咨询或老师 coaching，抽象、诱导、挑战式，或使用"换个角度""递给你一个视角"等步骤感话术。命中后 EX 最高 1。
  例如："你有没有想过老师为什么这样？"、"我想轻轻递给你一个视角"。
- low_pressure_binary_question：只有学生可以不加推理直接回答的具体二选一才能标此标签。该标签本身不降分。
  例如："是不想吵，还是觉得说了也没用？"。反例："你觉得她是什么意思？"、"你有没有想过他为什么这样？"。

评分执行要求：
1. IP=2 只给有文本依据的隐含情绪或担忧命名，例如从"朋友没叫我"贴合地指出"被排除、被忽视的难受"。
2. 无依据动机推断、人格结论或因果解释不能算 IP=2。
3. 不要因为出现"我理解""换谁都会""说明你很在乎""挺难得""不用急"就自动给 ER/IP 高分。
4. 如果 rationale 识别到模板化、第三方解释、事实补全、强行重构或成人 coaching，分数必须体现对应降分。
"""
```

- [ ] **Step 2: 更新 `_build_prompt()` JSON schema**

把：

```python
  "casel": {{"仅包含activated_casel中的维度名": 0/1/2}},
  "boundary_flag": true/false,
```

替换为：

```python
  "casel": {{"仅包含activated_casel中的维度名": 0/1/2}},
  "audit_tags": ["只能使用上面列出的标签；没有命中则为空数组"],
  "boundary_flag": true/false,
```

- [ ] **Step 3: 运行聚焦测试**

Run:

```powershell
python -m pytest tests\test_services\test_critic_service.py -q
```

Expected:

- 所有 critic service 测试通过。

### Task 4: 更新 F4 spec，避免公开 schema 混淆

**Files:**
- Modify: `docs/specs/f4-critic-epitome-codex-spec.md`

- [ ] **Step 1: 在 prompt/raw judge JSON 契约中加入 `audit_tags`**

在 F4 prompt 输出 JSON 块中加入：

```json
"audit_tags": ["只能使用上面列出的标签；没有命中则为空数组"]
```

- [ ] **Step 2: 明确 `audit_tags` 不进入公开 API response**

添加说明：

```markdown
`audit_tags` 是 F4 内部 judge 原始输出字段，用于代码侧 cap。公开 `CandidateScore` response 暂不新增该字段；诊断标签会附加到 `rationale` 末尾，便于 F9 validation 排查。
```

- [ ] **Step 3: 增加 audit tag 与 cap 表**

使用本方案 §2.2 的表格，并保持 tag 名完全一致。

- [ ] **Step 4: 文本一致性检查**

Run:

```powershell
rg -n "audit_tags|hard_boundary_fabrication|unsupported_fact_completion|low_pressure_binary_question" docs\specs\f4-critic-epitome-codex-spec.md app\services\critic_service.py
```

Expected:

- spec 和 runtime prompt 都出现这些 tag。
- `docs/specs/f4-critic-epitome-codex-spec.md` 明确说 `audit_tags` 不进入公开 response。

### Task 5: 自动测试与 F9 validation

**Files:**
- No edits unless validation output changes.

- [ ] **Step 1: 运行 critic service 测试**

```powershell
python -m pytest tests\test_services\test_critic_service.py -q
```

Expected: 全部通过。

- [ ] **Step 2: 运行 F9 validation 单测**

```powershell
python -m pytest tests\test_corpus\test_f9_validation.py -q
```

Expected: 全部通过。

- [ ] **Step 3: 运行完整测试**

```powershell
python -m pytest -q
```

Expected: 全部通过。

- [ ] **Step 4: 重跑 F9 validation**

```powershell
C:\Python313\python.exe scripts\corpus\f9_validation.py --output-dir docs\corpus\f9\validation
```

Expected: 生成新的 validation 产物。

- [ ] **Step 5: 检查 Gate**

```powershell
C:\Python313\python.exe -c "from pathlib import Path; text=Path('docs/corpus/f9/validation/f9_validation_report.md').read_text(encoding='utf-8'); start=text.index('## Gate Decision'); end=text.index('## Automatic Gate Criteria'); print(text[start:end])"
```

Expected target:

- `old_candidate_expectation_pass >= 8/10`
- `old_candidate_ER_IP_2_2 <= 2/10`
- `rerun_ER_2 <= 32/40`
- `rerun_IP_2 <= 32/40`

阈值说明：

- 旧坏候选是人工挑出的坏样本，所以 ER/IP 同时满分的上限是 20%。
- 新 40 条重跑样本是普通候选池，不要求低分，只要求不要满分饱和，所以 ER=2/IP=2 上限是 80%。

- [ ] **Step 6: 若仍失败，检查标签缺失**

```powershell
C:\Python313\python.exe -c "import csv; rows=list(csv.DictReader(open('docs/corpus/f9/validation/golden/f9_golden_existing_f4_scores.csv', encoding='utf-8-sig'))); [print(r['sample_no'], r['F4_ER'], r['F4_IP'], r['F4_EX'], r['boundary_flag'], r['f4_expectation_pass'], r['rationale']) for r in rows if r['f4_expectation_pass'] != 'true']"
```

Expected:

- 如果失败行 rationale 没有正确 `audit_tags`，回到 Task 3 补示例。
- 如果 tag 正确但 cap 不足，再讨论 cap 逻辑；不要先盲目加强 prompt。

### Task 6: 分离 F3 残留问题

**Files:**
- Read: `docs/corpus/f9/validation/f9_validation_report.md`

- [ ] **Step 1: 检查 F3 flagged rows**

```powershell
rg -n "Generated Flagged Rows|contains:" docs\corpus\f9\validation\f9_validation_report.md
```

Expected:

- 如果仍有 `sample 27 | c2 | contains:坐得近`，这是 F3 生成端事实/动机补全残留，不能混入 F4 修复。
- 如果 F4 指标已经达标但 Gate 仍被 F3 阻塞，另开 F3 generator prompt 修复。

---

## 5. 验收标准

- `python -m pytest tests\test_services\test_critic_service.py -q` 通过。
- `python -m pytest tests\test_corpus\test_f9_validation.py -q` 通过。
- `python -m pytest -q` 通过。
- F9 validation 显示旧坏候选通过率 `>= 8/10`。
- F9 validation 显示旧坏候选 ER/IP 同时 `2/2` 数量 `<= 2/10`。
- F9 validation 显示 rerun `ER=2` 和 `IP=2` 数量均 `<= 32/40`。
- 普通事实补全只降分，不直接触发 all-candidates-blocked 风险。
- 硬边界事实编造、prompt 泄漏、鼓励隐瞒等仍然 boundary 出局。
- sample 16 这类具体低压二选一问题不会被误罚。

## 6. 自检

- 没有把 `audit_tags` 加进公开 `CandidateScore` schema，避免 API/DAO/migration 扩散。
- 已补齐逐标签中文示例，Task 6 中“回到 prompt 示例修正”不再空悬。
- 已覆盖多标签组合场景。
- 已澄清 20% 与 80% 两个验收阈值的来源。
