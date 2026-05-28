# Orchestrator MVP Acceptance Assets

> 日期：2026-05-21

本目录用于保存 `/chat` 编排层 MVP 人工验收的说明和本地运行产物。

## 当前状态

- F1 安全门单列验收已通过，最终记录 run 为 `f1-real-llm-20260522-215321`。
- 真实 LLM 45 条正式验收已完成，正式记录 run 为 `real-llm-20260522-215717`。
- 当前结论、修复记录和证据文件见 `2026-05-21-orchestrator-mvp-test-summary.md`。

## 目录约定

```text
docs/acceptance/orchestrator-mvp/2026-05-21/
  README.md
  2026-05-21-orchestrator-manual-acceptance.md
  2026-05-21-orchestrator-mvp-test-summary.md
  runs/
    .gitignore
    <run-id>/
      raw_results.json
      review_all.csv
      low_quality_only.csv
      summary.md
```

`runs/` 下的验收结果是本地生成产物，默认不提交。需要共享结果时，优先共享某次 run 的 `summary.md` 和 `low_quality_only.csv`。

## 验收口径

- `mock-dry-run`：前置自检，只验证 API、脚本、导出和落库流程，不做人工质量判断。
- `real-llm`：正式人工验收，必须接入真实 LLM，人工只标低质量或异常产出。
- F9 信度校验不在本目录范围内。

详细流程见 `docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-manual-acceptance.md`。
