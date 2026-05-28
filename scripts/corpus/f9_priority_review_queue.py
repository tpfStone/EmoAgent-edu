import argparse
import csv
from pathlib import Path


BASE_COLUMNS = [
    "row_type",
    "review_order",
    "sample_no",
    "score_side",
    "scenario",
    "candidate_id",
    "orientation",
    "F4_ER",
    "F4_IP",
    "F4_EX",
    "rationale",
    "user_text",
    "candidate_text",
    "human_er_should_be_2",
    "human_ip_should_be_2",
    "human_issue_type",
    "human_notes",
]

OUTPUT_COLUMNS = [
    "review_bucket",
    "priority_rank",
    "priority_reason",
    *BASE_COLUMNS,
]

RISK_PROBES = (
    "换谁都会",
    "有没有想过",
    "换个角度",
    "递给你一个视角",
    "成人",
    "老师",
    "模板",
    "复述",
    "旁观者",
    "显性",
    "气死了",
    "是不是我哪里不好",
    "说明你",
    "可见你",
    "先接住",
    "再递",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _is_edge_summary(row: dict[str, str]) -> bool:
    return any(
        str(row.get(column, "")).strip().lower() == "true"
        for column in ("er_12_flip", "ip_12_flip", "er_unstable", "ip_unstable")
    )


def _edge_samples(rows: list[dict[str, str]]) -> set[str]:
    return {
        str(row.get("sample_no", "")).strip()
        for row in rows
        if str(row.get("sample_no", "")).strip() and _is_edge_summary(row)
    }


def _risk_probe_hit(row: dict[str, str]) -> bool:
    text = f"{row.get('rationale', '')}\n{row.get('candidate_text', '')}"
    return any(probe in text for probe in RISK_PROBES)


def _output_row(
    row: dict[str, str],
    *,
    bucket: str,
    rank: int | None,
    reason: str,
) -> dict[str, str]:
    output = {
        "review_bucket": bucket,
        "priority_rank": "" if rank is None else str(rank),
        "priority_reason": reason,
    }
    for column in BASE_COLUMNS:
        output[column] = row.get(column, "")
    return output


def _add_priority(
    *,
    output: list[dict[str, str]],
    selected_keys: set[tuple[str, str]],
    rows: list[dict[str, str]],
    rank: int,
    limit: int,
    reason: str,
) -> int:
    for row in rows:
        if rank > limit:
            break
        key = (str(row.get("sample_no", "")).strip(), row.get("candidate_id", ""))
        if key in selected_keys:
            continue
        output.append(_output_row(row, bucket="priority", rank=rank, reason=reason))
        selected_keys.add(key)
        rank += 1
    return rank


def build_priority_queue(
    queue_rows: list[dict[str, str]],
    *,
    count1_rows: list[dict[str, str]],
    count3_rows: list[dict[str, str]],
    priority_limit: int = 10,
) -> list[dict[str, str]]:
    calibration_rows = [
        row for row in queue_rows if row.get("row_type") == "calibration"
    ]
    review_rows = [row for row in queue_rows if row.get("row_type") == "review"]

    output: list[dict[str, str]] = [
        _output_row(row, bucket="calibration", rank=None, reason="calibration_anchor")
        for row in calibration_rows
    ]

    count1_edges = _edge_samples(count1_rows)
    count3_edges = _edge_samples(count3_rows)
    selected_keys: set[tuple[str, str]] = set()
    rank = 1

    rank = _add_priority(
        output=output,
        selected_keys=selected_keys,
        rows=[
            row
            for row in review_rows
            if str(row.get("sample_no", "")).strip() in count1_edges
        ],
        rank=rank,
        limit=priority_limit,
        reason="count1_rescore_edge",
    )
    rank = _add_priority(
        output=output,
        selected_keys=selected_keys,
        rows=[
            row
            for row in review_rows
            if str(row.get("sample_no", "")).strip() in count3_edges
        ],
        rank=rank,
        limit=priority_limit,
        reason="count3_rescore_edge",
    )
    rank = _add_priority(
        output=output,
        selected_keys=selected_keys,
        rows=[row for row in review_rows if row.get("score_side") != "ER_IP_2"],
        rank=rank,
        limit=priority_limit,
        reason="non_high_side_check",
    )
    rank = _add_priority(
        output=output,
        selected_keys=selected_keys,
        rows=[row for row in review_rows if _risk_probe_hit(row)],
        rank=rank,
        limit=priority_limit,
        reason="risk_probe",
    )
    rank = _add_priority(
        output=output,
        selected_keys=selected_keys,
        rows=review_rows,
        rank=rank,
        limit=priority_limit,
        reason="balanced_fill",
    )

    for row in review_rows:
        key = (str(row.get("sample_no", "")).strip(), row.get("candidate_id", ""))
        if key not in selected_keys:
            output.append(_output_row(row, bucket="backup", rank=None, reason=""))
    return output


def write_priority_queue(
    queue_path: Path,
    *,
    count1_path: Path,
    count3_path: Path,
    output_path: Path,
    priority_limit: int = 10,
) -> None:
    rows = build_priority_queue(
        _read_csv(queue_path),
        count1_rows=_read_csv(count1_path),
        count3_rows=_read_csv(count3_path),
        priority_limit=priority_limit,
    )
    _write_csv(output_path, rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a smaller prioritized F9 human review queue."
    )
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--count1-summary", type=Path, required=True)
    parser.add_argument("--count3-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--priority-limit", type=int, default=10)
    args = parser.parse_args()

    write_priority_queue(
        args.queue,
        count1_path=args.count1_summary,
        count3_path=args.count3_summary,
        output_path=args.output,
        priority_limit=args.priority_limit,
    )
    print(args.output)


if __name__ == "__main__":
    main()
