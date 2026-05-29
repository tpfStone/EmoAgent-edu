import csv
import json
from pathlib import Path

import pytest

from app.schemas.critic import CandidateScore, EpitomeScore
from app.config import Settings
from scripts.corpus.f9_fixed_candidate_rescore import (
    RUN_COLUMNS,
    SUMMARY_COLUMNS,
    build_run_row,
    select_source_rows,
    summarize_rescore_rows,
    run_fixed_rescore,
    write_rescore_outputs,
)


def _score(er: int, ip: int, ex: int, rationale: str = "复评分") -> CandidateScore:
    return CandidateScore(
        candidate_id="c2",
        epitome=EpitomeScore(ER=er, IP=ip, EX=ex),
        boundary_flag=False,
        boundary_reason="",
        weighted_total=float(er + ip + ex),
        rationale=rationale,
    )


def _source_row() -> dict[str, str]:
    return {
        "sample_no": "25",
        "scenario": "学业压力",
        "candidate_id": "c2",
        "orientation": "认知共情型",
        "用户倾诉": "老师没讲还考这么难，我气死了。",
        "候选文本": "你气的不是题难，而是明明没讲却要按这个评分。",
        "F4_ER": "2",
        "F4_IP": "2",
        "F4_EX": "2",
        "rationale": "原始评分",
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_run_row_preserves_original_score_and_marks_12_flips():
    row = build_run_row(_source_row(), repeat_no=1, score=_score(1, 2, 2))

    assert row["sample_no"] == "25"
    assert row["original_F4_ER"] == "2"
    assert row["original_F4_IP"] == "2"
    assert row["repeat_no"] == "1"
    assert row["rescore_F4_ER"] == "1"
    assert row["rescore_F4_IP"] == "2"
    assert row["changed_ER"] == "true"
    assert row["changed_IP"] == "false"
    assert row["er_12_flip"] == "true"
    assert row["ip_12_flip"] == "false"
    assert row["candidate_text"] == "你气的不是题难，而是明明没讲却要按这个评分。"


def test_summarize_rescore_rows_reports_unstable_values_and_change_counts():
    run_rows = [
        build_run_row(_source_row(), repeat_no=1, score=_score(1, 2, 2)),
        build_run_row(_source_row(), repeat_no=2, score=_score(2, 1, 2)),
        build_run_row(_source_row(), repeat_no=3, score=_score(2, 2, 2)),
    ]

    summary = summarize_rescore_rows(run_rows)

    assert len(summary) == 1
    assert summary[0]["sample_no"] == "25"
    assert summary[0]["rescore_ER_values"] == "1;2;2"
    assert summary[0]["rescore_IP_values"] == "2;1;2"
    assert summary[0]["changed_ER_count"] == "1"
    assert summary[0]["changed_IP_count"] == "1"
    assert summary[0]["er_unstable"] == "true"
    assert summary[0]["ip_unstable"] == "true"
    assert summary[0]["er_12_flip"] == "true"
    assert summary[0]["ip_12_flip"] == "true"


def test_write_rescore_outputs_uses_excel_friendly_utf8_bom(tmp_path):
    run_rows = [build_run_row(_source_row(), repeat_no=1, score=_score(1, 2, 2))]
    summary_rows = summarize_rescore_rows(run_rows)

    run_path, summary_path = write_rescore_outputs(tmp_path, run_rows, summary_rows)

    assert run_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert summary_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert list(_read_csv(run_path)[0].keys()) == RUN_COLUMNS
    assert list(_read_csv(summary_path)[0].keys()) == SUMMARY_COLUMNS


def test_build_run_row_reads_priority_queue_user_text_column():
    source_row = {
        "sample_no": "6",
        "scenario": "同伴关系",
        "candidate_id": "c2",
        "orientation": "认知共情型",
        "user_text": "学生原文",
        "candidate_text": "候选回复",
        "F4_ER": "2",
        "F4_IP": "2",
        "F4_EX": "2",
    }

    row = build_run_row(source_row, repeat_no=1, score=_score(1, 1, 2))

    assert row["user_text"] == "学生原文"
    assert row["candidate_text"] == "候选回复"


def test_select_source_rows_filters_priority_bucket():
    rows = [
        {"sample_no": "1", "review_bucket": "calibration"},
        {"sample_no": "2", "review_bucket": "priority"},
        {"sample_no": "3", "review_bucket": "backup"},
        {"sample_no": "4", "review_bucket": "priority"},
    ]

    selected = select_source_rows(rows, bucket="priority")

    assert [row["sample_no"] for row in selected] == ["2", "4"]


@pytest.mark.asyncio
async def test_run_fixed_rescore_records_bucket_and_deepseek_model_in_manifest(tmp_path):
    input_path = tmp_path / "priority.csv"
    output_dir = tmp_path / "out"
    fields = [
        "review_bucket",
        "sample_no",
        "scenario",
        "candidate_id",
        "orientation",
        "F4_ER",
        "F4_IP",
        "F4_EX",
        "user_text",
        "candidate_text",
    ]
    with input_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "review_bucket": "priority",
                    "sample_no": "6",
                    "scenario": "同伴关系",
                    "candidate_id": "c2",
                    "orientation": "认知共情型",
                    "F4_ER": "2",
                    "F4_IP": "2",
                    "F4_EX": "2",
                    "user_text": "学生原文",
                    "candidate_text": "候选回复",
                },
                {
                    "review_bucket": "backup",
                    "sample_no": "7",
                    "scenario": "同伴关系",
                    "candidate_id": "c2",
                    "orientation": "认知共情型",
                    "F4_ER": "2",
                    "F4_IP": "2",
                    "F4_EX": "2",
                    "user_text": "备份原文",
                    "candidate_text": "备份候选",
                },
            ]
        )

    await run_fixed_rescore(
        input_scores_path=input_path,
        output_dir=output_dir,
        settings=Settings(
            LLM_PROVIDER="mock",
            DEEPSEEK_MODEL="deepseek-v4-pro",
            CRITIC_SAMPLE_COUNT=3,
        ),
        repeats=1,
        blind_path=tmp_path / "missing_blind.csv",
        bucket="priority",
    )

    manifest = json.loads(
        (output_dir / "f9_fixed_candidate_rescore_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    summary_rows = _read_csv(output_dir / "f9_fixed_candidate_rescore_summary.csv")

    assert manifest["input_rows"] == 2
    assert manifest["scored_rows"] == 1
    assert manifest["bucket"] == "priority"
    assert manifest["deepseek_model"] == "deepseek-v4-pro"
    assert [row["sample_no"] for row in summary_rows] == ["6"]
