# 文档结构总览

[English](README_EN.md)

本目录同时保存项目方案、开发规格、验收记录、语料/F9 实验产物、前端设计和历史归档。阅读时应先区分三类内容：

- **产品运行口径**：学生真实交互走快路径，优先安全、流式和可持续对话。
- **研究实验口径**：F3 双候选、F4 critic、pairwise、F9 和 DPO 属于可复现实验链路。
- **历史证据/产物**：旧 F9、旧 pointwise 和 pairwise pilot 记录用于追溯，不自动代表当前上线策略。

## 当前状态

截至 2026-06-19，当前实现口径如下：

- `/chat` 和 `/chat/stream` 已接入快慢双路径。首次对话走 `F1 -> F2 -> F3 -> 流式返回 -> 后台 F4`；后续对话走轻量 CBT 支持，并在 F4 guidance 已完成时注入。
- F1 在 `/chat` 中默认使用本地分类器，不再依赖 LLM prompt。LLM 版 `/api/safety/evaluate` 保留用于兼容和对照。
- F2 输出情境、CASEL 维度、`support_mode`、`emotion_intensity`、`help_seeking`，并包含 `secondary_safety` 作为 LLM 兜底安全复核。
- F3 生产路径按 F2 路由生成单候选；模块接口仍可生成 `c1 共情型` 和 `c2 引导反思型` 双候选用于实验。
- F4 pointwise critic 已从在线阻塞择优器调整为后台质量评估和 session guidance 生成器。
- `frontend/` pnpm workspace 已支持学生端 SSE 流式交互、研究分析台、shared API/type 层。
- `../exp/` 是当前算法实验入口，记录 PsyQA 标注、F1 分类器、F3 support-card/RAG 验证和 F4 pairwise 对照实验；完整 PsyQA-derived labelled data 不随公开仓库发布。

## 当前 F4 主线口径

F4 有两个层次：

- **生产层**：F4 不阻塞学生回复。首次回复完成后后台运行，生成质量标签和 `session guidance`；下一轮若 guidance 已完成，再注入轻量生成。
- **研究层**：F4 pairwise 仍是后续偏好数据和 DPO 的目标主线，但模型 judge 与人工偏好一致性还不足，不能直接作为权威偏好来源。

当前结论是：F4 可以做后台评估、prompt 反哺和 DPO 候选数据构造；正式 DPO 前仍需要更多人工校准样本和稳定的 pairwise gate。

## 顶层目录

| 路径 | 定位 | 主要入口 |
|---|---|---|
| `overview/` | 项目总纲、工程拆分、比赛/论文路径 | `emoedu-mas-plan.md`、`emoedu-development-framework.md`、`emoedu-post-mvp-guide.md` |
| `specs/` | 面向实现的模块规格 | `f1-*-codex-spec.md`、`f2-*-codex-spec.md`、`f3-*-codex-spec.md`、`f4-*-codex-spec.md`、`f9-reliability-guide.md` |
| `plans/` | 未完成阶段计划和 gate | `phase-2b-plan.md` |
| `corpus/` | 合成语料方法、probe/production 产物、F9 实验链路 | `emoedu-corpus-synthesis.md`、`f9/README.md`、`f9/f9-mainline.md` |
| `acceptance/` | 后端/编排层验收流程与实跑证据 | `orchestrator-mvp/2026-05-21/README.md`、`backend-infrastructure/2026-05-26/backend-infrastructure-smoke.md` |
| `frontend/` | 前端设计基准、接口契约、重建计划、前端 UX 图 | `emoagent-frontend-design-baseline.md`、`frontend-cc-spec.md` |
| `issues/` | 开发过程问题记录 | `2026-05-20-f1-f4-development-issues.md`、`2026-05-22-f3-prompt-iteration-issues.md` |
| `figures/` | 论文/方案图 | `figure-*.svg` |
| `archive/` | 已归档的历史规划 | `2026-05-21/README.md` |
| `../exp/` | 当前算法实验台账 | `../exp/README.md` |

## 推荐阅读路径

### 1. 快速理解当前系统

1. 根目录 `README.md`：本地运行、API、快慢双路径和实验入口。
2. `../exp/README.md`：当前算法实验结论，包括 F1/F3/F4 的数据支撑。
3. `specs/README.md` 与 `specs/exp-integration-map.md`：当前 runtime/offline/default-off 边界。
4. `overview/emoedu-post-mvp-guide.md`：比赛投稿和应用端更新的当前工作图。

### 2. 开发后端模块

1. 先读对应 `specs/f*-*-codex-spec.md`，确认职责、IO schema、配置和 DoD。
2. 再读 `issues/` 中对应模块的问题记录，确认已知残留和边界。
3. 涉及 `/chat` 编排时，优先以 `app/services/orchestrator_service.py` 的快慢双路径为准。

### 3. 处理 F1/F2/F3 在线链路

1. `specs/f1-safety-gate-codex-spec.md`：本地分类器、阈值、soft rule 和保守短路。
2. `specs/f2-scenario-analysis-codex-spec.md`：情境、CASEL lookup、support mode 和二次安全兜底。
3. `specs/f3-multi-orientation-generator-codex-spec.md`：PsyQA support card、c1/c2 取向和生产单候选策略。
4. `../exp/README.md`：F1 训练指标与 F3 support probe 结果。

### 4. 处理 F4 / Pairwise / DPO

1. `specs/f4-critic-epitome-codex-spec.md`：后台 F4 pointwise critic 的当前职责。
2. `specs/f4-pairwise-selection-codex-spec.md`：pairwise 目标主线和迁移条件。
3. `../exp/README.md`：F4 eval package、模型对照和人工一致性结论。
4. `corpus/f9/README.md`：旧 F9 和 pairwise pilot 的历史上下文。

当前口径：F4 pairwise 是研究方向，不是 `/chat` 在线默认路径。未通过人工校准前，不把模型 judge 偏好直接用于 DPO。

### 5. 处理合成语料与 DPO

1. `corpus/emoedu-corpus-synthesis.md`：合成语料方法、字段、prompt、可执行管线。
2. `corpus/generation_config.json`：生成配置。
3. `corpus/runs/`：probe 实跑产物。
4. `corpus/production_quota_after_probe_001.json`：probe 后的放量 quota。

注意：F9 / pairwise 验证通过前，合成管线产出的偏好对只能视为 `judge_unverified`，不得作为 DPO 训练依据。由 pointwise 分数推导出的旧偏好对应记录为历史产物，不再作为新的训练主线。

### 6. 处理前端

1. `frontend/emoagent-frontend-design-baseline.md`：学生端和研究分析台的视觉/交互基准。
2. `frontend/frontend-cc-spec.md`：接口契约、mock/live 切换和 DoD。
3. `frontend/github-pages-mock-local-live.md`：GitHub Pages mock 和本机 live 演示。

当前口径：学生端应使用 `/chat/stream`，只展示用户需要看到的回复与基本状态；研究分析台可以展示完整 trace。

## 维护规则

- 根目录 `README.md` 维护运行入口和当前架构，不承载详细实验数据。
- `exp/README.md` 维护实验结果、复现命令和问题记录，是算法实验的事实源；`exp/data/README.md` 维护公开数据边界。
- `overview/` 给战略和论证，不应承载大量 run 证据。
- `specs/` 是实现契约；改代码行为、schema、prompt 或编排顺序时同步更新对应 spec。
- `plans/` 只放未完成计划；已完成事实应同步回入口文档和 specs。
- `corpus/f9/` 和 `archive/` 主要用于历史追溯；不能覆盖当前 `exp/` 结论。
- 若移动实验产物，必须同步更新对应 README、manifest 和报告路径。
