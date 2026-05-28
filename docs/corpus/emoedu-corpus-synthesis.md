# 情感教育系统 · 合成语料方法文档

> **用途**：定义合成语料怎么造、字段怎么标、能力边界在哪。配套 `../overview/emoedu-development-framework.md` §7。
> **状态**：方法 + prompt 模板已就绪；已补充可执行生成/清洗/偏好对提取管线规划与脚本入口。批量结果需先跑 probe（试水批次）校准后再放量。

---

## 1. 这份语料是什么、不是什么

- **是**：用 LLM 按「倾诉者画像 × 情境」系统生成的、模拟初中生倾诉的对话素材。
- **不是**：真实初中生数据，也未经心理学专家审核。**无权威性**。
- **只服务两个用途**（见开发框架 §7）：① RAG 检索池；② 系统输入测试集。
- **绝不用于**：评估系统好坏的真值基准；无信度校验下的 DPO 唯一依据。
- **当前范围**：第一版只生成**单轮学生倾诉**，字段继续使用现有 `text`，兼容 `/chat` 与 45 条验收脚本。多轮历史一致性、跨轮危机信号累积样本留作后续工作，不混入本批常规语料。

---

## 2. 生成网格：5 画像 × 3 情境

画像（依据 ERQ-CA 情绪调节策略分型，见方案 md §七）：

| 画像 | 调节策略倾向 | 语言特征 |
|---|---|---|
| 压抑型 | 高表达抑制 | 短句、回避真实感受、「没事」「无所谓」 |
| 反刍型 | 高反刍 | 反复纠结、「为什么偏偏是我」 |
| 回避型 | 高回避 | 转移话题、不愿直面 |
| 外放型 | 高发泄、低重评 | 情绪激烈、指责、感叹号多 |
| 适应型 | 高重评、高求助 | 能表达、愿沟通（作正样本/对照） |

情境（初中生高频、文献支撑、不轻易触临床危机）：学业压力 / 同伴关系 / 亲子摩擦。

→ 5 × 3 = 15 个单元格，每格按需生成 N 条。

**格内多样性注入**：每个情境在 `docs/corpus/generation_config.json` 中预置 `subscenarios`（子情境变体）和全局 `variant_tags`（表达变体标签）。生成时每条样本从对应情境的子情境变体中轮换取值，并叠加表达变体标签写入 prompt；`prompts.jsonl` 同步记录 `subscenario`、`variant_tags` 与 `prompt_hash`。这里采用确定性轮换而非纯随机抽取，保证同一配置和 run 参数下可复现。

放量时不把最终目标定为「每格倾诉条数」，而定为**全网格合计 usable preference pairs**：

- 目标：约 1200 条 usable preference pairs。
- 最低可接受：1000 条。
- 软上限：1500 条。
- 不要求格间均匀；适应型作为正样本/对照，F4 更容易打平，偏好对偏少是预期，不为它强行补量。

第一阶段只跑 3 个代表格 probe（试水批次），每格 160 条原始倾诉：

1. 反刍型 × 同伴关系
2. 外放型 × 学业压力
3. 适应型 × 亲子摩擦

`probe-001` 已完成上述 3 格，共 480 条 raw、479 条 accepted、433 条 `judge_unverified_preference_pairs`。这 3 格保留不返工，production 初始放量只覆盖剩余 12 格。

`probe-001` 也暴露出一个限制：格内的事件文本可以很多样，但同一画像 × 情境下的心理结构和偏好模式可能高度同质。因此 production 不继续把每个格子堆到 160 条，而采用“先广覆盖、后定向补量”的策略：

- 剩余普通格：每格 80 条 raw。
- 剩余压抑型格：每格 96 条 raw（80 × 1.2 buffer）。
- 首轮 production quota 合计：1008 条 raw，见 `production_quota_after_probe_001.json`。
- 跑完后按 usable pair 数、DPO diversity 指标和人工抽查结果做定向补量；补量优先补心理-策略稀缺格，不按文本事件数机械补齐。

---

## 3. 每条语料的字段规范（保证来源可追溯）

```json
{
  "id": "syn_0001",
  "persona": "压抑型",
  "persona_basis": "ERQ-CA: 高表达抑制",
  "scenario": "学业压力",
  "turns": [
    {"role": "student", "text": "……"},
    {"role": "system_response", "text": "……（可留空，仅作输入测试时）"}
  ],
  "gen_model": "deepseek-xxx",
  "gen_prompt_version": "v1",
  "intended_use": "rag_pool | test_input",
  "human_checked": false,
  "check_note": ""
}
```

> `persona_basis` / `gen_prompt_version` 字段就是「来源可追溯」的落地——论文里可据此说明语料的理论生成逻辑，而非「凭空捏造」。

---

## 4. 合成 prompt 模板（可直接用，待验收）

> 生成的是**倾诉者（学生）的话**，不是系统回应。用于填 RAG 池和测试输入。

```
你要扮演一名中国初中生（12–15 岁），向一个倾诉对象讲述自己的困扰。

【性格与情绪调节方式】{persona_desc}
（例：你习惯压抑自己的感受，不太愿意直接说出心里难受，常用"没事""无所谓"带过，但字里行间能感到你其实很在意。）

【困扰情境】{scenario_desc}
（例：这次月考成绩退步很多，你感到压力和挫败。）

【要求】
1. 用初中生真实、口语化的中文表达，符合上述性格。
2. 只输出学生的倾诉内容，1–5 句、20–180 字，不要写对方的回应。
3. 不要刻意煽情或夸张，贴近真实初中生的语气。
4. 不涉及自伤、自杀等危机内容（这类样本单独、谨慎处理，不在常规生成内）。

直接输出这段倾诉：
```

> **⚠️ 危机样本单列**：测试安全门需要「黄/红」级输入样本，但这类样本要极其谨慎生成、单独标注、限制用途（仅供内部测安全门），**绝不混入 RAG 池**。生成策略 🚧 后续单独盘，不在本批常规语料内。

---

## 5. 质量校验（合理性，非信效度）

- 小样本抽查（如每格抽 2–3 条，共 30–45 条），人工判断「像不像真实初中生在该情境下会说的话」。
- 记录通过率，写入论文方法（诚实数字，非权威背书）。
- 🚧 进阶（最强）：找少量真实、公开、合规的中文青少年情感对话，比对长度/情绪词/话题分布，做分布锚定。资源待查。

批量管线还必须做以下自动清洗：

1. **机械校验**：字段完整、1–5 句、20–180 字直接进入 accepted 候选；181–220 字在 F1 green 后进入 `length_review.jsonl` 复核/修短队列，不进入 accepted 或 `/chat`；少于 20 字或超过 220 字拒绝；无系统回应/教师提示/开发者提示痕迹。
2. **显式危机词拦截**：自伤、自杀、活着没意思、不想存在、消失算了等文本先进入隔离集。
3. **F1 安全门清洗**：每条倾诉都以 `history=[]`、`current_message=text` 调用 F1；凡 `risk_level != green` 或 F1 调用异常，进入 `quarantine_safety_only.jsonl`，不得进入常规 RAG/test/DPO 池。
4. **去重**：同格近重复优先剔除，全局高相似样本进入复核。放量到每格百条以上时，重复是主要损耗来源。
5. **人工抽查**：只抽查合理性，不把本语料声明为真实青少年数据或权威真值。

从原始倾诉到 preference pair 的损耗链按 probe（试水批次）实测，不使用拍脑袋固定系数。记录：

```text
accepted_rate = accepted / raw
pair_rate = preference_pairs / accepted
overall_yield = preference_pairs / raw
```

偏好对还必须记录 **DPO diversity**，用于判断偏好信号是否过度单一。该统计不新增 LLM 评估，只读取现有 F4 输出：

- winner/loser 分布：例如 `c2 > c1` 与 `c1 > c2` 的比例。
- score delta 分布：赢家 `weighted_total` 减输家 `weighted_total`。
- EX/CASEL 差异：赢家与输家在探索维度、CASEL 平均分上的差值。
- cell pair pattern：每个画像 × 情境下的 winner/loser 模式。

若低于目标，先看缺口来自 yield 不足还是 DPO diversity 不足：前者可补高 yield 的非适应型格子，后者应优先补心理-策略稀缺格或改进 F3 候选策略，而不是单纯继续堆同质倾诉。若超过软上限，保留全集，训练导出时再确定性降采样。

压抑型样本因为短句、回避和信息量低，F4 也可能更容易打平。它不额外加入 3 格 probe（试水批次），但 production（放量生产）阶段默认给压抑型 3 格增加 20% buffer（缓冲量）作为初始 quota（生成配额）余量。若压抑型最终偏好对仍偏少，可与适应型一样记录为预期内低产，不强行按格补齐。

---

## 6. 可执行管线

术语：

- **probe（试水批次）**：先选少量代表格跑完整链路，用来实测清洗、去重、`/chat` 产偏好对的真实损耗率，再决定是否放量。
- **quota（生成配额）**：放量阶段给每个「画像 × 情境」格子分配的原始倾诉生成数量。它可以按格不同，不强求每格均摊。

配置文件：`docs/corpus/generation_config.json`。

脚本入口：

```powershell
# 1. 3 格 probe dry-run，不调用真实 LLM
python -m scripts.corpus.synthesize_corpus --run-id probe-YYYYMMDD --mode probe --dry-run --per-cell 2

# 2. 真实 LLM 生成 probe；默认 probe_per_cell=160
python -m scripts.corpus.synthesize_corpus --run-id probe-YYYYMMDD --mode probe --resume

# 3. F1 清洗 + 去重
python -m scripts.corpus.validate_corpus --raw-path docs/corpus/runs/probe-YYYYMMDD/raw.jsonl --output-dir docs/corpus/runs/probe-YYYYMMDD/validated

# 4. 喂 /chat 提取 usable preference pairs
python -m scripts.corpus.extract_preference_pairs --accepted-path docs/corpus/runs/probe-YYYYMMDD/validated/accepted.json --output-dir docs/corpus/runs/probe-YYYYMMDD/pairs --run-id probe-YYYYMMDD

# 5. probe-001 后的首轮 production：只覆盖剩余 12 格
python -m scripts.corpus.synthesize_corpus --run-id production-YYYYMMDD --mode production --quota-file docs/corpus/production_quota_after_probe_001.json --resume
```

主要产物：

- `raw.jsonl`：原始生成倾诉。
- `prompts.jsonl`：prompt、prompt hash、子情境与变体标签。
- `accepted.json`：F1 green、机械有效、去重后的单轮倾诉。
- `rejected.jsonl`：非安全原因拒绝样本。
- `quarantine_safety_only.jsonl`：显式或 F1 判出的危机/疑似危机样本，只能供安全门测试或人工复核。
- `length_review.jsonl`：F1 green 但 181–220 字的偏长样本，只能人工修短后重新跑 `validate_corpus`，不得直接进入 RAG/test/DPO 池。
- `chat_results.jsonl`：完整 `/chat` 响应。
- `preference_pairs.jsonl`：`status=answered` 且存在 `preference_pair` 的可用偏好对。
- `summary_pairs.md`：偏好对数量、pair rate 与 DPO diversity 统计。

所有生成运行目录位于 `docs/corpus/runs/`，默认不提交。人工确认后的 curated corpus 再单独导出为可提交文件。

---

## 7. DPO 与信度边界

本批偏好对来自 F4 critic 自动判分。正式用于 DPO 训练前，必须完成 F9 信度校验；在此之前只能称为 `judge_unverified_preference_pairs`，不能作为已验证偏好真值。

合成语料可用于内部回归、RAG 候选池、系统输入压力测试和生成偏好对候选，但不得作为系统效果评估的真实真值。

---

## 8. 待验收 / 待执行

- [ ] **你验收**：§4 prompt 模板方向对不对？语气、长度、约束是否符合预期；现有 `emoedu-corpus-45-samples.json` 的 45 条 `text` 只作为风格基线参照，不是本批脚本的生成结果。
- [x] 先跑 3 个代表格 probe（试水批次），每格 160 条，实测损耗率。
- [x] 根据 `overall_yield` 校准剩余格子的生成 quota（生成配额），首轮 production quota 见 `production_quota_after_probe_001.json`。
- [ ] 跑剩余 12 格首轮 production，并根据 DPO diversity 做定向补量。
- [ ] F3 候选策略多样性改进：在正式 DPO 前，评估是否需要加入更多回应策略候选，避免偏好对长期退化为固定 `c2 > c1` 模式。
- [ ] 危机样本生成策略单独设计（谨慎）
- [ ] 分布锚定的真实语料资源调研
