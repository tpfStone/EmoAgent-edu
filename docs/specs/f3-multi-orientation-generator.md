# F3 多取向生成器优化方案

F3 位于 `F1 安全门 -> F2 情境分析 -> F3 生成` 的第三步，负责根据学生当前倾诉、对话历史、F2 情境结果和 PsyQA 支持信息生成回应。模块接口保留两条不同取向的候选回复，用于实验和调试：

- `c1 情感共情型`：更强调情绪被接住，对应 EPITOME 的 ER。
- `c2 认知共情型`：更强调处境和担心被说准，对应 EPITOME 的 IP。

生产 `/chat` 链路为了降低等待时间，首轮不再在线生成双候选并等待 F4，而是根据 F2 的 `support_mode` 选择一个方向生成单候选，并通过 SSE 流式返回。后续测试统一优先使用 DashScope 兼容模式下的 `qwen3.7-plus`。生成器保持较高温度，F1/F2/F4 保持低温确定性。

## 设计依据

CogMAS 的可迁移点不是简单增加 agent 数量，而是把复杂任务拆成不同职责的 teacher agent，再用检索样例和 evaluation agent 控制质量。迁移到 EmoEdu 后，F3 的两个候选生成器对应两个 teacher agent：同一底座模型，不同 prompt 取向。F4 critic 承担 CogMAS 中 evaluation agent 的职责，负责检测边界问题并选择更合适的候选。

PsyQA 标注数据提供两类支持：

- `psyqa_strategy_sequence` 用于统计场景对应的策略先验。
- `psyqa_strategy_segments` 和原始 `input` 用于构建短 support card。

PsyQA 不能直接作为整段回复模板库。当前标注数据中 `Interpretation` 和 `Direct Guidance` 频率很高，尤其学业压力场景中 `Direct Guidance` 占比最高。如果直接把完整 output 放进 RAG，模型容易过早给建议，变成说教或解决方案导向。因此 F3 只使用“策略先验”和“短片段支持”，不照抄原始输出。

## 数据使用策略

当前 `exp/data/psyqa_labelled.json` 中共有 4012 条标注数据：

- `direct_exemplar`：150 条，适合进入样例库。
- `strategy_reference`：1336 条，适合做策略统计和补充检索。
- `negative_example`：724 条，主要供 F4 critic 和后续负例实验使用。
- `reject`：1802 条，不进入 F3。

F3 的检索优先级：

1. 同场景 `direct_exemplar + good + green`。
2. 同场景 `strategy_reference + good/rewrite + green`。
3. 仍不足时才跨场景补充，但只作为语言动作参考。

不进入 F3 正向检索的内容：

- `negative_example`
- `reject`
- `safety_level` 非 green 的样本
- 自我暴露片段
- 过长、成人化、诊断化、药物化、私聊引导等片段

## 策略先验

F3SupportService 启动时读取 PsyQA 标注数据，按 scenario 统计：

- 样本数量
- 高频策略
- 常见起手策略
- 常见策略转移
- direct exemplar 数量

统计结果只用于内部 prompt，不直接展示给用户。

场景层面的通用结论：

- 学业压力：`Direct Guidance` 和 `Interpretation` 很高，但第一轮默认延后建议。
- 同伴关系：`Interpretation` 高，适合做处境澄清，但不能替同伴猜动机。
- 亲子摩擦：`Interpretation` 高，适合说准不被理解和边界感，但不能制造亲子对立。

策略进入 F3 的方式：

- `Restatement`：必须保留，负责具体复述。
- `Approval and Reassurance`：适合 c1，负责温和承接。
- `Interpretation`：适合 c2，负责说准处境和担心。
- `Information`：少量可用，但不主动科普。
- `Direct Guidance`：作为后续可能方向，第一轮默认延后。
- `Self-disclosure`：面向初中生默认禁用。
- `Others`：不作为正向策略。

## Support Card

F3 不把 PsyQA 原始 output 整段塞进 prompt，而是生成短 support card：

```text
【支持卡 1｜direct_exemplar｜同伴关系｜source=1368】
相似倾诉：朋友周末出去玩没有叫我，我翻了好几遍群消息。
策略路径：具体复述[Restatement] -> 温和承接[Approval and Reassurance] -> 处境澄清[Interpretation]
可借鉴的语言动作：
- 具体复述：你翻了好几遍群消息，发现他们出去玩没有叫你。
- 温和承接：那种被落下的感觉会很堵。
注意：样例含行动建议时，只把它当作后续可能方向，本轮不要照搬建议。
```

支持卡只提供语言动作，不要求模型复述原句。每轮最多取 `F3_SUPPORT_TOP_K` 张，默认 2 张。

## Prompt 组成

F3 的 prompt 由以下部分组成：

```text
COMMON_PROMPT
F9_RELIABILITY_GUARDRAILS
ORIENTATION_PROMPT[c1/c2]

【情境】F2 scenario
【本轮对话阶段】first_contact/follow_up
【本轮支持路由】emotion_first/solution_seeking/balanced
【情绪强度】low/medium/high
【是否明确求助】true/false
【对话历史】最近 N 轮
【策略先验】F3SupportService 统计结果
【PsyQA 支持卡】F3SupportService 检索结果 + 外部 rag_examples
【孩子刚说的话】当前用户输入
```

c1 的生成目标：

- 先具体复述。
- 再说出那一刻的具体情绪。
- 不解释原因，不建议，不追问。
- 强情绪首轮要有陪伴感，但不要显性表演“我懂你”。陪伴感来自具体场景、身体/心理感受和短句节奏，不来自“我理解你”“我在这里”“你不是一个人”等模板话。
- 避免模板兜底和抽象抒情，例如默认用“先不急着……”“慢慢来”“这样也没什么不对”收尾；优先 2 句，最多 3 句。

c2 的生成目标：

- 先具体复述。
- 再说准学生卡住的点、担心或处境意义。
- 不替第三方解释动机，不抛新观点，不给解决步骤。
- 如果用户明确问“怎么办/怎么解决/怎么说”，c2 采用“说准卡点 + 一个低压可执行起点”：先点出他真正卡住的两难或循环，再给一个小的、可选择的第一步。
- 这个起点不能是命令、不能替用户决定、不能要求马上摊牌，也不能制造亲子或同伴对立；更适合是先想清一句话、换一个不容易冲突的时机、把两个念头分开看，或用轻一点的方式试探。

## 人工偏好校准

2026-06-03 的 F4 clean pair 人工标注显示，c1/c2 不是固定谁更好，而是和用户当轮状态有关。15 个 clean pair 中，人工偏好 `B` 为 10 条、`A` 为 5 条；模型 critic 在 clean c1/c2 选择上的一致率并不稳定，说明不能把 F4 直接当作唯一偏好来源。

人工标注得到的关键规则：

- 用户消极情绪很强、主要在倾诉时，c1 的情感认同更合适，回应要让学生先感到“这份情绪被看见了”。
- c1 的“被看见”不能写成过度的“我懂你”。更好的写法是点回具体画面，再说出那一下真实的发慌、堵住、僵住、丢脸、委屈或喘不过气。
- 用户明确问“怎么办/怎么解决/怎么改变”时，c2 更有价值，应该把卡住点、担心和可能的下一步说清楚，但不能越界分析。
- c2 的下一步只给“低压可执行起点”，不做步骤清单，不把问题抛回给用户，也不使用“你觉得呢/你是不是该/为什么不”这类反问收尾。
- 第一次交互尽量不用反问句。反问容易让学生觉得问题被抛回自己，尤其在还没建立信任时。
- 持续上下文中不能一直只做情绪承接。首轮在线链路走“安全门、情境分析、单候选流式生成、后台 critic”；后续对话应逐渐加入 CBT 兼容的支持：简短承接、区分感受/想法/行为反应、给一个可选择的小起点。

因此 F2 现在额外输出内部路由信号：

```json
{
  "support_mode": "emotion_first | solution_seeking | balanced",
  "emotion_intensity": "low | medium | high",
  "help_seeking": true
}
```

F3 根据这些信号调整 prompt：

- `first_contact + emotion_first/high`：生产路径直接生成 c1，少问问题，不急着分析和建议。
- `first_contact + solution_seeking`：生产路径直接生成 c2，可以把卡点说准，但不使用反问作为默认收尾。
- `follow_up + solution_seeking`：允许给一个很小、非命令式的下一步。
- `follow_up + balanced`：不重复空泛安慰，逐步转向感受、想法、行为和可控边界的澄清。

这不是把 CBT 显性写给学生，而是让生成器在语言结构上更接近可持续的情感教育支持。

## 工程接口

新增服务：

```python
F3SupportService(settings).build_context(
    scenario="同伴关系",
    user_message="他们周末出去玩没叫我",
    external_examples=[],
)
```

返回：

```python
F3SupportContext(
    strategy_prior="统计支撑...",
    support_cards=["【支持卡 1...】", "【支持卡 2...】"],
)
```

GeneratorService 新构造：

```python
GeneratorService(llm_client, settings, f3_support_service)
```

外部 API 保持兼容：

```json
{
  "session_id": "string",
  "user_message": "string",
  "history": [{"role": "student", "text": "string"}],
  "scenario": "学业压力 | 同伴关系 | 亲子摩擦 | 其他",
  "rag_examples": []
}
```

`rag_examples` 仍可传入，但会被当作外部参考附加到 support card 后面。

生产 `/chat` 首轮使用：

```python
GeneratorService.stream_one_text(
    request,
    candidate_id="c1 | c2",
)
```

生产后续轮次使用：

```python
GeneratorService.stream_followup_text(
    session_id="string",
    current_message="string",
    history=[...],
    f4_guidance="后台 critic 已完成时注入；为空则忽略",
)
```

完整 `generate()` 双候选能力仍保留给 `/api/generator/generate` 和 `exp/` 实验脚本。

## 生产化原则

F3SupportService 应作为长生命周期实例使用，不要每次请求重新加载 JSON。当前 FastAPI lifespan 会在 `F3_SUPPORT_PRELOAD=true` 时预加载 `app.state.f3_support_service`，依赖层没有发现 app state 时才通过 lru_cache 创建。

轻量检索当前采用中文 n-gram overlap，不依赖 embedding，启动快、成本低。后续如果 direct exemplar 规模扩大，可以替换为 embedding 检索，但接口保持不变。

## 验收指标

F3 单独验收：

- c1 的 ER 应高于 c2。
- c2 的 IP 应高于 c1。
- 两条候选都不得过早给建议。
- 两条候选都不得照抄 support card。
- 输出保持 2-3 句，短、清楚、有温度。

F3-F4 联合验收：

- F4 能识别过早建议、第三方动机猜测、空泛安慰、过度解释。
- F4 选择结果不应长期偏向某一个 orientation。
- winner/loser 可沉淀为后续 DPO 偏好数据。

短期内生产侧先保持单候选流式生成，F4 只做后台指导。DPO 需要等 F4 pairwise 与人工偏好对齐更稳定，并积累足够高置信 preference pair 后再进入。
