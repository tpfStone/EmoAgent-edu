import csv

import pytest

from scripts.corpus.f9_reliability import (
    RELIABILITY_COLUMNS,
    analyze_f9_annotations,
    consensus_score,
    quadratic_weighted_kappa,
)


def _write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_quadratic_weighted_kappa_uses_ordered_distance():
    assert quadratic_weighted_kappa([0, 1, 2], [0, 1, 2]) == 1.0

    value = quadratic_weighted_kappa([0, 0, 2, 2], [0, 1, 1, 2])

    assert value == pytest.approx(2 / 3)


def test_consensus_score_rounds_half_up_for_adjacent_disagreement():
    assert consensus_score(0, 1) == 1
    assert consensus_score(1, 2) == 2
    assert consensus_score(0, 2) == 1


def test_analyze_f9_annotations_merges_scores_and_writes_summary(tmp_path):
    blind_path = tmp_path / "f9_blind_annotation.csv"
    holdout_path = tmp_path / "f9_f4_scores_holdout.csv"
    _write_csv(
        blind_path,
        [
            "sample_no",
            "scenario",
            "orientation",
            "用户倾诉",
            "对话历史",
            "候选文本",
            "A_ER",
            "A_IP",
            "A_EX",
            "B_ER",
            "B_IP",
            "B_EX",
            "",
        ],
        [
            {
                "sample_no": 1,
                "scenario": "学业压力",
                "orientation": "共情型",
                "用户倾诉": "倾诉1",
                "对话历史": "[]",
                "候选文本": "候选1",
                "A_ER": 2,
                "A_IP": 1,
                "A_EX": 0,
                "B_ER": 2,
                "B_IP": 2,
                "B_EX": 0,
                "": "",
            },
            {
                "sample_no": 2,
                "scenario": "同伴关系",
                "orientation": "引导反思型",
                "用户倾诉": "倾诉2",
                "对话历史": "[]",
                "候选文本": "候选2",
                "A_ER": 1,
                "A_IP": 1,
                "A_EX": 2,
                "B_ER": 1,
                "B_IP": 1,
                "B_EX": 1,
                "": "",
            },
            {
                "sample_no": 3,
                "scenario": "亲子摩擦",
                "orientation": "共情型",
                "用户倾诉": "倾诉3",
                "对话历史": "[]",
                "候选文本": "候选3",
                "A_ER": 0,
                "A_IP": 2,
                "A_EX": 1,
                "B_ER": 0,
                "B_IP": 2,
                "B_EX": 1,
                "": "",
            },
        ],
    )
    _write_csv(
        holdout_path,
        ["sample_no", "F4_ER", "F4_IP", "F4_EX"],
        [
            {"sample_no": 1, "F4_ER": 2, "F4_IP": 2, "F4_EX": 0},
            {"sample_no": 2, "F4_ER": 1, "F4_IP": 1, "F4_EX": 2},
            {"sample_no": 3, "F4_ER": 0, "F4_IP": 2, "F4_EX": 1},
        ],
    )

    result = analyze_f9_annotations(
        blind_annotation_path=blind_path,
        f4_holdout_path=holdout_path,
        output_dir=tmp_path / "out",
    )

    merged_rows = list(
        csv.DictReader(result.merged_annotations_path.open(encoding="utf-8-sig"))
    )
    summary_rows = list(
        csv.DictReader(result.reliability_summary_path.open(encoding="utf-8-sig"))
    )
    report = result.report_path.read_text(encoding="utf-8")

    assert result.sample_count == 3
    assert len(merged_rows) == 3
    assert merged_rows[0]["consensus_IP"] == "2"
    assert merged_rows[1]["consensus_EX"] == "2"
    assert list(summary_rows[0].keys()) == RELIABILITY_COLUMNS
    assert {row["dimension"] for row in summary_rows} == {"ER", "IP", "EX"}
    assert summary_rows[0]["n"] == "3"
    assert "quadratically weighted Cohen" in report


def test_analyze_f9_annotations_rejects_missing_human_scores(tmp_path):
    blind_path = tmp_path / "f9_blind_annotation.csv"
    holdout_path = tmp_path / "f9_f4_scores_holdout.csv"
    _write_csv(
        blind_path,
        [
            "sample_no",
            "scenario",
            "orientation",
            "用户倾诉",
            "对话历史",
            "候选文本",
            "A_ER",
            "A_IP",
            "A_EX",
            "B_ER",
            "B_IP",
            "B_EX",
        ],
        [
            {
                "sample_no": 1,
                "scenario": "学业压力",
                "orientation": "共情型",
                "用户倾诉": "倾诉",
                "对话历史": "[]",
                "候选文本": "候选",
                "A_ER": "",
                "A_IP": 1,
                "A_EX": 1,
                "B_ER": 1,
                "B_IP": 1,
                "B_EX": 1,
            }
        ],
    )
    _write_csv(
        holdout_path,
        ["sample_no", "F4_ER", "F4_IP", "F4_EX"],
        [{"sample_no": 1, "F4_ER": 1, "F4_IP": 1, "F4_EX": 1}],
    )

    with pytest.raises(ValueError, match="A_ER is blank for sample_no 1"):
        analyze_f9_annotations(blind_path, holdout_path, tmp_path / "out")
