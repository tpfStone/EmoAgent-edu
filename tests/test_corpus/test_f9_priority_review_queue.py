import csv
from pathlib import Path

from scripts.corpus.f9_priority_review_queue import (
    OUTPUT_COLUMNS,
    build_priority_queue,
    write_priority_queue,
)


def _calibration_row(sample_no: int) -> dict[str, str]:
    return {
        "row_type": "calibration",
        "review_order": str(sample_no),
        "sample_no": str(sample_no),
        "score_side": "calibration",
        "scenario": "同伴关系",
        "candidate_id": "c2",
        "orientation": "引导反思型",
        "F4_ER": "2",
        "F4_IP": "2",
        "F4_EX": "2",
        "rationale": "校准",
        "user_text": f"校准倾诉 {sample_no}",
        "candidate_text": f"校准候选 {sample_no}",
        "human_er_should_be_2": "no",
        "human_ip_should_be_2": "yes",
        "human_issue_type": "low_care_analysis",
        "human_notes": "校准标准",
    }


def _review_row(
    sample_no: int,
    *,
    scenario: str = "同伴关系",
    orientation: str = "引导反思型",
    score_side: str = "ER_IP_2",
    rationale: str = "无明显风险",
    candidate_text: str | None = None,
) -> dict[str, str]:
    er = "2"
    ip = "2"
    if score_side == "ER_not_2":
        er = "1"
    elif score_side == "IP_not_2":
        ip = "1"
    elif score_side == "ER_IP_not_2":
        er = "1"
        ip = "1"
    return {
        "row_type": "review",
        "review_order": str(sample_no),
        "sample_no": str(sample_no),
        "score_side": score_side,
        "scenario": scenario,
        "candidate_id": "c2",
        "orientation": orientation,
        "F4_ER": er,
        "F4_IP": ip,
        "F4_EX": "2",
        "rationale": rationale,
        "user_text": f"学生倾诉 {sample_no}",
        "candidate_text": candidate_text or f"候选文本 {sample_no}",
        "human_er_should_be_2": "",
        "human_ip_should_be_2": "",
        "human_issue_type": "",
        "human_notes": "",
    }


def _summary_row(sample_no: int, *, er_flip: bool = False, ip_flip: bool = False):
    return {
        "sample_no": str(sample_no),
        "candidate_id": "c2",
        "er_12_flip": str(er_flip).lower(),
        "ip_12_flip": str(ip_flip).lower(),
        "er_unstable": "false",
        "ip_unstable": str(ip_flip).lower(),
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_priority_queue_keeps_calibration_first_and_prioritizes_high_signal_rows():
    queue_rows = [
        _calibration_row(10),
        _calibration_row(13),
        _review_row(1, rationale="换谁都会觉得难受，是否更气她当众那句话"),
        _review_row(2, score_side="ER_not_2"),
        _review_row(3, scenario="学业压力", orientation="共情型"),
        _review_row(4, rationale="普通高分"),
        _review_row(5, scenario="亲子摩擦", orientation="共情型", candidate_text="你有没有想过换个角度"),
    ]
    count1_rows = [_summary_row(3, er_flip=True)]
    count3_rows = [_summary_row(5, ip_flip=True)]

    output = build_priority_queue(
        queue_rows,
        count1_rows=count1_rows,
        count3_rows=count3_rows,
        priority_limit=4,
    )

    assert [row["review_bucket"] for row in output[:2]] == [
        "calibration",
        "calibration",
    ]
    priority_rows = [row for row in output if row["review_bucket"] == "priority"]
    backup_rows = [row for row in output if row["review_bucket"] == "backup"]
    assert [row["sample_no"] for row in priority_rows] == ["3", "5", "2", "1"]
    assert "count1_rescore_edge" in priority_rows[0]["priority_reason"]
    assert "count3_rescore_edge" in priority_rows[1]["priority_reason"]
    assert "non_high_side_check" in priority_rows[2]["priority_reason"]
    assert "risk_probe" in priority_rows[3]["priority_reason"]
    assert [row["sample_no"] for row in backup_rows] == ["4"]
    assert list(output[0].keys()) == OUTPUT_COLUMNS


def test_write_priority_queue_outputs_utf8_bom(tmp_path):
    queue_path = tmp_path / "queue.csv"
    count1_path = tmp_path / "count1.csv"
    count3_path = tmp_path / "count3.csv"
    output_path = tmp_path / "priority.csv"
    queue_fields = [
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
    _write_csv(
        queue_path,
        queue_fields,
        [_calibration_row(10), _review_row(1), _review_row(2, score_side="ER_not_2")],
    )
    summary_fields = [
        "sample_no",
        "candidate_id",
        "er_12_flip",
        "ip_12_flip",
        "er_unstable",
        "ip_unstable",
    ]
    _write_csv(count1_path, summary_fields, [_summary_row(1, er_flip=True)])
    _write_csv(count3_path, summary_fields, [])

    write_priority_queue(
        queue_path,
        count1_path=count1_path,
        count3_path=count3_path,
        output_path=output_path,
        priority_limit=2,
    )

    assert output_path.read_bytes().startswith(b"\xef\xbb\xbf")
    rows = _read_csv(output_path)
    assert rows[0]["review_bucket"] == "calibration"
    assert rows[1]["review_bucket"] == "priority"
    assert list(rows[0].keys()) == OUTPUT_COLUMNS
