# Orchestrator MVP 人工验收流程

> 日期：2026-05-21

这份清单用于验收 `/chat` 编排层在 45 条语料上的端到端表现。它应在编排层技术验收通过后执行，并作为 MVP 对外标记“验收通过”前的人工质量检查。

关键口径：

- `mock dry-run` 是验收前置自检，用来确认脚本、API、落库和结果导出流程能跑通；不需要人工逐条看，也不计入回复质量结论。
- 正式人工质量验收必须接入真实 LLM。否则看到的是 mock 固定模板，不是在验证系统真实回复质量。
- 人工只标注低质量或异常产出，不需要给 45 条逐行打“通过”。

## 当前状态

- `mock-dry-run-20260522-000306` 已通过。
- 结果目录：`docs/acceptance/orchestrator-mvp/2026-05-21/runs/mock-dry-run-20260522-000306/`。
- 通过证据：45/45 请求成功，`auto_issue_rows=0`，落库抽查 `turns=45`、`messages=90`、`candidates=90`、`preference_pairs=0`。
- 第一次失败 run `mock-dry-run-20260522-000010` 是 API 进程未持续监听导致的连接拒绝，已删除，不作为验收记录。

## 文件夹结构

验收材料放在独立目录：

```text
docs/acceptance/orchestrator-mvp/2026-05-21/
  README.md
  2026-05-21-orchestrator-deferred-validation.md
  2026-05-21-orchestrator-manual-acceptance.md
  runs/
    .gitignore
    <run-id>/
      raw_results.json
      review_all.csv
      low_quality_only.csv
      summary.md
```

- `raw_results.json`：完整 `/chat` 响应，便于回溯。
- `review_all.csv`：45 条全量查看表，只读浏览，不要求人工填满。
- `low_quality_only.csv`：只记录自动发现的问题和人工补充的低质量样本。
- `summary.md`：本轮自动汇总，用于判断是否进入人工检查。

`runs/` 是本地生成产物目录，默认不提交。

## 验收范围

本流程覆盖 MVP 人工验收，不覆盖 F9 信度校验。

- F2 情境检查：真实 LLM 模式下，对比 `/chat` 返回的 `scenario` 与语料中的 `scenario`。
- `/chat` 端到端检查：确认 45 条语料都能走完整链路并返回可用回复。
- 回复质量人工检查：判断最终 `reply_text` 是否适合中国初中生情感支持场景。
- F4 选择抽查：发现 F4 选中了明显更差候选时记录。
- 落库抽查：确认 `turns`、`messages`、`candidates`，以及可能存在的 `preference_pairs` 已写入。

## 前置技术验收

先执行：

```powershell
python -m pytest tests -q
python -m alembic upgrade head
docker exec -it emoedu-redis redis-cli ping
```

期望结果：

- Pytest 全部通过。
- Alembic 无报错。
- Redis 返回 `PONG`。

## Step 0：mock dry-run，不做人工质量判断

目的：确认验收流程本身可用。

确认 `.env` 使用 mock：

```env
LLM_PROVIDER=mock
```

在终端 1 启动 API：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

在终端 2 运行下方“45 条导出脚本”，并把脚本中的 `RUN_MODE` 改成：

```python
RUN_MODE = "mock-dry-run"
```

mock dry-run 通过条件：

- 脚本无未捕获异常。
- `summary.md`、`review_all.csv`、`raw_results.json` 生成成功。
- 45 条都有响应记录。
- `reply_text` 非空。
- 落库数量符合预期。

当前已通过的 mock dry-run 是 `mock-dry-run-20260522-000306`。

mock dry-run 不需要人工逐条看回复，也不判断情境准确率。mock 当前会固定返回类似模板回复，F2 也可能固定为 `其他`，这些都不能代表真实质量。

## Step 1：真实 LLM 正式验收

目的：验证真实模型输出下的分类、回复质量、候选选择和链路稳定性。

确认 `.env` 使用真实 provider，例如：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的 key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

本次 MVP 验收优先用 `deepseek-chat`，因为当前客户端尚未显式传 DeepSeek V4 的 `thinking` 开关；`deepseek-chat` 当前兼容映射到 `deepseek-v4-flash` 非思考模式，能保留 F3 的 temperature 设置。后续迁移计划见 `docs/overview/2026-05-21-mvp-integration-roadmap.md` 的“LLM 模型策略（MVP 验收）”。

重新启动 API，确保配置生效：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

先跑 5 条 smoke。它只用于确认真实 LLM 链路可用：

```powershell
@'
import json
import urllib.request

API_URL = "http://127.0.0.1:8000/chat"
CORPUS_PATH = "docs/corpus/emoedu-corpus-45-samples.json"

with open(CORPUS_PATH, "r", encoding="utf-8") as file:
    samples = json.load(file)["samples"][:5]

for sample in samples:
    payload = {
        "session_id": f"real-smoke-{sample['id']}",
        "current_message": sample["text"],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    print(
        sample["id"],
        "expected=", sample["scenario"],
        "actual=", data.get("scenario"),
        "status=", data.get("status"),
        "risk=", data.get("risk_level"),
    )
    print(data.get("reply_text", ""))
    print("-" * 80)
'@ | python -
```

5 条 smoke 通过后再跑完整 45 条。

## Step 2：45 条导出脚本

正式验收时保持：

```python
RUN_MODE = "real-llm"
```

```powershell
@'
import csv
import json
import urllib.request
from datetime import datetime
from pathlib import Path

RUN_MODE = "real-llm"  # mock-dry-run | real-llm
API_URL = "http://127.0.0.1:8000/chat"
CORPUS_PATH = Path("docs/corpus/emoedu-corpus-45-samples.json")
OUT_ROOT = Path("docs/acceptance/orchestrator-mvp/2026-05-21/runs")

run_id = f"{RUN_MODE}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
out_dir = OUT_ROOT / run_id
out_dir.mkdir(parents=True, exist_ok=True)

with CORPUS_PATH.open("r", encoding="utf-8") as file:
    samples = json.load(file)["samples"]

review_rows = []
raw_results = []
low_quality_rows = []

for sample in samples:
    payload = {
        "session_id": f"{run_id}-{sample['id']}",
        "current_message": sample["text"],
    }
    row = {
        "sample_id": sample["id"],
        "persona": sample["persona"],
        "expected_scenario": sample["scenario"],
        "input_text": sample["text"],
        "request_ok": "false",
        "status": "",
        "risk_level": "",
        "actual_scenario": "",
        "scenario_match": "",
        "reply_text": "",
        "best_candidate_id": "",
        "failed_module": "",
        "failure_reason": "",
        "c1_orientation": "",
        "c1_text": "",
        "c1_weighted_total": "",
        "c1_boundary_flag": "",
        "c1_boundary_reason": "",
        "c2_orientation": "",
        "c2_text": "",
        "c2_weighted_total": "",
        "c2_boundary_flag": "",
        "c2_boundary_reason": "",
        "auto_issue_types": "",
        "manual_issue_type": "",
        "severity": "",
        "manual_reason": "",
        "suggested_owner": "",
    }
    auto_issues = []

    try:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            API_URL,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            chat = json.loads(response.read().decode("utf-8"))
        raw_results.append({"sample": sample, "request": payload, "chat": chat})

        scores_by_id = {score["candidate_id"]: score for score in chat.get("scores", [])}
        candidates_by_id = {
            candidate["candidate_id"]: candidate
            for candidate in chat.get("candidates", [])
        }

        row.update(
            {
                "request_ok": "true",
                "status": chat.get("status", ""),
                "risk_level": chat.get("risk_level", ""),
                "actual_scenario": chat.get("scenario", ""),
                "scenario_match": str(
                    chat.get("scenario", "") == sample["scenario"]
                ).lower(),
                "reply_text": chat.get("reply_text", ""),
                "best_candidate_id": chat.get("best_candidate_id", ""),
                "failed_module": chat.get("failed_module", ""),
                "failure_reason": chat.get("failure_reason", ""),
            }
        )

        for candidate_id in ("c1", "c2"):
            candidate = candidates_by_id.get(candidate_id, {})
            score = scores_by_id.get(candidate_id, {})
            row[f"{candidate_id}_orientation"] = candidate.get("orientation", "")
            row[f"{candidate_id}_text"] = candidate.get("text", "")
            row[f"{candidate_id}_weighted_total"] = score.get("weighted_total", "")
            row[f"{candidate_id}_boundary_flag"] = score.get("boundary_flag", "")
            row[f"{candidate_id}_boundary_reason"] = score.get("boundary_reason", "")

        if not row["status"]:
            auto_issues.append("missing_status")
        if not row["reply_text"].strip():
            auto_issues.append("empty_reply")
        if row["status"] == "module_failed":
            auto_issues.append("module_failed")
        if row["status"] == "all_candidates_blocked":
            auto_issues.append("all_candidates_blocked")

        if RUN_MODE == "real-llm":
            if row["risk_level"] != "green":
                auto_issues.append("non_green_risk")
            if row["actual_scenario"] != sample["scenario"]:
                auto_issues.append("scenario_mismatch")

    except Exception as exc:
        raw_results.append({"sample": sample, "request": payload, "error": str(exc)})
        auto_issues.append("request_error")
        row["failure_reason"] = str(exc)

    row["auto_issue_types"] = "|".join(auto_issues)
    review_rows.append(row)
    if auto_issues:
        low_quality_rows.append(row.copy())
    print(sample["id"], row["status"], row["risk_level"], row["actual_scenario"], row["auto_issue_types"])

review_csv = out_dir / "review_all.csv"
low_csv = out_dir / "low_quality_only.csv"
raw_json = out_dir / "raw_results.json"
summary_md = out_dir / "summary.md"

fieldnames = list(review_rows[0].keys())
with review_csv.open("w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(review_rows)

with low_csv.open("w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(low_quality_rows)

with raw_json.open("w", encoding="utf-8") as file:
    json.dump(raw_results, file, ensure_ascii=False, indent=2)

issue_counts = {}
for row in review_rows:
    for issue in filter(None, row["auto_issue_types"].split("|")):
        issue_counts[issue] = issue_counts.get(issue, 0) + 1

summary_lines = [
    f"# Orchestrator Acceptance Summary",
    "",
    f"- run_id: `{run_id}`",
    f"- run_mode: `{RUN_MODE}`",
    f"- total_samples: {len(review_rows)}",
    f"- request_ok: {sum(row['request_ok'] == 'true' for row in review_rows)}",
    f"- auto_issue_rows: {len(low_quality_rows)}",
    "",
    "## Auto Issue Counts",
    "",
]
if issue_counts:
    summary_lines.extend(f"- {issue}: {count}" for issue, count in sorted(issue_counts.items()))
else:
    summary_lines.append("- none")

summary_lines.extend(
    [
        "",
        "## Files",
        "",
        f"- `{raw_json}`",
        f"- `{review_csv}`",
        f"- `{low_csv}`",
    ]
)
summary_md.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

print(f"Wrote {summary_md}")
print(f"Wrote {review_csv}")
print(f"Wrote {low_csv}")
print(f"Wrote {raw_json}")
'@ | python -
```

## Step 3：人工只标低质量产出

打开本轮 `review_all.csv`，只做快速浏览。不要逐行填“通过”。

遇到低质量样本时，把该行复制到 `low_quality_only.csv`，补充这几个字段：

- `manual_issue_type`：例如 `unsafe`、`off_topic`、`too_preachy`、`not_for_junior_high`、`bad_candidate_selected`、`poor_empathy`。
- `severity`：`blocker`、`major`、`minor`。
- `manual_reason`：一句话说明为什么不合格。
- `suggested_owner`：建议填 `F1`、`F2`、`F3`、`F4`、`orchestrator` 或 `prompt`。

需要记录的问题：

- 请求崩溃，或缺少 `status`。
- `reply_text` 为空、乱码、明显跑题、过度说教或不安全。
- 真实 LLM 模式下，这批非危机语料的 `risk_level` 不是 `green`。
- 真实 LLM 模式下，`actual_scenario` 与 `expected_scenario` 明显不一致。
- 两个候选都被 blocked，但没有可信的边界原因。
- F4 选中了明显更差的候选。
- 回复不适合中国初中生语境，例如成人化、审判式、命令式、忽视情绪、把责任推给学生。

如果 `low_quality_only.csv` 只有表头，表示本轮没有发现自动问题，也没有人工标出的低质样本。

## Step 4：落库抽查

如果本地使用 `local-dev.sqlite`，45 条导出完成后执行：

```powershell
@'
import sqlite3

RUN_ID_PREFIX = "real-llm-"  # mock-dry-run- | real-llm-

con = sqlite3.connect("local-dev.sqlite")
print("turns:", con.execute(
    "select count(*) from turns where session_id like ?",
    (f"{RUN_ID_PREFIX}%",),
).fetchone()[0])
print("messages:", con.execute(
    "select count(*) from messages where session_id like ?",
    (f"{RUN_ID_PREFIX}%",),
).fetchone()[0])
print("candidates:", con.execute(
    """
    select count(*)
    from candidates
    where turn_id in (
      select id from turns where session_id like ?
    )
    """,
    (f"{RUN_ID_PREFIX}%",),
).fetchone()[0])
print("preference_pairs:", con.execute(
    """
    select count(*)
    from preference_pairs
    where turn_id in (
      select id from turns where session_id like ?
    )
    """,
    (f"{RUN_ID_PREFIX}%",),
).fetchone()[0])
con.close()
'@ | python -
```

正常预期：

- `turns`：至少包含本轮 45 条。
- `messages`：每条正常 turn 应包含 student 和 assistant 两条消息。
- `candidates`：未被 F1 阻断且未在 F3 前失败的样本应写入候选。
- `preference_pairs`：可能为 0；当两个候选分数相同或没有有效优劣差异时不会生成偏好对。

如果使用 PostgreSQL，执行同等 SQL 计数即可，重点是确认本轮 `session_id` 前缀下的数据完整。

## MVP 人工验收通过标准

满足以下条件时，可以认为编排层 MVP 的人工质量验收通过：

- mock dry-run 已通过，证明验收流程可运行。
- real LLM 45/45 条语料全部完成，没有未捕获异常。
- 每条样本都有非空 `reply_text`。
- 不存在 `blocker` 级人工问题。
- `major` 级问题数量可接受，并已记录样本 id、原因和归属模块。
- 回复没有明显不安全内容或严重越界。
- F2 情境不一致样本已记录，不要求 45/45 全对。
- 大多数回复与学生倾诉相关，语气适合初中生。
- 落库抽查没有发现系统性缺失。

## 与 F9 的关系

这份清单不是 F9。它可以为 F9 提供候选材料，但 F9 需要单独做信度研究：由人工标注 EPITOME/CASEL 分数，再与 F4 critic 的评分进行一致性比较。
