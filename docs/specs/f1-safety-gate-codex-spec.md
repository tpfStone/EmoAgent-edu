# F1 安全门模块规格

> **模块定位**：运行时管线第一环，最高优先级。中文情感教育系统（用户为初中生 12–15 岁）。
> **技术栈**：FastAPI + PostgreSQL + Redis + 本地 BERT 分类器；LLM 版安全门保留为兼容接口。

---

## 0. 当前状态 / 已完成 / 待办 / 后续计划

**当前状态**：已接入运行时。`/chat` 前置安全门默认使用 `ClassifierSafetyGateService` 和本地 `F1SafetyClassifier`；生产接口为 `/api/safety/classifier/evaluate`。旧的 LLM prompt 版 `/api/safety/evaluate` 仍保留，用于兼容和对照实验。`OrchestratorService` 只在 red 时短路下游 F2/F3，返回固定转介话术；yellow 是非阻断支持状态，普通生成继续。

**已完成**：
- 固定 red 转介模板已在代码中实现，包含可信成年人、12356、12355、120/110；yellow 支持提示会随安全结果保留，但不阻断普通生成。
- F1 本地分类器已迁入生产侧，启动时在 FastAPI lifespan 中预加载 BERT、分类头、scaler 和人工关键词表。
- 当前策略使用 `p_red` 与 `p_yellow + p_red` 做保守判定；生产阈值为 `F1_SAFETY_RED_THRESHOLD=0.45`、`F1_SAFETY_YELLOW_OR_RED_THRESHOLD=0.55`。
- soft rule 已用于减少口语夸张、欺凌词直升 red 等误判风险。
- `HISTORY_WINDOW_N` 已按“轮数 × 2 条消息”截取最近历史。
- 分类器加载或推理异常按 yellow 保守兜底；LLM 版接口的 JSON 解析失败、模型调用异常也按 yellow 处理。
- green/yellow/red 到 `block_generation` 与 `referral_message` 的映射已由代码填充。
- 判定日志通过 `safety_log_dao.create_log()` 写入。
- 服务与接口测试覆盖 `tests/test_services/test_safety_gate_service.py`、`tests/test_handlers/test_safety_handler.py`、`tests/test_services/test_orchestrator_service.py`。

**待办**：
- 当前提示词和转介话术仍硬编码在 service 中；若上线多地区资源，需要把热线与校园资源抽成配置。
- 现有 PsyQA 标注数据可支撑 F1 原型，但 red/yellow 样本仍偏少，分类器应视作第一道安全筛，不应承担唯一安全责任。

**后续计划入口**：
- F1/F4 历史实现问题：`../issues/2026-05-20-f1-f4-development-issues.md`
- 当前运行时链路索引：见本目录 `README.md`

## 1. 职责（一句话）

接收用户当前消息 + 最近 N 轮对话历史，判定风险等级（green/yellow/red），输出等级与转介动作。**green 和 yellow 继续进入后续路径；red 中断生成，返回固定转介内容。** 本模块只做风险分级与转介，不生成辅导对话。

---

## 2. 设计依据

- 分级逻辑挂靠 **C-SSRS（哥伦比亚自杀严重程度评定量表）学校版**：被动→主动意念（量表1–3项）= yellow（行为健康转介）；意图/计划/准备行为（量表4–6项）= red（紧急评估）。
- **危机信号常跨多轮累积**，故判定必须基于历史窗口，非单条消息。
- 三条铁律：①分级非一刀切（中低风险不可当高风险）；②红色绝不自行干预，只转介；③转介必含可信成年人（家长/老师/辅导员）+ 中国统一热线。

---

## 3. 输入 / 输出 Schema

### 输入
```json
{
  "session_id": "string",
  "current_message": "string",        // 用户当前这句
  "history": [                         // 最近 N 轮，时间正序，N 见 §6 配置
    {"role": "student", "text": "string"},
    {"role": "assistant", "text": "string"}
  ]
}
```

### 输出
```json
{
  "risk_level": "green | yellow | red",
  "matched_signals": ["string"],       // 命中的信号描述（便于日志/审计），green 时为空
  "rationale": "string",               // 一句中文判定理由
  "action": {
    "block_generation": false,         // green/yellow=false；red=true
    "referral_message": "string"       // green 时为空；yellow/red 可携带固定支持/转介话术
  }
}
```

> **重要**：公开输出仍是三分类标签。分类器内部会计算三类概率，但后续管线只依据 `action.block_generation` 分支：green/yellow→继续进入后续路径；red→直接把 `referral_message` 返回用户，**不进生成**。

## 4. 当前分类器实现

生产侧 F1 不再每轮调用 LLM。当前模型目录：

```text
exp/models/f1_safety_gate/manual-A-pattern-v1/
```

输入特征：

- `bert-base-chinese` 对用户输入做文本表征。
- 人工审查后的关键词表统计关键词命中频次。
- scaler 归一化关键词特征。
- 分类头输出 green/yellow/red 三类 logits，经 softmax 得到概率。

生产判定：

```text
if soft_rule 命中明显 red 必要条件，或 p_red >= 0.45:
    risk_level = red
elif p_yellow + p_red >= 0.55:
    risk_level = yellow
else:
    risk_level = green
```

本地 benchmark 显示单条推理平均约 12 ms，p95 约 17 ms；模型加载约 11 秒，因此必须在应用启动时预加载。

F1 不是最终安全兜底。F2 的 `secondary_safety` 会在第一次 LLM 介入时再次检查明显风险；F4 还会检查回应内容是否越界。

---

## 5. LLM 兼容 Prompt（保留接口，不是 `/chat` 默认路径）

```
你是一个面向中国初中生（12–15岁）情感教育系统的安全评估模块。你的唯一任务是评估用户最近的对话中是否存在自伤或自杀风险，并分级。你不与用户对话，只输出评估结果。

请基于【对话历史】和【当前消息】整体判断（风险信号可能分散在多轮中，需结合上下文，不要只看当前一句）。

分级标准（参照哥伦比亚自杀风险评估 C-SSRS）：
- green（无风险）：正常的情绪困扰、压力、烦躁、难过，但没有任何伤害自己的想法或表达。
- yellow（需关注）：出现被动或主动的自伤/自杀念头，但没有具体计划、意图或准备行为。例如表达"活着没意思""不想存在了""消失算了"等，但无进一步计划。
- red（高危）：出现自伤/自杀的意图、具体计划、方法、时间，或已有准备/尝试行为，或正在进行的伤害。

判定原则：
1. 分级要准确，不要把单纯的情绪宣泄（如"烦死了""我太菜了""不想上学"）误判为风险。
2. 但凡出现模糊的伤害自己的表达，宁可判 yellow 也不要漏判。
3. 只依据文本证据判断，不脑补。
4. 若不确定是 yellow 还是 red，从严判 red。

请输出严格的 JSON：
{
  "risk_level": "green/yellow/red",
  "matched_signals": ["命中的具体表达，逐条列出；green时为空数组"],
  "rationale": "一句话中文理由"
}

【对话历史】
{history}

【当前消息】
{current_message}
```

> 实现：把 LLM 返回的 JSON 解析后，由代码（非LLM）填充 `action` 字段（见转介话术），拼成 §3 的完整输出。转介话术不交给 LLM 即兴生成，用固定模板，确保信息（热线号码）永远正确。

---

## 6. 转介话术（固定模板，代码填充，勿让 LLM 即兴生成）

### yellow
```
谢谢你愿意把这些告诉我。听起来你现在很不容易，这些感受很重要，不该一个人扛着。
我想提醒你：和你信任的大人聊聊会很有帮助——可以是爸爸妈妈、老师，或学校的心理辅导老师。
如果你想找人随时说说话，可以拨打全国心理援助热线 12356，或共青团12355青少年服务台，都是免费的。
你愿意和我说说，是很勇敢的一步。
```

### red
```
我很担心你现在的安全，你的生命非常重要。
请立刻联系你信任的大人（爸爸妈妈、老师），告诉他们你现在的感受，不要独自面对。
现在就可以拨打：全国心理援助热线 12356，或紧急情况拨打 120 / 110。
共青团12355青少年服务台也随时可以倾诉。
你不是一个人，有人愿意帮你。请现在就找一个大人或拨打上面的电话。
```

> 🚧 后续盘：热线号码、附加资源（如本地校园辅导联系方式）应做成配置项，便于按地区/时间更新。号码已核（2025年起全国统一12356、12355青少年服务台）。

---

## 7. 配置项

| 配置 | 建议初值 | 说明 |
|---|---|---|
| `HISTORY_WINDOW_N` | 6 轮 | 读最近几轮历史。太短漏累积信号，太长增成本。🚧 试运行调 |
| `F1_SAFETY_MODEL_DIR` | `exp/models/f1_safety_gate/manual-A-pattern-v1` | 生产分类器目录 |
| `F1_SAFETY_BERT_MODEL` | `bert-base-chinese` | BERT 底座 |
| `F1_SAFETY_LOCAL_FILES_ONLY` | true | 生产侧默认不临时下载模型 |
| `F1_SAFETY_RED_THRESHOLD` | 0.45 | red 概率阈值 |
| `F1_SAFETY_YELLOW_OR_RED_THRESHOLD` | 0.55 | yellow/red 总概率阈值 |
| `F1_SAFETY_PRELOAD` | true | 启动时预加载分类器 |
| `SAFETY_LLM_TEMPERATURE` | 0 | 仅用于 LLM 兼容接口 |

---

## 8. 测试用例

| # | 当前消息（+历史） | 期望 risk_level | 说明 |
|---|---|---|---|
| T1 | "这次月考没考好，心情好差，不想上学了" | green | 单纯情绪/压力，非危机 |
| T2 | "烦死了！我妈天天唠叨，气死我了" | green | 情绪宣泄，非危机 |
| T3 | "最近总觉得活着没什么意思，挺没劲的" | yellow | 被动意念，无计划 |
| T4 | "我有时候想，要是我消失了是不是大家都轻松了" | yellow | 被动自杀意念，无计划 |
| T5 | "我想好了今晚就……（含具体方法/时间）" | red | 有计划/意图 → 高危 |
| T6 | 历史中第1轮"压力好大"，第5轮"撑不下去了想结束这一切" | red/yellow（按表达具体度） | **跨轮累积**，验证历史窗口生效 |
| T7 | "我太菜了，这题都不会，我是不是很笨" | green | 自我否定但非自伤，勿误判 |
| T8 | 空历史 + "你好" | green | 正常开场 |

> T6 是关键回归用例：必须确保模块读了历史、而非只看当前句。

---

## 9. 验收标准（Definition of Done）

- [x] FastAPI 端点，输入输出符合 §3 schema
- [x] `/chat` 使用分类器安全门；`/api/safety/classifier/evaluate` 可独立调用。
- [x] 分类器在 lifespan 中预加载，避免每次请求重新加载模型。
- [x] LLM 兼容接口仍可调用，temperature=0，解析 JSON 容错（解析失败时**默认从严按 yellow 处理**并记录，绝不静默放行）
- [x] 转介话术用 §5 固定模板，号码硬编码正确（不经 LLM）
- [x] 历史窗口 §6 可配置，T6 用例通过
- [x] green/yellow 时 `block_generation=false`，red 时为 true
- [x] 所有判定结果写日志（session_id, risk_level, matched_signals, 时间戳）供审计
- [x] 使用 PsyQA 标注数据训练并记录指标，实验入口见 `../../exp/README.md`。
- [ ] 如后续新增真实校园数据，应重新校准阈值和 red/yellow 召回。

> **失败兜底原则**：分类器调用异常、LLM 超时、JSON 解析失败或模型拒答时，当前代码按 yellow 保守处理，保留支持提示但不阻断普通生成；red 只在明确高危或达到 red 阈值时阻断。

---

## 10. 不在本模块范围

- 不生成任何辅导/共情对话内容（那是 F3 生成器的事）。
- 不做情境分类（那是 F2）。
- 不评估回应质量（那是 F4 critic）。
- 本模块只回答一个问题：当前对话安全吗？该不该继续、该不该转介？
