# F9 Pointwise Plans

本目录保存 F3/F4/F9 pointwise 诊断线的历史执行计划，状态为 **计划归档 / 可追溯**。这些计划解释已有产物为什么生成，以及当时的验收条件是什么；当前状态以 `../README.md` 和 `../pointwise-diagnostics/execution-summary.md` 为准。

| 文件 | 原文件名 | 用途 |
|---|---|---|
| `f3-generator-fix-plan.md` | `f3-fix-plan.md` | F3 generator 品质化总结、事实/动机补全、具体复述约束等修复计划。 |
| `f4-critic-fix-plan.md` | `f4-fix-plan.md` | F4 critic audit tags、deterministic caps、ER/IP/EX 降分规则修复计划。 |
| `stability-gate-plan.md` | `f9-stability-gate-plan.md` | stability rerun、内部提示外泄边界、high-score diff queue 的执行计划。 |
| `model-eval-plan.md` | `f9-model-eval-plan.md` | R9/R10 F4-only 模型因素调研和 deepseek-v4-pro 兼容计划。 |

不要把新的 run 产物放进本目录；产物继续放在 `../validation/`、`../validation-stability/` 或 `../pairwise-selection-pilot/`。
