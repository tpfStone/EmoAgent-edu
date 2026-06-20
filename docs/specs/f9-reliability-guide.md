# F9 信度校验 · 详细执行文档

> **这是什么**：F9 = 用小规模人工标注，验证 F4 critic 与人工判断的一致性。当前主线是 pairwise/human A/B gate；EPITOME 0/1/2 pointwise 信度只作为诊断线和历史兼容证据。
> **配套**：上层路线见 `emoedu-post-mvp-guide.md` 的 P1；评分定义见 `f4-critic-epitome-codex-spec.md` §4；理论依据见 `emoedu-mas-plan.md` §十。
> **一句话**：没有人工锚点，DPO 和系统效果的结论都站不住（AI 教 AI 无锚点）。正式 DPO 依赖 pairwise/human A/B gate，不由 pointwise EPITOME 单独解锁。

---

## 0. F9 当前要回答的问题

当前主问题：

> **对同一批候选对，critic pairwise 的偏好判断是否与人工 A/B 偏好达到可接受一致性？**

历史/诊断问题仍可保留：

> **F4 critic 用 EPITOME 0/1/2 给候选回应打的分，是否与人工标注大体一致？**

Pointwise 的操作化定义：F4 的 ER/IP/EX 打分与人工标注的一致性达到可解释水平（见 §6 诊断线），并对标原论文（Kumar & Groh 2025）报告同类指标。它可以支撑后台质量标签、session guidance 和旧记录解释，但不能单独解锁 runtime pairwise selector、production 放量或正式 DPO。

注意 F9 **不是**：不是评回复质量好坏（那是别的事），不是给 45 条逐条打分，不是 MVP 的「回复合理性排雷」。F9 是**信度**（reliability）验证——量的是「标尺准不准」，不是「东西好不好」。

---

## 1. Pointwise 诊断抽样：标什么、抽多少、怎么抽

### 标注对象

**候选回应**（不是情境、不是偏好对）。每条候选在「给定用户倾诉 + 历史」语境下，被标 ER/IP/EX 三维各 0/1/2。

### 数据来源（现成，不用等放量）

- `real-llm-20260522-215717` 的 90 条候选（45 情境 × 2 取向）。
- probe 的 433 对里的候选（含 F4 打分）。

### 抽多少

**30-50 条候选**（对标原论文量级，也是 mas-plan §十建议）。建议 **40 条**，留点余量。

### 怎么抽（抽样设计决定 κ 可信度）

- [ ] **跨情境分层**：学业压力 / 同伴关系 / 亲子摩擦各抽约 1/3，别全抽一类。
- [ ] **跨取向分层**：共情型、引导反思型各占一半。引导反思型的 EX 分布更宽，对 EX 维的 κ 估计更有意义。
- [ ] **覆盖分数梯度**：从 F4 打分里，高分/中分/低分候选都要抽到。**别只抽 F4 给高分的**——如果样本里 ER/IP/EX 全是 2，κ 会因为「方差太小」算出虚低或无意义的值（一致性指标在分数无变化时失效）。
- [ ] **故意纳入边界候选**：抽几条 F4 标了 `boundary_flag=true` 的，以及亲子/同伴里「替第三方猜动机」的候选（已知噪声）——这些是人机最可能分歧的地方，纳入才能暴露真实一致性。

> **抽样脚本建议**：从 `candidates` 表按 (scenario, orientation, weighted_total 分桶) 分层随机抽 40 条，导出成一张待标注表。固定随机种子，可复现。

---

## 2. 标注前：先对齐评分锚点（30 分钟，必做）

标注者（你 + 至少一名队友）开标前，一起做这件事，否则 κ 测的是「你俩理解不一致」而非「人机不一致」。

- [ ] 一起读 `f4-critic-epitome-codex-spec.md` §4 的三维 0/1/2 定义。
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
| 1 | 同伴关系 | 共情型 | … | … | … | | | | | | |

> F4 的分**单独存一张表**，标注全部完成后再合并比对。两表用 sample_no 对齐。

---

## 4. 算什么：三个 κ，别只算一个

用 **quadratically weighted Cohen's κ**（二次加权）。0/1/2 是有序量纲，普通 κ 把「标2 vs 标1」和「标2 vs 标0」当成同样的错，会低估一致性；加权 κ 让「差得越远扣得越多」，才对，也对标原论文。

三个要算的 κ：

1. **人人一致性（A vs B）**：两名人工标注者之间。这是「这套锚点人能不能标稳」的证据，也是人机一致性的天花板参照。
2. **人机一致性（人 vs F4）**：pointwise 诊断指标。用「两人的共识标注」或「两人均值取整」对 F4。**这是后台质量标签和旧 pointwise 可靠性要报的数字，不是 DPO 解锁数字。**
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

文档已多处诚实预告（`f4-critic-epitome-codex-spec.md` §2、`emoedu-development-framework.md` §4）：原论文里 EPITOME 的 **ER、IP 两维操作定义不清、专家可靠性偏低，只有 EX 较高**。

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

### Pointwise 诊断通过标准（比赛可投档）

- [ ] **EX 维人机 κ ≥ 0.6**（substantial）。EX 是 EPITOME 里最可靠的维，它要是不达标，整个 judge 的可信度存疑。
- [ ] **ER/IP 维人机 κ ≥ 0.4**（moderate），并在 limitation 诚实讨论。
- [ ] **人人 κ 不显著低于人机 κ**。如果人人之间都标不一致（人人 κ 很低），说明锚点本身有问题，要回 §2 重新对齐，而不是怪 F4。
- [ ] 报告时**三维分开 + 附分数分布**，不藏 ER/IP。

以上只说明 pointwise EPITOME 诊断可被引用。正式 DPO 或 runtime pairwise selector 还必须另过 pairwise/human A/B gate：

- [ ] 有效交集数量达到预设下限。
- [ ] critic-human agreement 达到预设线，且优于或至少不弱于 pointwise baseline。
- [ ] 位置偏见、hidden label、identical text 和 `c1` 偏斜控制没有失败。
- [ ] 只导出 `pairwise_stable` 且 `human_validated` 的 winner/loser；tie、invalid、unresolved、orientation default 和 pointwise tiebreak 不进入训练。

### 如果不达标

- **EX 都不达标** → F4 的 EPITOME prompt 或评分逻辑有真问题，回查 F4 §5 prompt，改完**重测 F9**（不是重标人工，是重跑 F4 再比）。
- **只有 ER/IP 低、EX 达标** → 可投，按 §5 写 limitation。这是预期内的，不算 F9 失败。
- **人人 κ 低** → 不是 F4 的问题，是你俩没对齐，回 §2。

> **F4 一旦因 F9 修改 → 所有用旧 F4 跑的诊断分数和未验证偏好对都要重新标注来源**（含 probe 433 对）。正式 DPO 仍以 pairwise/human gate 的稳定偏好对为准。

---

## 7. F9 的产出（直接进论文）

1. **一张 κ 表**：行=ER/IP/EX，列=人人 κ、人机 κ，附每维分数分布。
2. **一段方法描述**：抽样设计（40 条、分层、盲标、独立标）、加权 κ、对标原论文。
3. **一段 limitation**：ER/IP 残余局限 + 归因框架。
4. **一句结论**：「F4 critic 的 EPITOME 打分在本任务上达到与人工可比的一致性（EX substantial，ER/IP moderate），可作为后台质量诊断和历史 pointwise 解释证据。」
   - **这句话不能解锁 `judge_unverified_preference_pairs`**。放量与 DPO 只能在 pairwise/human A/B gate 通过后，使用 `pairwise_stable` / `human_validated` 来源的偏好对。

---

## 8. 执行清单（按顺序勾）

- [ ] 写抽样脚本，分层抽 40 条候选，固定种子，导出盲标表（删 F4 分列）。
- [ ] 标注者一起读 §4 定义 + 共标 5 条练习对齐锚点。
- [ ] 两人独立盲标 40 条 ER/IP/EX。
- [ ] 合并三表（A、B、F4）按 sample_no 对齐。
- [ ] 跑 §4 代码，得三维 × 人人/人机 κ + 分数分布。
- [ ] 对照 §6 判读：EX≥0.6？ER/IP≥0.4？人人不低于人机？
- [ ] Pointwise 诊断达标 → 写 §7 产出，作为后台质量报告和历史兼容证据。
- [ ] Pairwise/human gate 达标 → 才允许导出 stable/human_validated preference pairs，启动后续 production/DPO 准备。
- [ ] 不达标 → 按 §6 分支处理（改 F4 重测 / 重对齐锚点 / 写 limitation）。

---

## 9. 常见误区（别踩）

- ❌ 用普通 κ 而非加权 κ —— 低估有序量纲一致性。
- ❌ 只报三维合并 κ —— 掩盖 ER/IP 低、EX 高的真实结构。
- ❌ 标注时能看到 F4 分 —— κ 虚高，证据失效。
- ❌ 样本分数全是 2 —— κ 失真，必须有梯度。
- ❌ 把 F9 当质量评估 —— F9 是信度（标尺准不准），不是质量（东西好不好）。
- ❌ ER/IP 低就判所有 F9 失败 —— 那是 EPITOME 已知局限；pointwise 诊断可分维报告，但不能替代 pairwise gate。
- ❌ Pairwise/human gate 没过就放量或 DPO —— 用未验证 F4 铸的币可能全废。
