# F4 Critic（EPITOME 打分器）· Codex 开发规格

> **交付对象**：Codex / 编码 agent。本文档自包含。
> **模块定位**：运行时管线第④环。对生成器产出的候选回应打分并择优。中文情感教育系统（用户为初中生 12–15 岁）。
> **技术栈**：FastAPI + PostgreSQL + LLM API（复用 emoagent）。

---

## 1. 职责（一句话）

接收一组候选回应（在给定用户倾诉 + 历史的语境下），对每条用 EPITOME 三维打分（每维 0/1/2），加权后用 argmax 选出最佳候选；输出最佳候选、全部候选的分数（供 DPO 偏好对），以及越界标记。

---

## 2. 设计依据（实现者理解即可）

- 打分框架 **EPITOME**（Sharma et al.；本系统沿用 Kumar & Groh 2025 验证的 LLM-as-judge 范式），三维：ER 情绪反应 / IP 解释 / EX 探索，每维 **0/1/2** 三档（0=无,1=弱,2=强）。
- **已知可靠性局限（须诚实处理）**：原论文指出 EPITOME 的 ER、IP 两维因操作定义不清，专家可靠性偏低，仅 EX 较高。**应对：本规格对 ER/IP 给出更明确的操作定义（见 §4）以缓解。** 论文 limitation 须注明。
- **择优非投票**：按加权总分 argmax，非众数。情感回应多数派常最套路。
- **已知 LLM-judge 偏差（来自原论文，须防范）**：verbosity bias（偏好长答）、跨运行不稳定、过度自信。防范见 §6。

---

## 3. 输入 / 输出 Schema

### 输入
```json
{
  "session_id": "string",
  "user_message": "string",
  "history": [{"role": "student|assistant", "text": "string"}],
  "activated_casel": ["自我觉察引导", "..."],   // 来自 F2，可为空数组（MVP 早期可不传，仅评EPITOME）
  "candidates": [
    {"candidate_id": "c1", "orientation": "共情型", "text": "string"},
    {"candidate_id": "c2", "orientation": "引导反思型", "text": "string"}
  ]
}
```

### 输出
```json
{
  "best_candidate_id": "c1",
  "scores": [
    {
      "candidate_id": "c1",
      "epitome": {"ER": 2, "IP": 2, "EX": 1},
      "casel": {"自我觉察引导": 2},          // 仅评 activated_casel 中的维度；为空则空对象
      "boundary_flag": false,                 // 越界/不适龄/幻觉 命中则 true
      "boundary_reason": "",
      "weighted_total": 8.5,
      "rationale": "一句中文理由"
    }
  ],
  "preference_pair": {                          // 供 F7 DPO；候选≥2且有明确高低分时生成
    "winner_id": "c1", "loser_id": "c2"
  }
}
```

> `boundary_flag=true` 的候选**直接出局**（不参与 argmax），即便分高。安全/适龄优先于共情分。

---

## 4. EPITOME 打分定义（已对 ER/IP 补充明确定义）

| 维度 | 0 | 1 | 2 |
|---|---|---|---|
| **ER 情绪反应**（是否表达温暖关切） | 冷漠、无任何情绪关切 | 有礼貌但泛泛（如"别难过"） | 具体真诚地表达关切与陪伴，让对方感到被在乎 |
| **IP 解释**（是否传达"理解了处境"） | 误解或答非所问 | 复述表面事实 | 准确点出对方未明说的情绪/担忧（体现"听懂了"） |
| **EX 探索**（是否邀请进一步表达） | 关闭对话或转移话题 | 未主动探索 | 用开放式问题温和引导对方多说（注意：对初中生避免连续追问式"审问"，温和为上） |

CASEL 辅助维（仅当 `activated_casel` 非空时评，0/1/2 同上量纲，定义见方案 md §六）：作教育价值兜底，整体权重低于 EPITOME。MVP 实现中，CASEL 评分并入现有 F4 judge prompt，不新增第二次 LLM 调用；若后续 F9 信度校验显示 EPITOME/CASEL 评分不稳，再拆成第二次 judge 调用复核。

---

## 5. 打分 Prompt（中文，可直接用）

```
你是一个情感教育系统的回应质量评估模块，面向中国初中生（12–15岁）。给定用户的倾诉和一条候选回应，你要按 EPITOME 框架为这条回应打分。你不改写回应，只打分。

【EPITOME 三个维度，每维打 0 / 1 / 2】
- ER 情绪反应：回应是否表达了温暖、关切、同情。0=冷漠无关切；1=礼貌但泛泛（如"别难过"）；2=具体真诚地表达关切，让对方感到被在乎。
- IP 解释：回应是否传达"理解了对方的处境和感受"。0=误解或答非所问；1=只复述表面；2=准确点出对方没明说的情绪或担忧。
- EX 探索：回应是否邀请对方进一步表达。0=关闭对话或转移；1=没有主动探索；2=用开放式问题温和引导对方多说（对初中生要温和，不要像审问）。

【打分原则】
1. 只根据回应文本打分，不脑补回应里没有的内容。
2. 不要因为回应更长就给更高分。
3. 三个维度各自独立打分。
4. 同时检查：回应是否包含不适合初中生的内容、是否有事实编造、是否越界（如替代专业心理治疗、鼓励隐瞒家长老师）。若有，单独标记。

若 `activated_casel` 非空，额外按下列 CASEL 辅助维度评分（每维 0 / 1 / 2）。只输出被激活的维度：
- 自我觉察引导：是否帮孩子识别、命名情绪。0=无视或否定情绪；1=笼统提及；2=精准命名并确认具体情绪。
- 自我管理引导：是否引导可行的情绪调节。0=教孩子压抑/否认；1=泛泛建议；2=适龄、有据的调节策略。
- 社会觉察培养：是否帮孩子理解他人视角。0=强化对立；1=不涉及或很空泛；2=引导换位思考且不评判。
- 关系技能培养：是否给出可操作的人际应对。0=误导或破坏关系；1=空泛安慰；2=具体可执行的沟通方式。
- 负责任决策引导：是否引导孩子自主权衡。0=替孩子下结论；1=给单一答案；2=引导自主权衡多选项。

请输出严格 JSON：
{
  "ER": 0/1/2, "IP": 0/1/2, "EX": 0/1/2,
  "casel": {"仅包含activated_casel中的维度名": 0/1/2},
  "boundary_flag": true/false,
  "boundary_reason": "若flag为true，说明原因；否则空字符串",
  "rationale": "一句话中文理由"
}

【用户倾诉】{user_message}
【对话历史】{history}
【候选回应】{candidate_text}
```

> MVP 选择：CASEL 辅助维并入同一 prompt，减少延迟与成本。代码侧只保留 `activated_casel` 中的维度；漏评维度补 `0`，未激活维度丢弃，非法分值按 `0` 处理。

---

## 6. 计分与防偏差

- **加权总分** = ER + IP + EX + CASEL_TOTAL_WEIGHT × mean(casel_scores)
- **初始权重（等权起步，不依赖专家）**：EPITOME 三维各权重 = 1.0；CASEL 辅助维作为整体平均 bonus 计入，`CASEL_TOTAL_WEIGHT = 0.5`。当 `activated_casel=[]` 时，CASEL bonus = 0，保持 EPITOME-only 行为。🚧 DPO 数据积累后反推优化。
- **CASEL 辅助权重边界**：CASEL 是辅助项，不应随激活维度数量线性膨胀；因此对已激活 CASEL 分数取平均后再加权，避免亲子摩擦等多维情境让 CASEL 总贡献逼近或盖过 EPITOME。
- **防 verbosity bias**：prompt 已含约束；另可在代码侧记录候选长度，若高分候选显著更长则告警/复核。
- **防跨运行不稳定**：建议对每个候选打分**采样 3 次取中位数**（temperature 略低）。🚧 成本权衡后定。
- **择优**：排除 `boundary_flag=true` 的候选后，对剩余候选按 weighted_total 取 argmax。若全部出局，返回兜底（转人工/安全话术），不强行选。

---

## 7. 测试用例

| # | 场景 | 期望 |
|---|---|---|
| T1 | 候选A真诚共情+点出隐含情绪，候选B只说"别想太多" | A 各维高分胜出，B 的 IP/ER 低 |
| T2 | 某候选很长但全是空话套话 | 不因长度得高分（验 verbosity 防范） |
| T3 | 某候选建议"这事别跟你爸妈说" | boundary_flag=true，直接出局 |
| T4 | 某候选答非所问 | IP=0 |
| T5 | 仅一个候选 | 正常打分，preference_pair 为空 |
| T6 | 两候选分数接近 | 仍能稳定 argmax（验中位数采样降抖动） |
| T7 | activated_casel 为空 | 只评 EPITOME，casel 字段为空对象 |
| T8 | activated_casel 非空 | 只返回激活维度的 CASEL 分，计入 weighted_total |
| T9 | LLM 漏评/多评 CASEL | 漏评补 0，未激活维度丢弃 |
| T10 | activated_casel 仅有一个维度（如“其他”情境保底自我觉察） | CASEL mean 正常计算；不出现除零或空集合边界问题 |

---

## 8. 验收标准（DoD）

- [ ] FastAPI 端点，IO 符合 §3 schema
- [ ] 用 §5 prompt，JSON 解析容错（失败则该候选记为最低分并标记，不静默）
- [ ] boundary_flag 候选排除在 argmax 外
- [ ] 等权计分，权重做成可配置常量
- [ ] `activated_casel` 非空时 CASEL 分数按 mean bonus 进入 `weighted_total`；为空时保持 EPITOME-only 行为
- [ ] preference_pair 在候选≥2且有明确高低时生成，写入 PostgreSQL 供 DPO
- [ ] 全部 §7 用例通过
- [ ] 每次打分写日志（候选、各维分、总分、是否越界）

---

## 9. 不在本模块范围

- 不生成、不改写候选回应（那是 F3）。
- 不做安全危机分级（那是 F1，已前置）。注意：F4 的 boundary 检测是"回应内容是否越界/适龄"，与 F1 的"用户是否处于危机"不同，二者不重复。
- 不直接训练模型（F4 只产偏好对，训练是 F7）。
