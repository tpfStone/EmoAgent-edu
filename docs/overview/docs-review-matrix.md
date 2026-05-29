# 文档审查矩阵 - 2026-05-29

> 范围：当前 `master`，提交 `852d5da`。本文是文档清理审查产物，不替代原始设计文档、规格文档或实验报告。

## 事实源

| 范围 | 当前事实 |
|---|---|
| 后端运行时 | `app/main.py` 注册 F1/F2/F3/F4 API 和 `/chat`；`/chat` 仍使用 `CriticService` pointwise 分数与 `weighted_total` 择优。 |
| F1 安全门 | `SafetyGateService` 已实现历史窗口、green/yellow/red 分级、yellow/red 转介和异常 yellow 兜底；单列验收记录为 `f1-real-llm-20260522-215321`。 |
| F4 pairwise | `app/services/critic_pairwise.py` 与 `docs/corpus/f9/pairwise-selection-pilot/` 已存在离线工具链；尚未成为 `/chat` 默认 runtime。 |
| F9 / corpus | `docs/corpus/f9/` 同时保存 pointwise reliability diagnostics 与 pairwise preference-pair pilot；`probe-001` 已完成，剩余 12 格 production quota 已生成。 |
| 前端实现 | `frontend/` 已在当前 `master`，包含 student、console、shared workspace，以及 `frontend/scripts/build-pages.mjs`。 |
| 历史归档 | `docs/archive/2026-05-21/` 仅用于追溯，不作为当前执行入口。 |

## 当前主线表述

EmoEdu 是面向初中生的中文情感教育多智能体对话系统。当前 `/chat` 运行时已经串起 F1 安全门、F2 情境分析、F3 双取向生成和 F4 pointwise critic，并通过 PostgreSQL/Redis 记录对话、候选、分数和偏好对。前端包含两个物理分离的 React 应用：学生端只渲染公开回应字段，研究分析台展示完整 trace。F4 的目标主线已转为 pairwise preference-pair selection；pointwise 分数只作为历史路径、兼容字段和诊断线。pairwise 尚未成为 `/chat` 默认 runtime，DPO 仍需等待 F9/pairwise 验证 gate 通过。

## 问题清单

| ID | 优先级 | 状态 | 范围 | 处理结果 / 剩余风险 |
|---|---|---|---|---|
| D1 | P0 | 已修 | 根目录 `README.md`、`.env.example`、`app/config.py` | 顶层入口已从旧的 F1/F4 后端原型口径改为 `EmoEdu MAS`；API title 改为 `EmoEdu MAS API`；README 列出 F1-F4、`/chat`、F9/corpus 和前端。 |
| D2 | P0 | 已关闭 | 分支结构 / 文档事实源 | 前端与 corpus/pairwise 已合入当前 `master`。旧的跨工作区事实源说明已从 `docs/README.md` 移除。 |
| D3 | P0 | 已修 | `docs/overview/emoedu-mas-plan.md` | 已标明本文保留早期方案论证；RAG/F8/旧 pointwise 分数均按规划、历史或诊断线理解；待办清单已拆成已落地与仍待推进，避免把已完成的画像、F1 和 `/chat` 原型继续写成待办。 |
| D4 | P0 | 已修 | F4 / pairwise 规格 | `docs/specs/f4-pairwise-selection.md` 已标为目标规格 / 非运行时默认；明确当前 `/chat` 仍为 pointwise，Phase A rerun 为 `inconclusive`。 |
| D5 | P0 | 已修 | `docs/corpus/f9/README.md` | F9 入口已拆成 `pointwise reliability diagnostics` 和 `pairwise preference-pair pilot` 两条线；pairwise 当前结论、阻塞和推荐阅读顺序已补充。 |
| D6 | P1 | 已修 | `docs/overview/emoedu-post-mvp-guide.md` | 已重写为当前后续路线：P1 先收敛 F3/F4 与 pairwise gate，P2 再做人工 A/B 校验；不再把旧 pointwise 偏好对写成 DPO 解锁依据。 |
| D7 | P1 | 已修 | `docs/frontend/*` | `docs/frontend/github-pages-mock-local-live.md` 已在当前 `master`；新增 `docs/frontend/README.md` 记录前端状态、验证命令和学生端安全边界检查。 |
| D8 | P1 | 已修 | `docs/figures/figure-1-three-phase-lifecycle.svg` | 已标注 planned RAG 与 F9/pairwise gate。 |
| D9 | P1 | 已修 | `docs/figures/figure-2-runtime-pipeline.svg` | 已改为 F1 -> F2 -> planned RAG -> F3 两候选 -> 当前 pointwise / 目标 pairwise -> `/chat`。 |
| D10 | P1 | 已修 | `docs/figures/figure-3-argument-loop.svg` | 已明确 DPO 在 F9/pairwise gate 通过前阻塞，旧 pointwise 分数仅作历史/诊断。 |
| D11 | P2 | 已修 | `docs/README.md` | 已更新为当前 `master` 集成状态；不再要求跨工作区读取事实。 |
| D12 | P2 | 已修 | `docs/archive/2026-05-21/README.md` | 归档 README 已说明历史规划不再作为当前开发入口，冲突时以当前规格和总结为准。 |
| D13 | P2 | 已修 | `docs/overview/emoedu-development-framework.md` | 已改为普通工程落地状态表；移除代理定向措辞，并按当前代码更新 F1/F2/F3/F4/F5/F6/F7 状态。 |

## 后续维护规则

- 根目录 `README.md` 只维护当前入口、运行方式和阅读路径。
- `docs/README.md` 维护文档导航和当前主线口径。
- `docs/corpus/f9/README.md` 是 F9 / pairwise 产物目录的首读入口。
- `docs/overview/emoedu-post-mvp-guide.md` 是当前后续路线入口；若 pairwise gate 或 production 状态变化，应优先更新该文档。
- 改 `/chat` runtime、F4 selection schema、前端 trace 或 DPO 数据口径时，必须同步更新 `docs/specs/f4-pairwise-selection.md`、`docs/corpus/f9/README.md` 和相关前端文档。
