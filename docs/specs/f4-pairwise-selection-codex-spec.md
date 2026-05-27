# F4 Pairwise 择优改造 · Codex 增量开发规格

> **交付对象**：Codex / 编码 agent。本文档是对 `f4-critic-epitome-codex-spec.md` 的**增量改造**，不替代原 spec。原 spec 的 EPITOME pointwise 打分、CASEL 辅助、boundary 检测全部保留；本改造**只替换"如何择优、如何产偏好对"这一环**。
> **模块定位**：运行时管线第④环（F4 critic 内部）。中文情感教育系统（用户为初中生 12–15 岁）。
> **技术栈**：FastAPI + PostgreSQL + LLM API（critic 专用 client，模型 `deepseek-v4-pro`）。

---

## 0. 为什么做这个改造（实现者理解即可，不必复述）

实测发现（须知背景，影响实现取舍）：
- 用 pointwise 绝对评分（每维 0/1/2 再加权 argmax）时，critic 与人工一致性低：`deepseek-chat` 10/20，升级到 `deepseek-v4-pro` 仍仅 11/20。
- 根因不在模型档位，而在**任务形态**：弱模型对"什么算 2 分"缺乏稳定绝对标尺，导致 ER 偏宽、IP 飘。
- LLM-as-judge 的已知规律：**pairwise（A 和 B 哪个好）比 pointwise（每条打绝对分）稳得多**，因为相对判断不需要稳定的绝对标尺。
- 下游 DPO 真正需要的是 winner/loser **偏好对**，绝对分本就是多余的中间产物。

因此本改造：**择优与偏好对改由 pairwise 比较产出（新的真值来源）；EPITOME 三维 pointwise 分继续打，但降级为诊断性/展示性输出，经 F9 校验前不作真值。**

---

## 1. 改造后的职责（一句话）

接收一组候选回应（MVP 恰好 2 个），在给定用户倾诉 + 历史的语境下：
1. 对每条仍做 EPITOME 三维 pointwise 打分（0/1/2）+ CASEL 辅助 + boundary 检测 —— **逻辑沿用原 spec，仅作诊断输出，不再用于择优**。
2. 对候选做 **pairwise 比较**（含正反两次消位置偏见）选出 winner —— **这是新的择优真值**。
3. 输出最佳候选、各候选诊断分、pairwise 比较记录、偏好对（供 DPO）。

---

## 2. 范围与非目标

**做：**
- 新增 pairwise 比较 prompt（与 pointwise 在**同一次 judge 调用**内产出，不新增第二次 LLM 往返）。
- 新增正反两次比较消位置偏见。
- 择优逻辑改为 `select_winner()` 调 `compare_pair()`；boundary 候选仍前置出局。
- 偏好对改由 pairwise 结果产出。
- schema 增量扩展，向后兼容。

**不做：**
- 不删除 EPITOME pointwise / CASEL / boundary 逻辑。
- 不改 F1/F2/F3 任何接口。
- 不实现 3 候选的两两比较聚合（`select_winner` 留扩展钩子，但 MVP 只处理 2 候选）。
- 不改 `weighted_total` 字段含义（它仍是 pointwise 加权分，仅供诊断）。

---

## 3. 关键设计决策

### 3.1 单次 judge 调用同时产出 pointwise + pairwise
延续 MVP "合并调用降成本"的纪律。一次调用让模型既给两条候选的 EPITOME/CASEL 分，又直接给出"哪条更好 + 理由"。

### 3.2 正反两次比较消位置偏见
LLM 倾向偏袒先出现的候选。因此对同一对候选跑两次：
- 第 1 次：候选顺序 (c1, c2)
- 第 2 次：候选顺序 (c2, c1)

判定规则：
- **两次都选同一条** → 该条稳定胜出（`pairwise_stable=true`）。
- **两次结论冲突**（各偏袒自己的位置，或一次平一次胜）→ 记为**平票/不稳定**（`pairwise_stable=false`），走 §5.3 兜底。

> 两次比较可在**同一次 judge 调用**里要求模型输出两个方向的判断，或拆两次调用。MVP 实现：**同一次调用内要求模型对 (c1,c2) 与 (c2,c1) 两种排列分别给结论**，避免两次往返。若模型对此不稳定，回退为两次独立调用（配置开关 `CRITIC_PAIRWISE_TWO_CALLS`，默认 `false`）。

### 3.3 boundary 仍优先于一切
任一候选 `boundary_flag=true` → 该候选直接出局，**不进入 pairwise**。
- 若仅一条越界 → 另一条直接为 winner（无需比较），偏好对仍生成（winner=未越界, loser=越界）。
- 若两条都越界 → 不择优，返回兜底（同原 spec §6）。

---

## 4. 配置项（在原 spec §6 基础上新增）

| 配置 | 建议初值 | 说明 |
|---|---|---|
| `CRITIC_DEEPSEEK_MODEL` | `deepseek-v4-pro` | critic 专用模型，与 F3 的 `deepseek-chat` 分离 |
| `CRITIC_LLM_MAX_TOKENS` | `4096` | 必须足够大：v4-pro 会先产 reasoning_content，token 不足会 `finish_reason=length` 导致 content 空、parse 失败 |
| `CRITIC_LLM_RESPONSE_FORMAT_JSON` | `True` | 强制 JSON 输出 |
| `CRITIC_PAIRWISE_TWO_CALLS` | `false` | 正反比较是否拆两次调用；默认单次调用内做两排列 |
| `CRITIC_SELECTION_MODE` | `pairwise` | `pairwise`（新默认）/ `pointwise`（回退到原 argmax 行为，便于对照实验） |

> `CRITIC_SELECTION_MODE=pointwise` 必须保留，作为 F9 对照实验的回退路径，也作为 pairwise 出问题时的安全网。

---

## 5. 改造后的择优逻辑

### 5.1 代码结构（扩展钩子）

把"比较一对"和"从候选集选 winner"拆成两个函数，为未来 3 候选留口子（MVP 不实现聚合）：

```python
def compare_pair(ctx, cand_a, cand_b) -> PairwiseResult:
    """对一对候选做正反两次比较，返回稳定胜者或平票。
    2 候选与未来多候选完全通用。"""
    ...

def select_winner(ctx, candidates, scores) -> SelectionResult:
    """MVP：先排除 boundary 候选；剩余恰好 2 条时调一次 compare_pair；
    剩余 1 条直接胜出；剩余 0 条走兜底。
    未来 3+ 候选：在此函数内加两两聚合，不改 compare_pair 与 prompt。"""
    ...
```

### 5.2 select_winner 流程（MVP）

```
1. 过滤掉 boundary_flag=true 的候选 → survivors
2. len(survivors) == 0  → 返回兜底（all_candidates_blocked），best=None，无偏好对
3. len(survivors) == 1  → winner=该条；若有被 boundary 淘汰的另一条，偏好对=(winner, 越界条)
4. len(survivors) == 2  → result = compare_pair(...)
     - result.stable == True  → winner=result.winner；偏好对=(winner, loser)
     - result.stable == False → 平票兜底（见 5.3）
5. len(survivors) >= 3   → MVP 未实现，抛 NotImplementedError（或按配置降级取前 2）
```

### 5.3 平票/不稳定兜底
当 `compare_pair` 两次结论冲突：
- **默认**：用 pointwise `weighted_total` 作 tiebreak（这正是诊断分仍有用的地方），取高分者为 winner，并标 `selection_method="pointwise_tiebreak"`。
- 若 pointwise 也相等 → 取 **共情型（c1）** 为默认 winner（情感辅导共情优先），标 `selection_method="orientation_default"`，**不生成偏好对**（无明确优劣，喂 DPO 会加噪）。

> 平票兜底用 pointwise 是合理的：pairwise 不稳时，pointwise 至少给一个有依据的方向，好过随机。但此时不产偏好对，避免把模糊样本喂进 DPO。

---

## 6. Pairwise 比较 Prompt（中文，可直接用）

在原 pointwise prompt 的同一次调用中追加 pairwise 部分。完整 prompt 结构：先给两条候选的 pointwise 打分指令（沿用原 spec §5），再追加：

```
————————————————
【第二部分：成对比较（这部分决定最终选择，请认真）】

现在请你忘掉具体打几分，直接判断：对这个孩子此刻的倾诉，下面两条回应哪一条更好？

"更好"的标准，按重要性排序：
1. 是否让孩子真正感到"被具体地看见"，而不是被一句放在谁身上都成立的万能话敷衍。
2. 是否准确接住了孩子没明说、但藏在话里的那层情绪或担忧。
3. 是否在不审问、不说教、不替别人开脱的前提下，温和地给了孩子一点继续表达或往前看的空间。
4. 语气是否像一个可信任、稍年长的朋友，而不是居高临下或打官腔。

请做两次独立判断，避免受顺序影响：

【判断一】先看回应甲，再看回应乙：
- 回应甲：{candidate_a_text}
- 回应乙：{candidate_b_text}
你的选择（"甲" 或 "乙" 或 "难分"）：

【判断二】先看回应乙，再看回应甲：
- 回应乙：{candidate_b_text}
- 回应甲：{candidate_a_text}
你的选择（"甲" 或 "乙" 或 "难分"）：

注意：
- 不要因为某条更长就觉得它更好。
- 只根据回应文本判断，不脑补没写出来的内容。
- 两次判断请各自独立，不要为了一致而强行对齐。

请把这部分追加进同一个 JSON 输出，字段如下：
{
  ...（前面 pointwise 的 ER/IP/EX/casel/boundary 字段，每条候选一份）...,
  "pairwise": {
    "judgment_1": "甲/乙/难分",     // 顺序 (甲,乙)
    "judgment_2": "甲/乙/难分",     // 顺序 (乙,甲)
    "reason": "一句话中文说明你为什么觉得胜出的那条更好"
  }
}
```

> 实现注意：prompt 里"甲/乙"是**展示顺序的占位**，代码侧负责把 c1/c2 映射到甲/乙，并在 judgment_2 中交换。解析时统一映射回 candidate_id。

---

## 7. pairwise 结果判定（代码侧）

把模型的两次判断映射回 candidate_id 后：

| judgment_1 | judgment_2 | 判定 |
|---|---|---|
| 同一条胜 | 同一条胜 | `stable=True`，winner=该条 |
| 一条胜 | 难分 | `stable=False`（弱不稳） |
| c1 胜 | c2 胜（即各偏位置） | `stable=False`（位置偏见，平票） |
| 难分 | 难分 | `stable=False`（模型认为难分） |

> 只有两次**指向同一条 candidate_id** 才算 stable。任何冲突或含"难分"都按 `stable=False` 走 §5.3 兜底。

---

## 8. Schema 增量（向后兼容）

在原 §3 输出基础上**新增**字段，不删旧字段：

```json
{
  "best_candidate_id": "c1",
  "selection_method": "pairwise_stable",   // 新增：pairwise_stable | pointwise_tiebreak | orientation_default | single_survivor | all_blocked
  "scores": [ ... 原 pointwise 诊断分，含 weighted_total，含义不变 ... ],
  "pairwise": {                            // 新增
    "winner_id": "c1",
    "stable": true,
    "judgment_1_winner_id": "c1",
    "judgment_2_winner_id": "c1",
    "reason": "甲准确点出了孩子怕让父母失望的那层心情，乙只是泛泛安慰。"
  },
  "preference_pair": {                     // 语义不变，但来源改为 pairwise
    "winner_id": "c1", "loser_id": "c2"
  }
}
```

字段说明：
- `selection_method`：记录 winner 是怎么定的，便于 F9 分析与调试。
- `scores[].weighted_total`：**仍计算并落库**，但仅作诊断 / tiebreak / F9 校验对象，**不再驱动择优**。下游/论文须明确：经 F9 前不作质量真值。
- `preference_pair`：仅当 `selection_method in {pairwise_stable, single_survivor}` 时生成；`pointwise_tiebreak` 也可生成（有明确高低）；`orientation_default` **不生成**。

> **数据库**：`candidates` 表无需改结构（pointwise 分照旧落库）。建议 `turns` 表新增列 `selection_method`（String）记录择优方式，便于后续抽取干净的 DPO 数据（只取 pairwise_stable 来源的偏好对）。若不想动表，可暂存进现有 JSON 字段。

---

## 9. 测试用例（在原 §7 基础上新增/调整）

| # | 场景 | 期望 |
|---|---|---|
| P1 | 两次判断都选 c1 | `selection_method=pairwise_stable`，winner=c1，偏好对(c1,c2) |
| P2 | judgment_1 选 c1、judgment_2 选 c2（位置偏见） | `stable=false`，走 pointwise tiebreak |
| P3 | 两次都"难分" | `stable=false`，pointwise tiebreak；若 pointwise 也平 → orientation_default，无偏好对 |
| P4 | c2 越界(boundary)、c1 正常 | 不进 pairwise，winner=c1，`selection_method=single_survivor`，偏好对(c1,c2) |
| P5 | 两条都越界 | best=None，all_blocked，无偏好对 |
| P6 | pointwise 分 c1 高但 pairwise 稳定选 c2 | winner=c2（**pairwise 优先于 pointwise**，验证真值来源切换） |
| P7 | `CRITIC_SELECTION_MODE=pointwise` | 回退到原 argmax 行为，pairwise 字段可空 |
| P8 | v4-pro 长 reasoning，max_tokens=4096 | 不出现 `finish_reason=length` / 空 content / parse 失败（回归 token 预算 bug） |
| P9 | 单次调用解析出 pointwise + pairwise 两部分 | 两部分都正确解析，缺任一按容错处理（pairwise 缺→降级 pointwise；pointwise 缺→该候选记最低诊断分） |

> P6 是这次改造的**核心回归用例**：必须证明 pairwise 结论能覆盖 pointwise 加权分。

---

## 10. 验收标准（DoD）

- [ ] critic 专用 client 接 `deepseek-v4-pro`，`CRITIC_LLM_MAX_TOKENS=4096`，`response_format=json`
- [ ] `compare_pair` / `select_winner` 拆分实现，2 候选走通；3+ 候选明确未实现（NotImplementedError 或配置降级）
- [ ] 正反两次比较产出，只有指向同一 candidate_id 才 `stable=true`
- [ ] boundary 候选前置出局，不进 pairwise
- [ ] 平票兜底按 §5.3：pointwise tiebreak → orientation_default；后者不产偏好对
- [ ] schema 新增 `selection_method`、`pairwise` 字段，旧字段全保留
- [ ] `weighted_total` 仍计算落库，但不驱动择优
- [ ] 偏好对仅在有明确优劣时生成（orientation_default 不生成）
- [ ] `CRITIC_SELECTION_MODE=pointwise` 回退路径可用（对照实验用）
- [ ] §9 全部用例通过，尤其 P6（pairwise 覆盖 pointwise）、P8（token 预算回归）
- [ ] F9 / rescore 脚本同步用 critic 专用模型

---

## 11. 与 F9 的衔接（务必写进论文方法链）

改造后，F9 信度校验要校验的**主对象从 pointwise 三维分变成 pairwise 偏好判断**：
- 人工对同一批候选对做 A/B 偏好标注（"哪条更好"，比标 0/1/2 更快更稳，标注成本反而下降）。
- 算人工 pairwise vs critic pairwise 的一致性（可用简单 agreement / Cohen's κ，对成对判断比 quadratically weighted κ 更直接）。
- pointwise 三维分仍可附带做一致性分析，作为"诊断维度可靠性"的补充证据。

> 论文叙事：pointwise→pairwise 的切换不是退步，而是"在具体任务上验证后选择更可靠的 judge 形态"——正是 Kumar & Groh (2025) 强调的 "validated on specific tasks with appropriate benchmarks" 的落地。
