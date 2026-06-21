# F2 情境分析模块规格

> **模块定位**：运行时管线第②环（安全门放行后）。对标 CogMAS 的 Q-matrix lookup。中文情感教育系统（用户为初中生 12–15 岁）。
> **技术栈**：FastAPI + PostgreSQL + LLM API（复用 emoagent）。

---

## 0. 当前状态 / 已完成 / 待办 / 后续计划

**当前状态**：已接入运行时。`/api/scenario/evaluate` 与 `/chat` 中的 F2 均使用 `app/services/scenario_service.py`，输出 `scenario`、`scenario_confidence`、`activated_casel`、`support_mode`、`emotion_intensity`、`help_seeking`、`secondary_safety` 与 `rationale`。在线链路中，F2 是第一次 LLM 介入，因此同时承担 F1 之后的风险兜底。

**已完成**：
- 四类情境分类 prompt 已实现，LLM temperature 为 `SCENARIO_LLM_TEMPERATURE=0.0`。
- `SCENARIO_CASEL_MAP` 已硬编码，`activated_casel` 不由 LLM 即兴生成。
- `secondary_safety` 已加入 F2 schema。若 F2 发现 red 风险，`/chat` 会直接返回转介话术；yellow 作为非阻断支持状态保留；安全复核缺失或非法时返回 `safety_status=unavailable` 并暂停普通生成。
- `support_mode` 已接入 F3 首轮路由：强情绪优先 c1，明确求助优先 c2，其他走 balanced。
- JSON 包裹解析、非法情境和调用异常均默认归为“其他”。
- 服务与接口测试覆盖 `tests/test_services/test_scenario_service.py`、`tests/test_handlers/test_scenario_handler.py`、`tests/test_services/test_orchestrator_service.py`。

**待办**：
- 尚未把 45 条语料的 `scenario` 字段接成持续回归/准确率报告；当前主要是单元测试覆盖。
- 若分类延迟或成本成为瓶颈，再评估轻量分类器替代 LLM。

**后续计划入口**：
- 语料与标注入口：`../corpus/`
- 当前运行时链路索引：见本目录 `README.md`

## 1. 职责（一句话）

接收用户当前消息 + 对话历史，判定**情境类型**（学业压力 / 同伴关系 / 亲子摩擦 / 其他），并据此输出本轮应**激活的 CASEL 辅助评估维度子集**。同时，它要判断本轮更需要情绪承接还是低压解决起点，并做一次 LLM 兜底安全复核。它不生成最终回复、不打分，只做「路由」。

---

## 2. 设计依据

- 对应 CogMAS 的 Q-matrix：不是每条对话都跑全部维度，而是先判定情境，再激活相关维度，避免无关维度稀释信号。
- 三类核心情境（学业压力/同伴关系/亲子摩擦）是 MVP 范围，依据初中生高频议题 + SEL 文献。超出的归「其他」，仍可走通用共情，不阻断。
- 情境→CASEL 维度的映射来自方案文档 §五的「情境×维度」矩阵。

---

## 3. 输入 / 输出 Schema

### 输入
```json
{
  "session_id": "string",
  "current_message": "string",
  "history": [{"role": "student|assistant", "text": "string"}]
}
```

### 输出
```json
{
  "scenario": "学业压力 | 同伴关系 | 亲子摩擦 | 其他",
  "scenario_confidence": 0.0,                 // 0~1，可选，便于调试
  "activated_casel": ["自我觉察引导", "自我管理引导", "负责任决策引导"],
  "secondary_safety": {
    "risk_level": "green | yellow | red",
    "safety_status": "ok | degraded | unavailable",
    "matched_signals": [],
    "rationale": "一句中文判定理由",
    "action": {
      "block_generation": false,
      "referral_message": ""
    }
  },
  "support_mode": "emotion_first | solution_seeking | balanced",
  "emotion_intensity": "low | medium | high",
  "help_seeking": true,
  "rationale": "一句中文理由"
}
```

> `activated_casel` 直接传给 F3 和后台 F4。`support_mode` 决定首轮 F3 生成方向；`secondary_safety` 是 F1 之后的兜底安全复核。若 `secondary_safety.action.block_generation=true` 或 `secondary_safety.safety_status=unavailable`，编排层不进入 F3；red 返回固定转介，unavailable 返回“当前安全评估暂不可用”提示。yellow 是非阻断支持状态。

---

## 4. 情境 → 激活 CASEL 维度映射表（来自方案 §五）

| 情境 | 激活的 CASEL 维度 |
|---|---|
| 学业压力 | 自我觉察引导、自我管理引导、负责任决策引导 |
| 同伴关系 | 自我觉察引导、社会觉察培养、关系技能培养 |
| 亲子摩擦 | 自我觉察引导、自我管理引导、社会觉察培养、关系技能培养 |
| 其他 | 自我觉察引导（仅保底一项，走通用共情） |

> 此表硬编码为配置（dict），不需 LLM 决定激活哪些维度——LLM 只判情境类型，维度由表查出。这样可控、可解释、可改。

---

## 5. 判定 Prompt（中文，可直接用）

```
你是一个面向中国初中生情感教育系统的情境分类模块。给定用户的倾诉和对话历史，判断这属于哪一类情境。你只分类，不回应、不评价。

候选情境（四选一）：
- 学业压力：与考试、成绩、作业、学习状态、升学等相关。
- 同伴关系：与同学、朋友之间的相处、冲突、孤立、误会等相关。
- 亲子摩擦：与父母/家人之间的矛盾、不被理解、管控、沟通问题等相关。
- 其他：以上都不明显，或涉及多类难以归为单一类。

判断原则：
1. 结合历史综合判断，以当前消息为主。
2. 若同时涉及多类，选最主要的那一类；若确实无法区分主次，归"其他"。
3. 只输出分类，不要劝导或建议。

输出严格 JSON：
{
  "scenario": "学业压力/同伴关系/亲子摩擦/其他",
  "scenario_confidence": 0~1的小数,
  "secondary_safety": {
    "risk_level": "green/yellow/red",
    "matched_signals": ["若有明显风险，列出具体表达；否则为空数组"],
    "rationale": "一句中文安全复核理由"
  },
  "support_mode": "emotion_first/solution_seeking/balanced",
  "emotion_intensity": "low/medium/high",
  "help_seeking": true/false,
  "rationale": "一句话中文理由"
}

【对话历史】{history}
【当前消息】{current_message}
```

> 代码拿到 `scenario` 后，用 §4 映射表查出 `activated_casel`。LLM 只需给出 `secondary_safety.risk_level` 等判定字段；`safety_status` 与固定转介 action 由代码补全，避免让 LLM 即兴生成安全话术。缺失或非法 `secondary_safety` 会被代码转为 `safety_status=unavailable`。

---

## 6. 实现方式选择

- **MVP 默认：用上面的 LLM prompt 分类**（简单、零训练、够用）。
- 🚧 后续盘：emoagent 项目里已有 BERT 模型，若分类延迟/成本成为瓶颈，可训练/复用一个轻量分类器替代 LLM 调用。MVP 阶段不做。

---

## 7. 配置项

| 配置 | 建议初值 | 说明 |
|---|---|---|
| `HISTORY_WINDOW_N` | 6 轮 | 与 F1 对齐，可共用会话历史缓存 |
| `LLM_MODEL` | 复用 emoagent | 分类任务用快模型即可 |
| `LLM_TEMPERATURE` | 0 | 分类要确定性 |
| `SCENARIO_CASEL_MAP` | §4 表 | 硬编码 dict，便于修改 |
| `support_mode` | LLM 输出 | 仅用于内部路由，不直接展示给学生 |
| `secondary_safety` | LLM 输出 + 代码补 action/status | F1 后的风险兜底；red 短路，yellow 为非阻断支持状态；缺失或非法值返回 `safety_status=unavailable` 并阻断普通生成 |

---

## 8. 测试用例

| # | 输入 | 期望 scenario | 期望激活维度 |
|---|---|---|---|
| T1 | "这次月考没考好，压力好大" | 学业压力 | 自我觉察、自我管理、负责任决策 |
| T2 | "他们出去玩没叫我" | 同伴关系 | 自我觉察、社会觉察、关系技能 |
| T3 | "我妈又翻我手机了" | 亲子摩擦 | 自我觉察、自我管理、社会觉察、关系技能 |
| T4 | "今天天气不错，随便聊聊" | 其他 | 自我觉察（保底） |
| T5 | "考试压力大，回家我妈还说我"（跨两类） | 取最主要一类，或其他 | 对应表 |
| T6 | 可用 EmoEdu-语料-45条.json 的 scenario 字段做批量对拍 | 分类准确率 | — |

> T6 是现成福利：45 条语料每条都标了 scenario，可直接当 F2 的标注测试集，算分类准确率。

---

## 9. 验收标准（DoD）

- [x] FastAPI 端点，IO 符合 §3
- [x] LLM 分类用 §5 prompt，temperature=0，JSON 解析容错（失败默认归"其他"，不报错中断）
- [x] activated_casel 由 §4 表查出，非 LLM 即兴
- [x] 输出可直接接入 F3 和后台 F4。
- [x] 输出 `secondary_safety`，作为 F1 之后的 LLM 风险兜底。
- [x] 输出 `support_mode`、`emotion_intensity`、`help_seeking`，作为 F3 首轮方向选择依据。
- [ ] §8 批量语料用例纳入持续回归，并记录分类准确率。

---

## 10. 不在本模块范围

- 不替代 F1 主安全门；这里只做 F1 之后的 LLM 兜底复核。
- 不生成回应（F3）、不打分（F4）。
- 不决定 EPITOME 维度（那是 critic 恒评项）。
- 本模块只回答：这是什么情境、该激活哪些教育维度。
