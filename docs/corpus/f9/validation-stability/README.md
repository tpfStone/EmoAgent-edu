# F9 Validation Stability

本目录保存不覆盖主包的稳定性复跑、固定候选复评和模型评测产物，状态为 **当前阻塞证据**。它回答两个问题：主包 PASS 是否稳定，以及高分饱和来自 F3 批次方差、F4 judge 抖动还是模型配置。

| 路径 | 状态 | 用途 |
|---|---|---|
| `run-1/`、`run-2/` | FAIL | 主包后的两次独立 stability rerun，均因 ER/IP=2 超过 32/40 失败。 |
| `post-erip-run-1/` 到 `post-erip-run-3/` | FAIL | F4 ER/IP 高档定义收紧后的三次联网 validation，仍未过 gate。 |
| `r8-fixed-rescore/` | 诊断完成 | 固定 `post-erip-run-2` 候选复评，区分 F4 judge 抖动和 F3 批次方差。 |
| `model-eval/` | 诊断中 | R9/R10 F4-only 模型对照与 v4-pro JSON smoke 产物。 |

关键入口：

- `run-2/f9_high_score_diff_review_queue.csv`：stability run-2 相对主包多出的 ER/IP=2 差集人工审查队列。
- `post-erip-run-2/f9_priority_review_queue.csv`：R8 priority 人工复核队列。
- `model-eval/f9_priority_model_comparison_summary.md`：模型对照摘要。

CSV/JSON 产物是运行事实记录，整理文档时不要改写其数据内容。
