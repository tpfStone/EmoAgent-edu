# EmoEdu 后续开发指南

> **当前定位**：本文是比赛投稿和应用端更新的工作图，不再沿用“每轮完整同步 F1-F4 再择优”的旧推进口径。
> **核心判断**：产品在线路径必须保持轻量，当前 `/chat` 已调整为首次 `F1 -> F2 -> F3 -> 流式返回 -> 后台 F4`，后续轮次走轻量 CBT 支持。F4 pairwise 与 DPO 仍是研究主线，但未通过人工校准前不进入在线阻塞路径。
> **关键路径**：P0 快路径稳定 -> P1 应用端体验更新 -> P2 后台 F4 guidance 与研究台观测 -> P3 pairwise/人工校准 -> P4 DPO + 消融。短期优先把学生端体验做顺，不把完整研究链路压到在线响应里。

---

## 0. 当前位置

### 已经成立的事实

- `/chat` 运行时已改为快慢双路径：首次对话 F1 本地安全门、F2 情境和二次安全兜底、F3 单候选流式返回，F4 在后台生成 session guidance。
- 后续轮次走轻量 CBT 生成，若后台 F4 guidance 已完成则注入；若未完成不等待。
- F1 已从 LLM prompt 迁移为本地分类器，模型和指标记录在 `exp/README.md`。
- F3 已接入 PsyQA 标注数据的策略先验和 support card，双候选实验链路保留在 `exp/`。
- 真实 LLM 45 条验收曾跑通：request_ok 45/45，F2 情境准确率 43/45，落库 candidates=90，旧 pointwise 逻辑生成 preference_pairs=43。
- F1 单列验收已补齐，异常/解析失败按 yellow 保守转介。
- 合成语料 probe-001 已完成 3 个代表格：raw=480、accepted=479、旧 pointwise 口径下 `judge_unverified_preference_pairs=433`。
- F4 pairwise 离线工具链已存在：候选包生成、pairwise judge、pointwise baseline、人工 A/B 表和评估脚本均已落地；新的实验入口以 `exp/README.md` 为准。

### 不能再按旧口径推进的部分

- 旧 43 对和 probe-001 的 433 对只证明“pointwise pipeline 能产出差异”，不证明这些偏好对可用于 DPO。
- Pointwise 诊断线显示 F3/F4 仍不稳定：旧主包单次 PASS，但 stability rerun 失败；post-erip 多轮仍有 ER/IP 高分饱和。
- R8 priority 10 条人工复核显示候选质量和 F4 高分判断仍有系统偏差。
- F4 已切到 `deepseek-v4-pro`、4096 token、JSON mode，但 priority smoke 仅从 10/20 改善到 11/20，不能单靠模型升级解锁 F9。
- Pairwise Phase A rerun 为 `inconclusive`：有效交集不足、critic-human agreement 不足，且 stable winner 有 `c1` 偏斜。

### 当前结论

当前不再把完整 F3/F4 链路作为学生在线等待路径。下一步应分两条线推进：应用侧先把流式对话、简短可读输出、匿名用户连续性、数据存储和研究台观测做顺；研究侧继续把 F4 pairwise、人工 A/B 和 DPO 证据链做扎实。正式 DPO 不能跳过人工校准 gate。

---

## P0：后端主链路验收（已关闭）

P0 只保留为回归维护，不再作为当前阻塞项。

- [x] F1 八用例实测与安全门单列验收。
- [x] F1 异常兜底语义：解析失败或调用失败均按 yellow 保守转介。
- [x] `/chat` mock 与真实 LLM 主链路验收已完成。
- [x] PostgreSQL/Alembic、Redis history store 和 `/chat` mock orchestrator integration 已在 2026-05-26 复验。

维护要求：改 F1/F2/F3/F4 schema 或编排顺序时，同步跑服务、handler 和 orchestrator 测试。

---

## P1：应用端体验与快路径稳定（当前主线）

目标是让产品先可用：学生端交互必须快、短、清楚、有温度；研究侧能力以后台和控制台方式呈现。

- [x] `/chat/stream` 已支持 SSE 流式返回。
- [x] 首轮在线路径已简化为 F1/F2/F3，F4 改后台。
- [x] F1 分类器、F3 support service 在 lifespan 中预加载。
- [ ] 学生端默认使用 live SSE，处理 `metadata`、`delta`、`done` 和 `error`。
- [ ] 学生端输出样式继续优化为短段落、低阅读负担，不展示内部 F1-F4 术语。
- [ ] 研究分析台同步展示快路径 trace、后台 F4 是否完成、session guidance 和质量标签。
- [ ] 登录/未登录数据策略明确：未登录使用 `anonymous_user_id + session_id`，登录后再做归属迁移。

维护要求：应用端改动优先保证 `/chat/stream` 与 mock/live 双模式都能演示。

---

## P2：F3/F4 与 Pairwise Gate 收敛（研究主线）

目标不是继续打磨 pointwise 分数，而是让“候选生成 -> pairwise 判断 -> 人工 A/B 对照”这条链路可验证、可复跑、可解释。

### P2.1 F3 候选质量

- [ ] 减少“复述 + 加深情绪 + 分析提问”的默认模式，避免两取向候选在策略上趋同。
- [ ] 针对亲子/同伴情境继续控制第三方动机推测、事实补全、品质化总结和成人化 coaching。
- [ ] 对 flash/pro 或不同生成配置的侧线比较只作为候选质量证据，不混入 Phase A 主指标。
- [ ] pairwise rerun 前冻结输入包，记录模型、prompt hash、候选来源和生成配置。

### P2.2 F4 pointwise 诊断线

- [ ] Pointwise 分数继续保留为历史兼容和诊断字段，不再作为新的 DPO 主判据。
- [ ] 若继续跑 priority 10 的完整 v4-pro count=3 对照，应只回答“pointwise judge 是否仍偏宽”，不能直接解锁 DPO。
- [ ] 新增或修改 F4 prompt 时，同步更新 `docs/specs/f4-critic-epitome-codex-spec.md` 和 `docs/corpus/f9/f4-fix-execution-summary.md`。

### P2.3 Pairwise 试点线

- [ ] 重新生成或清洗 Phase A 输入包，保证有效交集数量达到计划下限。
- [ ] 人工 A/B 标注要保留 tie/无效样本，不把难分样本强行转换成 winner/loser。
- [ ] 专项检查 `c1` 偏斜：同一 pair 正反顺序、隐藏标签、identical-text control 和 physical swap control 都要保留。
- [ ] 只有 `pairwise_stable` 且通过人工 gate 的 winner/loser 才能进入 DPO 候选池。

P2 产出：

- 一份 pairwise rerun conclusion，明确 go/no-go。
- 一份 `c1` 偏斜或位置偏差诊断。
- 一份冻结样本包 manifest，能复现候选、judge 和人工标注来源。

---

## P3：F9 / Pairwise 人工校验

当前 F9 主问题应从“EPITOME 0/1/2 分数是否可信”转为：

> 对同一批候选对，critic pairwise 的偏好判断是否与人工 A/B 偏好达到可接受一致性？

### 校验方式

- [ ] 对冻结候选对做人工 A/B 盲标，标注者看不到 critic 结果和 pointwise 分数。
- [ ] 计算人工间一致性与人工-critic 一致性；pairwise 可先报 simple agreement，也可对 winner/tie/invalid 使用 Cohen's kappa。
- [ ] Pointwise ER/IP/EX 可附带算 weighted kappa，但只作为诊断维度可靠性，不再作为 DPO 解锁的主证据。
- [ ] 不稳定、tie、invalid 或 `pairwise_unresolved` 样本不得进入训练偏好对。

### 通过条件

通过条件需在 rerun plan 中先写死，不能看结果后调阈值。最低要求：

- 有效交集数量满足计划下限。
- critic-human agreement 明显高于 pointwise baseline 或达到预设可接受线。
- 位置偏见和 `c1` 偏斜有控制实验解释。
- 人工标注表、judge runs、eval report 和 conclusion 均能复现。

---

## P4：Corpus Production 放量

production 放量必须在 P2 gate 通过后启动。probe-001 已经可用于估算损耗率，但不能直接作为 DPO 数据来源。

- [x] probe-001 已完成，overall_yield 约 90.2%。
- [x] 已生成首轮 production quota：`docs/corpus/production_quota_after_probe_001.json`。
- [ ] P2 gate 通过后，按剩余 12 格 quota 跑 production。
- [ ] 每条倾诉过 F1，非 green 或异常进 quarantine，不进常规池。
- [ ] production 后用真实 usable pair 数和心理-策略多样性决定是否补量。

注意：文本事件多样不等于 DPO 信息多样。反刍×同伴 probe 已暴露“事件换皮但心理结构同质”的风险；production 要优先覆盖 15 格心理结构和 variant_tags，而不是单格堆量。

---

## P5：DPO + 消融

DPO 只接受通过 P2 gate 的稳定偏好对。

- [ ] 偏好对来源必须标注 `pairwise_stable` / `human_validated` 等来源字段。
- [ ] 旧 pointwise 推导出的 `judge_unverified_preference_pairs` 不得直接进训练。
- [ ] 训练栈可选 trl `DPOTrainer` 或 LLaMA-Factory；DeepSeek API 不能直接 DPO，需要可训练底座。
- [ ] 换底座后必须重验 F3：取向分化、temperature、回应风格、边界行为都可能变化。
- [ ] 消融实验应比较 DPO 前后同一批测试情境的候选质量，并使用通过 gate 的 judge 或人工评估。

---

## P6：RAG 与第三取向（余力项）

- F6 RAG 是增强项，不应排在 pairwise gate 和 DPO 主链前面。
- F8 行动建议型对初中生有说教和过早建议风险，仍放在最后；只有 P1-P4 完成且有余力时再做。

---

## 当前最小可投路径

```
P0 快路径稳定
  -> P1 应用端体验更新
  -> P2 F3/F4 + pairwise gate 收敛
  -> P3 人工 A/B 校验通过
  -> P4 corpus production 放量
  -> P5 DPO + 消融
  -> 论文可投
```

若 P3 不通过，返回 P2 修候选生成、输入包或 pairwise judge，不进入 production 和 DPO。

---

## 需要同步更新的文件

- F4 runtime 或 selection schema 变化：`docs/specs/f4-critic-epitome-codex-spec.md`、`docs/specs/f4-pairwise-selection-codex-spec.md`。
- F9 / pairwise 结论变化：`docs/corpus/f9/README.md`、`docs/specs/f9-reliability-guide.md`。
- 前端 trace 展示变化：`docs/frontend/` 与 `frontend/shared/src/types.ts`。
- production 放量完成：本文件 P3、`docs/corpus/README.md`、`docs/corpus/production_quota_after_probe_001.json` 的后续说明。
