import csv
from pathlib import Path

from scripts.corpus.f9_model_eval import (
    COMPARISON_COLUMNS,
    build_model_comparison,
    write_model_eval_outputs,
)


def _human_row(
    sample_no: int,
    *,
    er: str,
    ip: str,
    issue: str = "",
    notes: str = "",
) -> dict[str, str]:
    return {
        "review_bucket": "priority",
        "priority_rank": str(sample_no),
        "sample_no": str(sample_no),
        "candidate_id": "c2",
        "human_er_should_be_2": er,
        "human_ip_should_be_2": ip,
        "human_issue_type": issue,
        "human_notes": notes,
        "user_text": f"学生原文 {sample_no}",
        "candidate_text": f"候选回复 {sample_no}",
    }


def _summary_row(sample_no: int, *, er_values: str, ip_values: str) -> dict[str, str]:
    return {
        "sample_no": str(sample_no),
        "candidate_id": "c2",
        "rescore_ER_values": er_values,
        "rescore_IP_values": ip_values,
        "rescore_EX_values": "2;2;2",
    }


def _run_row(
    sample_no: int,
    *,
    boundary_reason: str = "",
    boundary_flag: str = "false",
) -> dict[str, str]:
    return {
        "sample_no": str(sample_no),
        "candidate_id": "c2",
        "rescore_boundary_flag": boundary_flag,
        "rescore_boundary_reason": boundary_reason,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_model_comparison_counts_matches_against_human_labels():
    human_rows = [
        _human_row(6, er="yes", ip="no", notes="人工认可 ER，但不认可 IP"),
        _human_row(19, er="no", ip="no", issue="low_care_analysis"),
        {**_human_row(20, er="no", ip="no"), "review_bucket": "backup"},
    ]
    baseline_rows = [
        _summary_row(6, er_values="2;2;2", ip_values="2;2;2"),
        _summary_row(19, er_values="2;2;2", ip_values="2;2;2"),
    ]
    candidate_rows = [
        _summary_row(6, er_values="2;2;2", ip_values="1;1;1"),
        _summary_row(19, er_values="1;1;1", ip_values="1;1;1"),
    ]

    comparison, summary = build_model_comparison(
        human_rows,
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        baseline_model="deepseek-chat",
        candidate_model="deepseek-v4-pro",
    )

    assert [row["sample_no"] for row in comparison] == ["6", "19"]
    assert comparison[0]["baseline_er_match"] == "true"
    assert comparison[0]["baseline_ip_match"] == "false"
    assert comparison[0]["candidate_er_match"] == "true"
    assert comparison[0]["candidate_ip_match"] == "true"
    assert comparison[0]["preferred_model"] == "candidate"
    assert summary["baseline_total_matches"] == 1
    assert summary["candidate_total_matches"] == 4
    assert summary["candidate_better_rows"] == 2
    assert summary["baseline_better_rows"] == 0


def test_build_model_comparison_does_not_count_parse_failure_zero_as_match():
    comparison, summary = build_model_comparison(
        [_human_row(19, er="no", ip="no")],
        baseline_rows=[_summary_row(19, er_values="2;2;2", ip_values="2;2;2")],
        candidate_rows=[_summary_row(19, er_values="0", ip_values="0")],
        candidate_run_rows=[
            _run_row(19, boundary_flag="true", boundary_reason="llm_parse_failure")
        ],
        baseline_model="deepseek-chat",
        candidate_model="deepseek-v4-pro",
    )

    assert comparison[0]["candidate_valid"] == "false"
    assert comparison[0]["candidate_failure_reason"] == "llm_parse_failure"
    assert comparison[0]["candidate_er_match"] == "false"
    assert comparison[0]["candidate_ip_match"] == "false"
    assert comparison[0]["preferred_model"] == "tie"
    assert summary["candidate_invalid_rows"] == 1
    assert summary["candidate_total_matches"] == 0


def test_write_model_eval_outputs_uses_utf8_bom_and_summary_markdown(tmp_path):
    comparison, summary = build_model_comparison(
        [_human_row(6, er="yes", ip="no")],
        baseline_rows=[_summary_row(6, er_values="2;2;2", ip_values="2;2;2")],
        candidate_rows=[_summary_row(6, er_values="2;2;2", ip_values="1;1;1")],
        baseline_model="deepseek-chat",
        candidate_model="deepseek-v4-pro",
    )

    csv_path, summary_path = write_model_eval_outputs(tmp_path, comparison, summary)

    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert list(_read_csv(csv_path)[0].keys()) == COMPARISON_COLUMNS
    text = summary_path.read_text(encoding="utf-8")
    assert "deepseek-chat" in text
    assert "deepseek-v4-pro" in text
    assert "candidate_total_matches: 2" in text
