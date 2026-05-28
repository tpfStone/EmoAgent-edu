# 文档结构总览

本目录同时保存项目方案、开发规格、验收记录、语料/F9 实验产物、前端设计和历史归档。阅读时应先区分两类内容：

- **主线文档**：解释项目为什么这样设计、当前应做什么。
- **证据/产物**：保存某次验收、某次 run、某轮 F9 或 pairwise 试验的输入、输出和报告。

## 当前集成说明

截至 2026-05-29，文档审查需要同时参考两条本地事实源：

- 后端、F9、corpus、pairwise pipeline：当前分支 `feat/corpus-preference-pipeline`。
- 前端实现：本地 `master` worktree（`D:/projects/EmoAgent-edu/.worktrees/master-merge/frontend`）。

完整审查矩阵与修复建议见 `overview/docs-review-matrix.md`。在前端与 corpus 分支完成集成前，不应只用单个 checkout 判断全部文档是否准确。

## 当前 F4 主线口径

F4 的目标主线已从“逐项打分后按总分择优”调整为“成对偏好比较（pairwise）”。具体分数仍是历史路径和兼容字段：它们可用于追溯旧实验、解释现有代码和迁移过程，但不应再被写成未来择优或 DPO 数据的主判据。

当前实现状态需要分清：

- 目标方向：F4 以 pairwise 产出 winner/loser 和训练用偏好对。
- 代码现状：`/chat` 运行时仍主要使用 pointwise 分数、`weighted_total` 和 `scores`，尚未切换到 pairwise。
- 试验证据：Phase A rerun 结论为 `inconclusive`，不能证明当前 pairwise 设置已经优于 pointwise。
- 后续门槛：运行时、API、数据库和前端控制台迁移前，必须重新通过 pairwise 样本验证；不稳定或无效的 pairwise 结果不得进入 DPO。

## 顶层目录

| 路径 | 定位 | 主要入口 |
|---|---|---|
| `overview/` | 项目总纲、工程拆分、比赛/论文路径 | `emoedu-mas-plan.md`、`emoedu-development-framework.md`、`emoedu-post-mvp-guide.md` |
| `specs/` | 面向实现的模块规格 | `f1-*`、`f2-*`、`f3-*`、`f4-*`、`f9-reliability-guide.md` |
| `corpus/` | 合成语料方法、probe/production 产物、F9 实验链路 | `emoedu-corpus-synthesis.md`、`f9/README.md`、`f9/f9-mainline.md` |
| `acceptance/` | 后端/编排层验收流程与实跑证据 | `orchestrator-mvp/2026-05-21/README.md`、`backend-infrastructure/2026-05-26/backend-infrastructure-smoke.md` |
| `frontend/` | 前端设计基准、接口契约、重建计划、前端 UX 图 | `emoagent-frontend-design-baseline.md`、`frontend-cc-spec.md` |
| `issues/` | 开发过程问题记录 | `2026-05-20-f1-f4-development-issues.md`、`2026-05-22-f3-prompt-iteration-issues.md` |
| `figures/` | 论文/方案图 | `figure-*.svg` |
| `archive/` | 已归档的历史规划 | `2026-05-21/README.md` |

## 推荐阅读路径

### 1. 快速理解项目

1. `overview/emoedu-mas-plan.md`：系统方案、理论依据、generator-critic 闭环。
2. `overview/emoedu-development-framework.md`：F1-F9 工程拆分、运行时链路、技术栈。
3. `overview/emoedu-post-mvp-guide.md`：比赛投稿视角的关键路径和阶段安排。

### 2. 开发某个后端模块

1. 先读对应 `specs/f*-*.md`，确认职责、IO schema、prompt、配置、测试与 DoD。
2. 再读 `issues/` 中对应模块的问题记录，确认已知残留和边界。
3. 如涉及编排或落库，补读 `acceptance/orchestrator-mvp/2026-05-21/` 下的验收材料。

### 3. 处理 F9 / F3 / F4 主线

1. `corpus/f9/f9-mainline.md`：当前最高优先级入口，记录 F9 如何反向牵出 F3/F4 修复。
2. `corpus/f9/README.md`：F9 目录结构、关键文件和推荐阅读顺序。
3. `specs/f9-reliability-guide.md`：正式人工 F9 的执行方法。
4. `corpus/f9/validation*/`：自动验收与稳定性复跑证据。

当前口径：正式人工 F9 仍暂停。主线已进入 F4 新模型接入和 F3/F4 质量偏差处理阶段；不要把现有 rerun 包直接当作正式人工 F9 入口。

### 4. 处理 F4 pairwise 主线

1. `specs/f4-pairwise-selection-codex-spec.md`：pairwise 改造规格。
2. `corpus/f9/pairwise-selection-pilot/f4-pairwise-selection-pilot-plan.md`：试点总方案。
3. `corpus/f9/pairwise-selection-pilot/reports/phase-a-rerun/f9_pairwise_rerun_conclusion.md`：Phase A rerun 当前结论。

当前口径：pairwise 是 F4 的目标主线，但还不是 `/chat` 默认运行时。Phase A rerun 结论为 `inconclusive`，说明旧试点不能直接支撑上线；下一阶段应先修 F3 候选生成、frozen package 设计和 pairwise 判定稳定性，再评估是否迁移 runtime。

### 5. 处理合成语料与 DPO

1. `corpus/emoedu-corpus-synthesis.md`：合成语料方法、字段、prompt、可执行管线。
2. `corpus/generation_config.json`：生成配置。
3. `corpus/runs/`：probe 实跑产物。
4. `corpus/production_quota_after_probe_001.json`：probe 后的放量 quota。

注意：F9 / pairwise 验证通过前，合成管线产出的偏好对只能视为 `judge_unverified`，不得作为 DPO 训练依据。由 pointwise 分数推导出的旧偏好对应记录为历史产物，不再作为新的训练主线。

### 6. 处理前端

1. `frontend/emoagent-frontend-design-baseline.md`：学生端和研究分析台的视觉/交互基准。
2. `frontend/frontend-cc-spec.md`：前端模块边界、接口契约、mock/live 切换和 DoD。
3. `frontend/2026-05-26-frontend-rebuild-plan.md`：实施计划与自审记录。

当前口径：前端代码已经在本地 `master` worktree 中基本完成，并通过 test/typecheck/build；当前分支尚未包含前端实现。集成前的前端事实以 `master` worktree 为准。

## 维护规则

- 根目录 `README.md` 只维护结构索引和阅读路径；具体状态以各子目录 README 或主线文档为准。
- `overview/` 给战略和论证，不应承载大量 run 证据。
- `specs/` 是实现契约；改代码行为时同步更新对应 spec。
- `corpus/f9/f9-mainline.md` 是 F9 当前状态的最高优先级入口。
- `acceptance/` 和 `corpus/**/runs/` 保存证据，不作为新需求入口。
- 历史规划移入 `archive/` 后，只用于追溯，不再作为当前执行依据。
- 若移动实验产物，必须同步更新对应 README、manifest、报告里的路径引用。
