import csv
from pathlib import Path

import pytest

from scripts.corpus.f9_pairwise_package import (
    HUMAN_ANNOTATION_COLUMNS,
    PAIR_PACKAGE_COLUMNS,
    build_annotation_rows,
    build_pair_rows,
    validate_pair_provenance,
    write_annotation_template,
    write_pair_package,
)


def _row(sample_no: str, candidate_id: str, text: str) -> dict[str, str]:
    return {
        "sample_no": sample_no,
        "source": "generated",
        "candidate_id": candidate_id,
        "scenario": "同伴关系",
        "activated_casel_json": '["自我觉察引导", "关系技能培养"]',
        "orientation": "情感共情型" if candidate_id == "c1" else "认知共情型",
        "用户倾诉": "他们没叫我进小群。",
        "对话历史": '[{"role":"student","text":"前文"}]',
        "候选文本": text,
        "generator_run_id": "run-1",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "generator_model": "deepseek-v4-flash",
        "generator_thinking": "disabled",
        "f3_prompt_bundle_hash": "hash-1",
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_pair_rows_groups_complete_c1_c2_pairs():
    rows = [
        _row("3", "c2", "候选二"),
        _row("3", "c1", "候选一"),
        _row("4", "c1", "缺少 c2"),
    ]

    pair_rows = build_pair_rows(rows)

    assert len(pair_rows) == 1
    assert pair_rows[0] == {
        "pair_id": "sample-3",
        "sample_no": "3",
        "scenario": "同伴关系",
        "activated_casel_json": '["自我觉察引导", "关系技能培养"]',
        "user_text": "他们没叫我进小群。",
        "history_json": '[{"role":"student","text":"前文"}]',
        "c1_orientation": "情感共情型",
        "c1_text": "候选一",
        "c2_orientation": "认知共情型",
        "c2_text": "候选二",
        "source_run": "generated",
        "generator_run_id": "run-1",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "generator_model": "deepseek-v4-flash",
        "generator_thinking": "disabled",
        "f3_prompt_bundle_hash": "hash-1",
        "notes": "",
    }


def test_build_pair_rows_reads_priority_queue_style_columns():
    rows = [
        {
            "sample_no": "6",
            "review_bucket": "priority",
            "candidate_id": "c1",
            "scenario": "亲子摩擦",
            "activated_casel_json": "",
            "orientation": "情感共情型",
            "user_text": "我爸很失望。",
            "history_json": "[]",
            "candidate_text": "候选一",
        },
        {
            "sample_no": "6",
            "review_bucket": "priority",
            "candidate_id": "c2",
            "scenario": "亲子摩擦",
            "activated_casel_json": "",
            "orientation": "认知共情型",
            "user_text": "我爸很失望。",
            "history_json": "[]",
            "candidate_text": "候选二",
        },
    ]

    pair_rows = build_pair_rows(rows)

    assert pair_rows[0]["user_text"] == "我爸很失望。"
    assert pair_rows[0]["c2_text"] == "候选二"
    assert pair_rows[0]["activated_casel_json"] == (
        '["自我觉察引导", "自我管理引导", "社会觉察培养", "关系技能培养"]'
    )
    assert pair_rows[0]["source_run"] == "priority"
    assert pair_rows[0]["f3_prompt_bundle_hash"] == ""


def test_validate_pair_provenance_rejects_missing_or_mismatched_hash():
    pair_rows = build_pair_rows([_row("3", "c1", "候选一"), _row("3", "c2", "候选二")])

    validate_pair_provenance(pair_rows, expected_f3_prompt_bundle_hash="hash-1")

    missing = [dict(pair_rows[0], generator_run_id="")]
    with pytest.raises(ValueError, match="missing provenance"):
        validate_pair_provenance(missing, expected_f3_prompt_bundle_hash="hash-1")

    mismatched = [dict(pair_rows[0], f3_prompt_bundle_hash="old-hash")]
    with pytest.raises(ValueError, match="f3_prompt_bundle_hash"):
        validate_pair_provenance(mismatched, expected_f3_prompt_bundle_hash="hash-1")


def test_write_pair_package_uses_excel_friendly_utf8_bom(tmp_path):
    output_path = tmp_path / "pairs.csv"
    pair_rows = build_pair_rows([_row("3", "c1", "候选一"), _row("3", "c2", "候选二")])

    written = write_pair_package(output_path, pair_rows)

    assert written == output_path
    assert output_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert list(_read_csv(output_path)[0].keys()) == PAIR_PACKAGE_COLUMNS


def test_write_annotation_template_preserves_context_and_blank_human_fields(tmp_path):
    output_path = tmp_path / "annotations.csv"
    pair_rows = build_pair_rows([_row("3", "c1", "候选一"), _row("3", "c2", "候选二")])

    annotation_rows = build_annotation_rows(pair_rows)
    written = write_annotation_template(output_path, annotation_rows)

    assert written == output_path
    assert output_path.read_bytes().startswith(b"\xef\xbb\xbf")
    row = _read_csv(output_path)[0]
    assert list(row.keys()) == HUMAN_ANNOTATION_COLUMNS
    assert row["pair_id"] == "sample-3"
    assert row["user_text"] == "他们没叫我进小群。"
    assert row["c1_text"] == "候选一"
    assert row["human_preference"] == ""
    assert row["annotator_id"] == ""
