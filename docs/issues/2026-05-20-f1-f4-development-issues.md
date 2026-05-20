# F1/F4 开发问题记录

> 记录时间：2026-05-20
> 处理策略：记录并继续开发。以下问题不阻塞 F1/F4 第一版实现。

## 已知口径问题

1. EPITOME 评分尺度存在文档口径不一致。
   - `docs/overview/emoedu-mas-plan.md` 中曾出现 `1-5` 分表述。
   - `docs/overview/emoedu-development-framework.md` 与 `docs/specs/f4-critic-epitome-codex-spec.md` 明确要求 EPITOME 使用原框架 `0/1/2`。
   - 本轮实现按 F4 规格执行：`ER/IP/EX = 0/1/2`。

2. `docs/figures/figure-1-three-phase-lifecycle.svg` 中“人在环偏好标注”容易被理解为大量人工标注。
   - 正文方案强调“小规模人工信度校验 + 经校验 LLM-judge 自动产偏好对”。
   - 本轮实现只保留 critic 运行日志和可用偏好对，不实现人工标注流程。

3. 总纲中“专家定维度与权重”和开发文档“无领域专家、等权起步”存在表述张力。
   - 本轮实现采用等权起步：`ER + IP + EX`。
   - CASEL 辅助评分暂不实现，仅保留 `activated_casel` 输入和空 `casel` 输出。

## 本轮范围裁剪

- 不实现 F2 情境分析。
- 不实现 F3 多取向生成器。
- 不实现 RAG、DPO、CASEL 辅助维评分。
- 不调用真实 LLM；测试通过 fake/mock LLM 完成。
