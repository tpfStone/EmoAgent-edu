import csv
from pathlib import Path

from scripts.corpus.f9_pairwise_package import (
    HUMAN_ANNOTATION_COLUMNS,
    PAIR_PACKAGE_COLUMNS,
    build_annotation_rows,
    build_pair_rows,
    write_annotation_template,
    write_pair_package,
)


def _row(sample_no: str, candidate_id: str, text: str) -> dict[str, str]:
    return {
        "sample_no": sample_no,
        "source": "generated",
        "candidate_id": candidate_id,
        "scenario": "同伴关系",
        "orientation": "共情型" if candidate_id == "c1" else "引导反思型",
        "用户倾诉": "他们没叫我进小群。",
        "对话历史": '[{"role":"student","text":"前文"}]',
        "候选文本": text,
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
        "user_text": "他们没叫我进小群。",
        "history_json": '[{"role":"student","text":"前文"}]',
        "c1_orientation": "共情型",
        "c1_text": "候选一",
        "c2_orientation": "引导反思型",
        "c2_text": "候选二",
        "source_run": "generated",
        "notes": "",
    }


def test_build_pair_rows_reads_priority_queue_style_columns():
    rows = [
        {
            "sample_no": "6",
            "review_bucket": "priority",
            "candidate_id": "c1",
            "scenario": "亲子摩擦",
            "orientation": "共情型",
            "user_text": "我爸很失望。",
            "history_json": "[]",
            "candidate_text": "候选一",
        },
        {
            "sample_no": "6",
            "review_bucket": "priority",
            "candidate_id": "c2",
            "scenario": "亲子摩擦",
            "orientation": "引导反思型",
            "user_text": "我爸很失望。",
            "history_json": "[]",
            "candidate_text": "候选二",
        },
    ]

    pair_rows = build_pair_rows(rows)

    assert pair_rows[0]["user_text"] == "我爸很失望。"
    assert pair_rows[0]["c2_text"] == "候选二"
    assert pair_rows[0]["source_run"] == "priority"


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
