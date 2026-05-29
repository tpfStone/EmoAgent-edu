# F9 信度校验 · 详细执行文档

> **这是什么**：F9 = 用极小规模人工标注，验证 F4 critic 的 LLM 判断与人工判断一致。它是论文里「LLM-judge 在本任务可靠」这句话的**唯一证据**，也是放量与 DPO 的前置闸门。
> **配套**：当前执行状态见 `../corpus/f9/README.md`；评分定义见 `f4-critic-epitome.md` §4；pairwise 目标见 `f4-pairwise-selection.md`。
> **一句话**：没有这份校验，DPO 和系统效果的所有结论都站不住（AI 教 AI 无锚点）。

---

## 当前状态 / 已完成 / 待办 / 后续计划

**当前状态**：本文同时保留旧 pointwise EPITOME 信度校验方法，并明确新的 pairwise F9 主线。按 `docs/corpus/f9/README.md` 的当前判定，正式人工 F9 仍暂停：旧 pointwise validation 主包单次 PASS，但稳定性复跑未通过；pairwise pilot 工具链可用但 Phase A rerun 结论为 `inconclusive`。

**已完成**：
- 第一轮 F9 基线产物已在 `../corpus/f9/baseline/` 保存。
- pointwise 自动验收、稳定性复跑、post-erip 多轮诊断产物已在 `../corpus/f9/validation*` 保存。
- F4 已根据 F9 差集分析收紧 ER/IP 定义、加入 audit tags 与代码侧 cap。
- pairwise 离线工具链、Phase A rerun 输入/输出与报告已在 `../corpus/f9/pairwise-selection-pilot/` 保存。

**待办**：
- 不直接启动新的人工 F9，直到 pairwise rerun 通过预设 gate，或项目明确批准新的 F9 gate 口径。
- 当前推荐主线是 pairwise F9：验证成对偏好判断与人工 A/B 是否一致。
- Pointwise ER/IP/EX 只作为诊断线保留；若继续 pointwise，需要先解决 ER/IP 高分饱和与稳定性问题，再冻结新盲标包。

**后续计划入口**：
- F9 总览：`../corpus/f9/README.md`
- Pointwise 诊断记录：`../corpus/f9/pointwise-diagnostics/execution-summary.md`
- Pairwise 当前结论：`../corpus/f9/pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md`
- F4 pointwise 规格：`f4-critic-epitome.md`
- F4 pairwise 目标规格：`f4-pairwise-selection.md`

## 0. 当前 F9 要回答的主问题

> **F4 critic 做成对偏好判断时，是否与人工 A/B 偏好一致？**

「可信」的操作化定义：在同一批冻结候选对上，critic pairwise winner/tie/invalid 与人工 A/B 标注达到预设一致性门槛；不稳定、tie、invalid 或 `pairwise_unresolved` 样本不得进入 DPO。

Pointwise EPITOME 0/1/2 信度仍有价值，但它现在是诊断问题：用于解释旧实现、定位 ER/IP 高分饱和和保留论文 limitation，不再作为 DPO 解锁的主 gate。

注意 F9 **不是**：不是评回复质量好坏（那是别的事），不是给 45 条逐条打分，不是 MVP 的「回复合理性排雷」。F9 是**信度**（reliability）验证——量的是「judge 准不准」，不是「东西好不好」。

---

## 0.1 Pairwise F9 执行框架（当前主线，高层框架）

> **状态说明**：本节只固定 pairwise F9 的目标对象、基本纪律和核心指标；新一轮可直接执行的详细 rerun 方案尚未冻结。实际开跑前必须另写或更新 pairwise rerun plan，明确样本冻结规则、样本量、tie/invalid 处理、人工一致性口径和 go/no-go 阈值。

### 标注对象

**候选对**。每条样本包含同一用户倾诉、同一上下文和两条候选回应。人工标注者只回答：A 更适合、B 更适合、难分/tie、无效/越界。

### 数据来源

- `../corpus/f9/pairwise-selection-pilot/inputs/phase-a-rerun/` 的候选对和 manifest。
- 后续 rerun 重新冻结的候选包。必须记录模型、prompt hash、候选来源、生成配置和 pair_id。

### 标注纪律

- [ ] 人工看不到 critic pairwise 结果、pointwise 分数和 candidate_id 原始标签。
- [ ] 至少两名标注者独立标注；先算人工间一致性，再算人工-critic 一致性。
- [ ] 保留 tie 和 invalid，不强行转成 winner/loser。
- [ ] 亲子/同伴场景中涉及第三方动机推测的样本单独标记，避免混淆候选质量问题和 judge 问题。

### 指标

- `valid_pair_count`：进入比较的有效人工样本数量，必须达到 rerun plan 预设下限。
- `human_human_agreement`：人工之间的一致性，用作人机一致性的上限参照。
- `critic_human_agreement`：critic pairwise 与人工共识的一致性。
- `agreement_delta_vs_pointwise`：pairwise 相对 pointwise baseline 是否改善。
- `position_bias_controls`：physical swap、hidden label、identical text 等控制实验结果。

通过线必须在 rerun plan 中先写死，不能看结果后调整。

---

> **旧方案边界**：以下 §1-§6 以及 §8 的 checklist 是旧 pointwise EPITOME 0/1/2 信度校验方案，当前只保留为历史复盘、诊断线和论文 limitation 参考。它不是当前 pairwise F9 的可执行详细方案，也不能单独解锁 `/chat` pairwise runtime 或 DPO。

## 1. Pointwise 旧方法：抽样、标什么、抽多少、怎么抽

以下方法保留用于旧 EPITOME 0/1/2 诊断。它不再直接解锁 DPO。

### 标注对象

**候选回应**（不是情境、不是偏好对）。每条候选在「给定用户倾诉 + 历史」语境下，被标 ER/IP/EX 三维各 0/1/2。

### 数据来源（现成，不用等放量）

- `real-llm-20260522-215717` 的 90 条候选（45 情境 × 2 取向）。
- probe 的 433 对里的候选（含 F4 打分）。

### 抽多少

**30-50 条候选**（对标原论文量级，也是 mas-plan §十建议）。建议 **40 条**，留点余量。

### 怎么抽（抽样设计决定 κ 可信度）

- [ ] **跨情境分层**：学业压力 / 同伴关系 / 亲子摩擦各抽约 1/3，别全抽一类。
- [ ] **跨取向分层**：情感共情型、认知共情型各占一半。新 c2 不再是旧“引导反思型”，不要预设其 EX 分布更宽；EX 的方差应通过覆盖 F4 分数梯度和边界样本来保证。
- [ ] **覆盖分数梯度**：从 F4 打分里，高分/中分/低分候选都要抽到。**别只抽 F4 给高分的**——如果样本里 ER/IP/EX 全是 2，κ 会因为「方差太小」算出虚低或无意义的值（一致性指标在分数无变化时失效）。
- [ ] **故意纳入边界候选**：抽几条 F4 标了 `boundary_flag=true` 的，以及亲子/同伴里「替第三方猜动机」的候选（已知噪声）——这些是人机最可能分歧的地方，纳入才能暴露真实一致性。

> **抽样脚本建议**：从 `candidates` 表按 (scenario, orientation, weighted_total 分桶) 分层随机抽 40 条，导出成一张待标注表。固定随机种子，可复现。

---

## 2. 标注前：先对齐评分锚点（30 分钟，必做）

标注者（你 + 至少一名队友）开标前，一起做这件事，否则 κ 测的是「你俩理解不一致」而非「人机不一致」。

- [ ] 一起读 `f4-critic-epitome.md` §4 的三维 0/1/2 定义。
- [ ] **共标 5 条练习样本**（不计入正式 40 条），逐条对答案、讨论分歧，直到对锚点理解一致。
- [ ] 特别对齐三个易错点：
  - **EX 的 0 vs 1**：「关闭对话/转移」是 0，「没主动探索但也没关闭」是 1。容易混。
  - **IP 的 1 vs 2**：「复述表面事实」是 1，「点出未明说的情绪」是 2。这条最主观，务必对齐。
  - **ER 的 1 vs 2**：「礼貌泛泛（别难过）」是 1，「具体真诚」是 2。

> 这 5 条练习不进正式集——它们的作用是校准人，不是校准 F4。

---

## 3. 标注纪律（决定 κ 是否可信）

- [ ] **盲标**：标注时**看不到 F4 的打分**。导出待标注表时只留 (倾诉, 历史, 候选文本)，**删掉 F4 的 ER/IP/EX 列**。看到了就会无意识对齐，κ 虚高，论文一文不值。
- [ ] **独立标**：两名标注者**各标各的，先不互通**。这样能同时算出两个 κ（见 §4）。
- [ ] **只依文本**：不脑补候选没写出的内容（和 F4 prompt 同一条原则）。
- [ ] **逐维独立**：ER/IP/EX 分开判，不要让一维的印象带跑另一维。

### 待标注表结构（示例）

| sample_no | scenario | orientation | 用户倾诉 | 对话历史 | 候选文本 | 标注者A_ER | A_IP | A_EX | 标注者B_ER | B_IP | B_EX |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 同伴关系 | 情感共情型 | … | … | … | | | | | | |

> F4 的分**单独存一张表**，标注全部完成后再合并比对。两表用 sample_no 对齐。

---

## 4. 算什么：三个 κ，别只算一个

用 **quadratically weighted Cohen's κ**（二次加权）。0/1/2 是有序量纲，普通 κ 把「标2 vs 标1」和「标2 vs 标0」当成同样的错，会低估一致性；加权 κ 让「差得越远扣得越多」，才对，也对标原论文。

三个要算的 κ：

1. **人人一致性（A vs B）**：两名人工标注者之间。这是「这套锚点人能不能标稳」的证据，也是人机一致性的天花板参照。
2. **人机一致性（人 vs F4）**：核心指标。用「两人的共识标注」或「两人均值取整」对 F4。**这是论文要报的主数字。**
3. **逐维分开**：ER、IP、EX 各算一套上面两个 κ。**不要只报三维合并的总 κ**——因为你预期 EX 高、ER/IP 低（见 §5），合并会掩盖这个结构。

### 可直接跑的计算代码

```python
# pip install scikit-learn pandas
import pandas as pd
from sklearn.metrics import cohen_kappa_score

# 读入：每行一个候选，列含 A_ER,A_IP,A_EX,B_ER,B_IP,B_EX,F4_ER,F4_IP,F4_EX
df = pd.read_csv("f9_annotations_merged.csv")

def wk(y1, y2):
    # quadratic weighted kappa
    return cohen_kappa_score(y1, y2, weights="quadratic", labels=[0, 1, 2])

# 人机共识：两人一致时用一致值；不一致时用均值四舍五入（或开会定夺，记录下来）
for dim in ["ER", "IP", "EX"]:
    a, b, f4 = df[f"A_{dim}"], df[f"B_{dim}"], df[f"F4_{dim}"]
    consensus = ((a + b) / 2).round().astype(int)  # 简化共识；分歧大的建议人工复核
    print(f"=== {dim} ===")
    print(f"  人人 (A vs B)   weighted κ = {wk(a, b):.3f}")
    print(f"  人机 (共识 vs F4) weighted κ = {wk(consensus, f4):.3f}")

# 同时报告每维的分数分布，证明方差足够（避免虚低κ）
for dim in ["ER", "IP", "EX"]:
    print(f"{dim} F4分布:", df[f"F4_{dim}"].value_counts().sort_index().to_dict())
```

> **若 CASEL 维也标了**：同法分维算。但 MVP 阶段 CASEL 是辅助项，EPITOME 三维的 κ 才是论文主体。

---

## 5. 预期会遇到的：ER/IP 偏低，这是已知局限不是 bug

文档已多处诚实预告（`f4-critic-epitome.md` §2、`emoedu-development-framework.md` §4）：原论文里 EPITOME 的 **ER、IP 两维操作定义不清、专家可靠性偏低，只有 EX 较高**。

所以你大概率会看到：**EX 的 κ 不错，ER/IP 偏低。** 这是 EPITOME 框架本身的性质，不是你的系统坏了。

### 怎么处理（这是方法严谨性，不是遮丑）

- **你已做的缓解**：F4 spec §4 对 ER/IP 补了更明确的中文操作定义。
- **论文这样写**：
  > 「针对 EPITOME 原框架 ER/IP 维可靠性偏低的已知问题（Kumar & Groh 2025），我们补充了面向初中生场景的中文操作定义。F9 校验显示 EX 维 weighted κ = [X]（substantial），ER/IP 维 = [Y/Z]（moderate）。我们在 limitation 中如实讨论 ER/IP 的残余局限，并指出其根源在框架本身的操作化困难而非本系统实现。」
- **主动承认 + 给出缓解 + 归因到框架 = 审稿人眼里的严谨**，而非漏洞。

### 反向警惕

如果三维 κ **都异常高**（比如全 >0.85），别急着高兴——先查：
- 标注者是不是偷看了 F4 的分？（违反 §3 盲标）
- 样本是不是分数方差太小（全是 2）导致 κ 失真？（违反 §1 分数梯度）

---

## 6. 判读线：到什么数算过

weighted κ 的常用解读（Landis & Koch）：<0.2 slight，0.2-0.4 fair，0.4-0.6 moderate，0.6-0.8 substantial，>0.8 almost perfect。

### Pointwise 诊断通过标准（不直接解锁 DPO）

- [ ] **EX 维人机 κ ≥ 0.6**（substantial）。EX 是 EPITOME 里最可靠的维，它要是不达标，整个 judge 的可信度存疑。
- [ ] **ER/IP 维人机 κ ≥ 0.4**（moderate），并在 limitation 诚实讨论。
- [ ] **人人 κ 不显著低于人机 κ**。如果人人之间都标不一致（人人 κ 很低），说明锚点本身有问题，要回 §2 重新对齐，而不是怪 F4。
- [ ] 报告时**三维分开 + 附分数分布**，不藏 ER/IP。

### 如果不达标

- **EX 都不达标** → F4 的 EPITOME prompt 或评分逻辑有真问题，回查 F4 §5 prompt，改完**重测 F9**（不是重标人工，是重跑 F4 再比）。
- **只有 ER/IP 低、EX 达标** → 可投，按 §5 写 limitation。这是预期内的，不算 F9 失败。
- **人人 κ 低** → 不是 F4 的问题，是你俩没对齐，回 §2。

> **F4 一旦因 F9 修改 → 所有用旧 F4 跑的 pointwise 偏好对都只能保留为历史诊断产物**（含 probe 433 对），不得直接进 DPO。新的训练数据必须来自通过 pairwise gate 的稳定偏好对。

---

## 7. F9 的产出（直接进论文）

### Pairwise 主产出

1. **一张 A/B 一致性表**：人工间一致性、critic-human agreement、pointwise baseline、delta、有效样本数。
2. **一段方法描述**：冻结候选包、盲标、正反顺序控制、tie/invalid 保留、位置偏差控制实验。
3. **一段 go/no-go 结论**：是否允许 `pairwise_stable` 偏好对进入 DPO 候选池。
4. **一段 limitation**：若存在 `c1` 偏斜、有效交集不足或场景偏差，必须如实写入。

### Pointwise 附属产出

1. **一张 κ 表**：行=ER/IP/EX，列=人人 κ、人机 κ，附每维分数分布。
2. **一段诊断描述**：解释 ER/IP 高分饱和、EX 相对更可靠、pointwise 不再作为 DPO 主判据。
3. **一段 limitation**：ER/IP 残余局限 + 归因框架。

---

## 8. Pointwise 旧执行清单（仅诊断/参考）

- [ ] 写抽样脚本，分层抽 40 条候选，固定种子，导出盲标表（删 F4 分列）。
- [ ] 标注者一起读 §4 定义 + 共标 5 条练习对齐锚点。
- [ ] 两人独立盲标 40 条 ER/IP/EX。
- [ ] 合并三表（A、B、F4）按 sample_no 对齐。
- [ ] 跑 §4 代码，得三维 × 人人/人机 κ + 分数分布。
- [ ] 对照 §6 判读：EX≥0.6？ER/IP≥0.4？人人不低于人机？
- [ ] 达标 → 写 §7 的 pointwise 附属产出；若未同步通过 pairwise gate，不解锁 DPO。
- [ ] 不达标 → 按 §6 分支处理（改 F4 重测 / 重对齐锚点 / 写 limitation）。

---

## 9. 常见误区（别踩）

- ❌ 用普通 κ 而非加权 κ —— 低估有序量纲一致性。
- ❌ 只报三维合并 κ —— 掩盖 ER/IP 低、EX 高的真实结构。
- ❌ 标注时能看到 F4 分 —— κ 虚高，证据失效。
- ❌ 样本分数全是 2 —— κ 失真，必须有梯度。
- ❌ 把 F9 当质量评估 —— F9 是信度（标尺准不准），不是质量（东西好不好）。
- ❌ ER/IP 低就判 F9 失败 —— 那是 EPITOME 已知局限，EX 达标即可投 + 写 limitation。
- ❌ F9 没过就放量 —— 用未验证 F4 铸的币可能全废。
