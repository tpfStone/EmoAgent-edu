import csv
from pathlib import Path

from scripts.corpus.f9_high_score_calibration_queue import (
    OUTPUT_COLUMNS,
    build_calibration_queue,
    write_calibration_queue,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _score_row(sample_no: int, er: int, ip: int) -> dict[str, str]:
    return {
        "sample_no": str(sample_no),
        "scenario": "同伴关系",
        "candidate_id": "c2",
        "orientation": "引导反思型",
        "用户倾诉": f"学生倾诉 {sample_no}",
        "候选文本": f"候选文本 {sample_no}",
        "F4_ER": str(er),
        "F4_IP": str(ip),
        "F4_EX": "2",
        "rationale": f"rationale {sample_no}",
    }


def _calibration_row(sample_no: int) -> dict[str, str]:
    return {
        "sample_no": str(sample_no),
        "scenario": "同伴关系",
        "student_text": f"校准倾诉 {sample_no}",
        "stability_candidate_id": "c2",
        "stability_orientation": "引导反思型",
        "stability_F4_ER": "2",
        "stability_F4_IP": "2",
        "stability_F4_EX": "2",
        "stability_rationale": f"校准 rationale {sample_no}",
        "stability_candidate_text": f"校准候选 {sample_no}",
        "human_er_should_be_2": "no",
        "human_ip_should_be_2": "yes",
        "human_issue_type": "low_care_analysis",
        "human_notes": "分析不等于陪伴",
    }


def test_build_calibration_queue_puts_reviewed_examples_first_and_keeps_both_score_sides():
    score_rows = [
        _score_row(10, 2, 2),
        _score_row(11, 1, 2),
        _score_row(12, 2, 1),
    ]
    calibration_rows = [_calibration_row(25), _calibration_row(34)]

    rows = build_calibration_queue(score_rows, calibration_rows)

    assert [row["row_type"] for row in rows] == [
        "calibration",
        "calibration",
        "review",
        "review",
        "review",
    ]
    assert [row["sample_no"] for row in rows] == ["25", "34", "10", "11", "12"]
    assert rows[0]["human_er_should_be_2"] == "no"
    assert rows[0]["human_notes"] == "分析不等于陪伴"
    assert rows[2]["score_side"] == "ER_IP_2"
    assert rows[3]["score_side"] == "ER_not_2"
    assert rows[4]["score_side"] == "IP_not_2"
    assert rows[2]["human_er_should_be_2"] == ""
    assert rows[2]["human_ip_should_be_2"] == ""


def test_write_calibration_queue_outputs_utf8_sig_and_expected_columns(tmp_path):
    input_path = tmp_path / "scores.csv"
    calibration_path = tmp_path / "calibration.csv"
    output_path = tmp_path / "queue.csv"
    score_fields = [
        "sample_no",
        "scenario",
        "candidate_id",
        "orientation",
        "用户倾诉",
        "候选文本",
        "F4_ER",
        "F4_IP",
        "F4_EX",
        "rationale",
    ]
    calibration_fields = [
        "sample_no",
        "scenario",
        "student_text",
        "stability_candidate_id",
        "stability_orientation",
        "stability_F4_ER",
        "stability_F4_IP",
        "stability_F4_EX",
        "stability_rationale",
        "stability_candidate_text",
        "human_er_should_be_2",
        "human_ip_should_be_2",
        "human_issue_type",
        "human_notes",
    ]
    _write_csv(input_path, score_fields, [_score_row(10, 2, 2), _score_row(11, 1, 2)])
    _write_csv(calibration_path, calibration_fields, [_calibration_row(25)])

    write_calibration_queue(input_path, calibration_path, output_path)

    assert output_path.read_bytes().startswith(b"\xef\xbb\xbf")
    rows = _read_csv(output_path)
    assert list(rows[0].keys()) == OUTPUT_COLUMNS
    assert rows[0]["row_type"] == "calibration"
    assert rows[1]["row_type"] == "review"
    assert rows[2]["score_side"] == "ER_not_2"
