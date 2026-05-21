# MVP 集成规划与后续开发路线图

> **用途**：把 F1/F2/F3/F4 四个模块串成一条能跑的最小对话链路（MVP），并规划 MVP 之后的开发顺序。配套各模块 Codex 规格。
> **技术栈**：FastAPI + PostgreSQL + Redis + LLM API（复用 emoagent）。

---

## 1. MVP 是什么 / 不是什么

- **MVP = 一条能完整跑通的单轮对话链路**：用户说话 → 安全门 → 情境分析 → 两取向生成 → critic 择优 → 回复，并把候选与分数落库。
- **MVP 包含**：F1 安全门、F2 情境分析、F3 生成器、F4 critic、F5 日志（F5 不是独立模块，是 F4/编排层顺带落库）。
- **MVP 不包含**：F6 RAG（生成器先不吃参考）、F7 DPO（先不训练）、第三取向、F9 信度校验。这些是 MVP 之后。
- **MVP 的成功标准**：能对一条初中生倾诉给出一条经过安全把关、按情境定制、择优后的回应，全链路不崩，数据落库正确。**它证明 generator-critic 架构在你手里真能转。**

---

## 2. 四模块如何串（编排层 orchestrator）

MVP 需要一个**编排层**把四个模块按顺序调起来。这是 F1–F4 之外要新写的「胶水」，建议单独一个 orchestrator service。

```
POST /chat  (用户发来一条消息)
  │
  ▼
[编排层 orchestrator]
  │
  ├─① 调 F1 安全门(current_message, history)
  │     └─ risk_level != green → 直接返回 referral_message，结束（不往下走）
  │
  ├─② 调 F2 情境分析(current_message, history)
  │     └─ 得到 scenario + activated_casel
  │
  ├─③ 调 F3 生成器(user_message, history, scenario, rag_examples=[])
  │     └─ 得到 candidates[]（MVP 阶段 rag_examples 传空）
  │
  ├─④ 调 F4 critic(user_message, history, activated_casel, candidates)
  │     └─ 得到 best_candidate_id + scores + preference_pair
  │
  ├─⑤ 落库(F5)：会话、候选全集、各维分数、preference_pair → PostgreSQL
  │
  └─⑥ 返回 best_candidate 的 text 给用户
```

### 编排层要处理的关键点
- **短路**：F1 非 green 立即返回，不调用后续模块（省成本 + 安全优先）。
- **会话历史**：Redis 缓存每个 session 的对话历史，F1/F2/F3/F4 共用同一份 history（统一 HISTORY_WINDOW_N=6）。
- **失败兜底**：任一模块异常 → 返回安全兜底话术（如"我现在有点没反应过来，要不你再说一次？"），不抛原始错误给用户。F1 异常尤其要按非 green 保守处理。
- **全候选出局**：若 F4 所有候选都 boundary_flag=true，返回兜底/转介，不强行回复。

---

## 3. 数据模型（PostgreSQL，MVP 最简）

```
sessions(session_id, created_at, ...)
messages(id, session_id, role, text, created_at)
turns(                          -- 每次系统应答一条记录
  id, session_id,
  user_message,
  risk_level,                   -- 来自 F1
  scenario, activated_casel,    -- 来自 F2
  best_candidate_id,
  created_at
)
candidates(                     -- 每个候选一条，供 DPO
  id, turn_id, candidate_id, orientation, text,
  epitome_er, epitome_ip, epitome_ex,
  casel_scores_json,
  boundary_flag, weighted_total,
  is_winner                     -- 便于后续抽 preference pair
)
preference_pairs(id, turn_id, winner_id, loser_id, created_at)  -- 供 F7 DPO
```

> candidates 表是**免费 DPO 数据**的来源——每轮的 winner/loser 天然成对，攒着就是 F7 的训练料。

---

## 4. 开发顺序（建议）

### 阶段 0：准备
- [ ] 确认 emoagent 的 LLM API 配置可复用（DeepSeek key、base url）
- [ ] 建 PostgreSQL 表（§3）、Redis 会话缓存
- [ ] 准备好 EmoEdu-语料-45条.json 作测试输入

### 阶段 1：单模块各自跑通（可并行交 Codex）
- [ ] F1 安全门 → 过自己的 8 个测试用例
- [ ] F2 情境分析 → 用 45 条语料跑分类准确率
- [ ] F3 生成器 → 能出两个不同取向候选
- [ ] F4 critic → 过自己的 7 个测试用例
> 四个模块**接口已对齐**（F2.activated_casel→F4；F3.candidates→F4），可独立开发再拼。

### 前置任务 A：补齐 F4 CASEL 辅助评分
> 这是串 MVP `/chat` 前的前置任务，不是“阶段 0：准备”。阶段编号保持路线图原意不变。

- [ ] F4 在 `activated_casel` 非空时评对应 CASEL 维度，量纲 `0/1/2`
- [ ] CASEL 评分并入现有 critic judge prompt，不新增第二次 LLM 调用
- [ ] 仅保留 `activated_casel` 中的维度；漏评维度补 `0`，未激活维度丢弃
- [ ] 总分改为 `ER + IP + EX + 0.5 * sum(casel_scores)`
- [ ] `activated_casel=[]` 时保持 EPITOME-only 行为不变

### 阶段 2：编排层串 MVP
- [ ] 写 orchestrator（§2 流程 + 短路 + 兜底）
- [ ] 端到端：丢一条语料进 /chat，看能否走完全链路并落库
- [ ] 用 45 条语料逐条跑，人工看回应合理性 + 检查各环节数据

### 阶段 3：MVP 之后
- [ ] **F9 信度校验**：抽 30–50 条候选人工标 EPITOME 0/1/2，算与 F4 的一致性 → 这是 DPO 可信前提，也是论文证据
- [ ] **F6 RAG**：定向量库（pgvector 复用 PG / 独立库），批量生成 500–750 条 RAG 语料填池，接入 F3 的 rag_examples
- [ ] **F7 DPO**：攒够 preference_pairs 后离线训练，更新 F3 底座
- [ ] **F8 第三取向**（行动建议型）：视效果加
- [ ] 权重调优：用 DPO/校验数据反推 EPITOME/CASEL 权重（替代当前等权）

---

## 5. 里程碑与论文的对应

| 里程碑 | 证明了什么 | 论文里写成 |
|---|---|---|
| MVP 跑通 | generator-critic 架构可行 | 系统架构与实现 |
| F9 信度校验通过 | LLM-judge 在本任务可靠 | 方法可靠性验证（关键！） |
| F6 RAG 接入 | 检索增强提升回应质量 | 消融：有无 RAG |
| F7 DPO 见效 | 系统能自进化 | 消融：有无 DPO（对标 CogMAS） |

> 没有 F9，DPO 和系统效果的所有结论都站不住（AI 教 AI 无锚点）。F9 是论文可信度的命门，别跳过。

---

## 6. 当前可立即交 Codex 的模块

F1、F2、F3、F4 的完整规格**均已就绪**，接口互相对齐，可并行开发。编排层（§2）待四模块跑通后写。

**建议执行顺序**：F1（最该先验证安全）→ F2、F3、F4（并行）→ 编排层串 MVP → 阶段 3。
