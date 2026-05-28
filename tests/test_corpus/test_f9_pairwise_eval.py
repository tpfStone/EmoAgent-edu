import csv
from pathlib import Path

from scripts.corpus.f9_pairwise_eval import (
    EVAL_COLUMNS,
    build_eval_rows,
    build_markdown_report,
    summarize_eval_rows,
    write_eval_outputs,
)


def _pairwise(pair_id: str, winner: str, *, stable: str = "true") -> dict[str, str]:
    return {
        "pair_id": pair_id,
        "sample_no": pair_id.replace("sample-", ""),
        "winner_id": winner,
        "pairwise_stable": stable,
        "pairwise_confidence": "unanimous",
        "selection_method": "pairwise_stable" if stable == "true" else "invalid",
        "invalid_count": "0" if stable == "true" else "1",
    }


def _human(pair_id: str, preference: str) -> dict[str, str]:
    return {
        "pair_id": pair_id,
        "sample_no": pair_id.replace("sample-", ""),
        "human_preference": preference,
        "human_tie": "true" if preference == "tie" else "false",
        "human_invalid": "true" if preference == "invalid" else "false",
        "human_boundary_winner": "",
        "human_issue_type": "",
        "human_notes": "",
        "annotator_id": "A",
    }


def _pointwise(
    pair_id: str, winner: str, *, sample_count: str = "3"
) -> dict[str, str]:
    return {
        "pair_id": pair_id,
        "pointwise_winner": winner,
        "pointwise_sample_count": sample_count,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_eval_rows_excludes_human_ties_and_invalid_pairwise_from_main_agreement():
    eval_rows = build_eval_rows(
        pairwise_rows=[
            _pairwise("sample-1", "c1"),
            _pairwise("sample-2", "c2"),
            _pairwise("sample-3", "c1", stable="false"),
            _pairwise("sample-4", "c1"),
        ],
        human_rows=[
            _human("sample-1", "c1"),
            _human("sample-2", "c1"),
            _human("sample-3", "c1"),
            _human("sample-4", "tie"),
        ],
        pointwise_rows=[
            _pointwise("sample-1", "c2"),
            _pointwise("sample-2", "c1"),
            _pointwise("sample-3", "c1"),
            _pointwise("sample-4", "c1"),
        ],
    )
    summary = summarize_eval_rows(eval_rows)

    assert eval_rows[0]["pairwise_match"] == "true"
    assert eval_rows[1]["pairwise_match"] == "false"
    assert eval_rows[2]["main_exclusion_reason"] == "critic_invalid_or_unstable"
    assert eval_rows[3]["main_exclusion_reason"] == "human_tie_or_invalid"
    assert summary["total_pairs"] == 4
    assert summary["human_valid_pairs"] == 3
    assert summary["critic_valid_pairs"] == 2
    assert summary["pairwise_matches"] == 1
    assert summary["critic_human_agreement"] == "0.500"
    assert summary["pointwise_valid_pairs"] == 2
    assert summary["pointwise_matches"] == 1
    assert summary["pointwise_human_agreement"] == "0.500"
    assert summary["agreement_delta_vs_pointwise"] == "0.000"
    assert summary["comparison_intersection_pairs"] == 2
    assert summary["pairwise_valid_pairs_all"] == 2
    assert summary["pointwise_valid_pairs_all"] == 3
    assert summary["attrition_human_tie_or_invalid"] == 1
    assert summary["attrition_pairwise_unstable_or_invalid"] == 1
    assert summary["attrition_pointwise_invalid_or_nonformal"] == 0


def test_eval_marks_delta_unavailable_without_formal_pointwise_baseline():
    eval_rows = build_eval_rows(
        pairwise_rows=[_pairwise("sample-1", "c1")],
        human_rows=[_human("sample-1", "c1")],
        pointwise_rows=[_pointwise("sample-1", "c2", sample_count="1")],
    )
    summary = summarize_eval_rows(eval_rows)

    assert eval_rows[0]["main_exclusion_reason"] == "pointwise_invalid_or_nonformal"
    assert summary["critic_valid_pairs"] == 0
    assert summary["pointwise_valid_pairs"] == 0
    assert summary["comparison_intersection_pairs"] == 0
    assert summary["agreement_delta_vs_pointwise"] == "unavailable"


def test_write_eval_outputs_writes_csv_summary_and_markdown(tmp_path):
    eval_rows = build_eval_rows(
        pairwise_rows=[_pairwise("sample-1", "c1")],
        human_rows=[_human("sample-1", "c1")],
        pointwise_rows=[_pointwise("sample-1", "c2")],
    )
    summary = summarize_eval_rows(eval_rows)

    paths = write_eval_outputs(tmp_path, eval_rows, summary)
    report = build_markdown_report(summary)

    assert paths["eval"].read_bytes().startswith(b"\xef\xbb\xbf")
    assert list(_read_csv(paths["eval"])[0].keys()) == EVAL_COLUMNS
    assert "critic_human_agreement: 1.000" in paths["report"].read_text(encoding="utf-8")
    assert "agreement_delta_vs_pointwise: 1.000" in report
    assert "样本流失分解" in report
