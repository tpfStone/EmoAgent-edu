# 文档审查矩阵 - 2026-05-29

> 范围：本次审查同时覆盖当前 `feat/corpus-preference-pipeline` worktree，以及包含前端重建成果的本地 `master` worktree。本文是审查产物，不替代原始设计文档、规格文档或实验报告。

## 事实源

| 范围 | 来源 | 状态 |
|---|---|---|
| 后端运行时、F3/F4/F9、corpus pipeline | `D:\projects\EmoAgent-edu`，分支 `feat/corpus-preference-pipeline`，提交 `9165a25` | 当前工作分支；跟踪 `origin/feat/corpus-preference-pipeline`。 |
| 前端实现 | `D:\projects\EmoAgent-edu\.worktrees\master-merge`，分支 `master`，提交 `672b824` | 本地 `master` 已包含前端 workspace 和 GitHub Pages mock workflow。 |
| 远端 GitHub 仓库 | `origin=https://github.com/tpfStone/EmoAgent-edu.git` | 远端目前只暴露 `feat/corpus-preference-pipeline`，远端 HEAD 也指向该分支。 |
| 2026-05-21 归档计划 | `docs/archive/2026-05-21/` | 仅用于历史追溯，不应再作为当前执行依据。 |

## 验证证据

前端验证来自本地 `master` worktree：

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
rg "FullChatResponse|fetchChat\(|scores|candidates|weighted_total|failure_reason|preference_pair" frontend\student\src
rg "scrollIntoView" frontend
```

结果：

- 前端测试通过：shared `6`、console `3`、student `5`。
- 前端 typecheck 通过：`shared`、`student`、`console` 均通过。
- 前端 production build 通过：student 和 console 均可构建。
- 学生端源码中没有直接匹配分析字段或 console 全量 fetch API。
- `frontend/` 中未发现 `scrollIntoView` 用法。

## 问题清单

| ID | 优先级 | 处理状态 | 文档 / 范围 | 当前表述 | 事实来源 | 问题 | 建议修复 |
|---|---|---|---|---|---|---|---|
| D1 | P0 | 待集成后处理 | 根目录 `README.md`、`.env.example`、`app/config.py` | 项目仍被描述为 `EmoEdu F1/F4 FastAPI`，且只列 F1 与 F4。 | `app/main.py` 注册了 F1/F2/F3/F4 和 `/chat`；本地 `master` 还包含前端 workspace。 | 顶层入口过时，遮蔽了当前 MAS、运行时链路和前端实际范围。 | 分支集成后，围绕 `/chat`、F1-F4 runtime、F9/corpus pipeline 和前端重写根 README；API title 建议改为类似 `EmoEdu MAS API`。 |
| D2 | P0 | 待分支集成 | 分支结构 / 文档事实源 | 当前 worktree 文档提到前端设计，但当前分支没有前端文件。 | `master` 有 `frontend/`、`.github/workflows/pages-mock.yml`、`docs/frontend/github-pages-mock-local-live.md`；当前分支没有。 | 读者在当前分支 checkout 中无法验证前端实现。 | 将 `master` 的前端合入 corpus 分支，或先创建集成分支再做最终文档清理。集成前先在文档中注明前端事实来自本地 `master`。 |
| D3 | P0 | 已修 | `docs/overview/emoedu-mas-plan.md` | 原文混合 RAG、三生成器和 F4 分数排序设想。 | 运行时传入 `rag_examples=[]`；F3 只有两个取向；F4 目标主线已转为 pairwise，但 runtime 仍是 pointwise。 | 该文曾混合概念方案、历史设想和当前架构声明，与代码和后续 specs 冲突。 | 已加 2026-05-29 状态补充，并将 F4 改为 pairwise 目标主线；RAG/F8/旧分数均标为规划、历史或诊断线。 |
| D4 | P0 | 已修 | F4 / pairwise 文档 | `docs/specs/f4-pairwise-selection-codex-spec.md` 把 pairwise 写成可直接进入默认运行时的改造。 | 运行时仍注入 `CriticService`；`app/config.py` 没有 `CRITIC_SELECTION_MODE`；`phase-a-implementation-plan.md` 明确只做离线；Phase A rerun 结论是 `inconclusive`。 | pairwise 已成为 F4 目标主线，但还不是运行时默认；具体分数应降级为历史路径和兼容字段。 | 已改为 `目标规格 / 非运行时默认`：当前 `/chat` 仍为 pointwise；下一阶段先补 runtime adapter、API、数据库和前端 trace，再通过 pairwise 验证 gate。 |
| D5 | P0 | 待修 | F9 主线文档 | `docs/corpus/f9/f9-mainline.md` 主要围绕 pointwise ER/IP 稳定性线写到 R10。 | `docs/corpus/f9/pairwise-selection-pilot/` 下已有 pairwise pilot 产物和 rerun 诊断。 | 最高优先级 F9 入口没有清楚区分历史 pointwise 诊断线与新的 pairwise preference-pair 主线。 | 将当前 F9 状态拆成两条线：`pointwise reliability diagnostics` 作为历史/诊断线，`pairwise preference-pair pilot` 作为后续主线；在 `docs/corpus/f9/README.md` 中明确导读。 |
| D6 | P1 | 部分修 | `docs/overview/emoedu-post-mvp-guide.md` | P0 仍说 F1 八用例未回填，并沿用旧 pointwise 偏好对驱动 DPO 的假设。 | `docs/acceptance/orchestrator-mvp/2026-05-21/README.md` 已说 F1 单列验收通过；后续 F9/pairwise 文档已经覆盖 pointwise DPO readiness 的旧假设。 | 比赛路线叙述有价值，但包含过时阻塞项和旧 DPO 假设。 | 已加 2026-05-29 状态补充，标为历史参考；后续如继续使用，应重写为当前 roadmap。 |
| D7 | P1 | 待前端合入 | `docs/frontend/*` | 前端文档主要是设计、规格和实施计划。 | `master` 前端 test/typecheck/build 均通过；`github-pages-mock-local-live.md` 只存在于 `master`。 | 当前 checkout 中没有 branch-aware 的前端实现状态入口。 | 合入 `docs/frontend/github-pages-mock-local-live.md`，新增简短 `docs/frontend/README.md`，记录状态、命令和学生端安全边界验证。 |
| D8 | P1 | 已修 | `docs/figures/figure-1-three-phase-lifecycle.svg` | 图中展示 setup 填充 RAG memory，优化阶段含人工偏好标注。 | RAG 当前为空 / 未来项；偏好对尚未通过验证，不能用于 DPO。 | 该图更像概念图，作为当前架构图会误导。 | 已改为标注 `planned RAG` 和 `F9/pairwise gate`，提醒 DPO 前必须通过验证。 |
| D9 | P1 | 已修 | `docs/figures/figure-2-runtime-pipeline.svg` | 图中展示 runtime RAG、生成器 C、打分总分 argmax。 | 当前运行时跳过 RAG，F3 只有两个生成取向；F4 目标主线转为 pairwise，但 runtime 仍未迁移。 | runtime 图已不符合主线与已实现系统。 | 已改为：F1 -> F2 -> RAG planned -> F3 两候选 -> F4 当前 pointwise / 目标 pairwise -> `/chat`；第三取向标为未来项。 |
| D10 | P1 | 已修 | `docs/figures/figure-3-argument-loop.svg` | 图中说 LLM judging 已验证，并自动产生 DPO pair。 | F9 暂停；pairwise rerun 为 `inconclusive`；DPO 不应消费当前 pairs。 | 图中过度声明了验证状态。 | 已改为“待 F9/pairwise gate 验证”；明确 DPO 在 gate 通过前阻塞，旧 pointwise 分数仅作历史/诊断。 |
| D11 | P2 | 已修（临时说明） | `docs/README.md` | 结构索引方向正确，但默认所有事实都在当前 checkout。 | 前端实现位于 `master`；corpus/pairwise 位于当前分支。 | 新 docs index 有用，但需要补分支 / 集成上下文。 | 已在 `docs/README.md` 保留“当前集成说明”；最终仍需等前端与 corpus 分支合并后再清理。 |
| D12 | P2 | 待修 | `docs/archive/2026-05-21/*` | 历史实施计划仍容易从打开的 tab 进入阅读。 | 当前模块、验收和路线已经多次演进。 | 归档本身没问题，风险在于读者把它当当前执行入口。 | 保持归档文件不改，只让 `archive/README.md` 明确写明“非当前执行依据”。 |

## 建议的当前主线表述

分支集成后，顶层文档可采用以下口径：

> EmoEdu 是面向初中生的中文情感教育多智能体对话系统。当前 `/chat` 运行时已经串起 F1 安全门、F2 情境分析、F3 双取向生成和 F4 pointwise critic，并通过 PostgreSQL/Redis 记录对话、候选、分数和偏好对。前端包含两个物理分离的 React 应用：学生端只渲染公开回应字段，研究分析台展示完整 trace。F4 的目标主线已转为 pairwise preference-pair selection；pointwise 分数只作为历史路径、兼容字段和诊断线。pairwise 尚未成为 `/chat` 默认 runtime，DPO 仍需等待 F9/pairwise 验证 gate 通过。

## 修复顺序

1. 从 `master` 创建集成分支。
2. 将 `feat/corpus-preference-pipeline` 合入该集成分支，保留 `master` 的前端文件，并保留 feature 分支的 corpus/pairwise 文件。
3. 优先解决入口文档冲突：根目录 `README.md`、`docs/README.md`、`docs/corpus/f9/README.md`、`docs/frontend/README.md`。
4. 重新分类旧 overview 文档：区分当前架构文档与历史论证文档。
5. 已先修正三个 `docs/figures/figure-*.svg` 的过期口径；后续若进入论文排版，可再重画为最终版。
6. 推送前同时运行后端测试与前端 test/typecheck/build。

## GitHub 分支处理方案

当前远端状态：

- `origin` 只有 `refs/heads/feat/corpus-preference-pipeline`。
- `origin/HEAD` 指向 `feat/corpus-preference-pipeline`。
- 本地 `master` 已存在并包含前端，但还没有推送为 `origin/master`。

推荐安全路径：

```powershell
# 在主 worktree 中，先提交或暂存本地 docs 修改
git switch -c integrate/frontend-corpus master
git merge feat/corpus-preference-pipeline

# 解决冲突后验证
python -m pytest tests -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build

# 将集成结果发布为 master
git branch -f master integrate/frontend-corpus
git push -u origin master
```

随后在 GitHub 仓库设置中操作：

1. 进入 **Settings -> Branches -> Default branch**。
2. 将默认分支从 `feat/corpus-preference-pipeline` 改为 `master`。
3. 检查 GitHub Pages workflow 的触发分支。现有 Pages workflow 监听的是 `main`；需要改成 `master`，或保留手动触发。
4. 确认 `origin/master` 正确后，再决定是否保留或删除 feature 分支：

```powershell
git push origin --delete feat/corpus-preference-pipeline
```

不要在未集成本地 `master` 的情况下，把当前 feature 分支强推覆盖成 `master`；否则会丢掉前端这条线，除非先完成合并。
