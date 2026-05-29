import csv
import json
from pathlib import Path

import pytest

from app.services.critic_pairwise import PairwiseSampleResult
from scripts.corpus.f9_pairwise_judge import (
    RUN_COLUMNS,
    SUMMARY_COLUMNS,
    run_pairwise_judge,
)


class FakePairwiseService:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    async def judge_sample(self, context, candidate_a, candidate_b, sample_no):
        self.calls.append((context, candidate_a, candidate_b, sample_no))
        return self.results.pop(0)


def _write_pairs(path: Path):
    fields = [
        "pair_id",
        "sample_no",
        "scenario",
        "activated_casel_json",
        "user_text",
        "history_json",
        "c1_orientation",
        "c1_text",
        "c2_orientation",
        "c2_text",
        "source_run",
        "generator_run_id",
        "generated_at",
        "generator_model",
        "generator_thinking",
        "f3_prompt_bundle_hash",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
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
        )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.asyncio
async def test_run_pairwise_judge_writes_runs_summary_and_manifest(tmp_path):
    pair_path = tmp_path / "pairs.csv"
    output_dir = tmp_path / "out"
    _write_pairs(pair_path)
    service = FakePairwiseService(
        [
            PairwiseSampleResult(
                "sample-3",
                1,
                "c1",
                "c1",
                True,
                "c1",
                False,
                "c1",
                judgment_1_epitome_comparison={"ER": "c1", "IP": "tie", "EX": "c2"},
                judgment_2_epitome_comparison={"ER": "c1", "IP": "tie", "EX": "c2"},
                judgment_1_casel_comparisons={
                    "自我觉察引导": "c1",
                    "关系技能培养": "tie",
                },
                judgment_2_casel_comparisons={
                    "自我觉察引导": "c1",
                    "关系技能培养": "tie",
                },
            ),
            PairwiseSampleResult("sample-3", 2, "c1", None, False, None, False, "tie"),
            PairwiseSampleResult("sample-3", 3, "c1", "c1", True, "c1", False, "c1"),
        ]
    )

    paths = await run_pairwise_judge(
        pair_package_path=pair_path,
        output_dir=output_dir,
        service=service,
        pairwise_sample_count=3,
    )

    run_rows = _read_csv(paths["runs"])
    summary_rows = _read_csv(paths["summary"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

    assert list(run_rows[0].keys()) == RUN_COLUMNS
    assert len(run_rows) == 3
    assert run_rows[0]["repeat_no"] == "1"
    assert run_rows[0]["stable"] == "true"
    assert json.loads(run_rows[0]["judgment_1_epitome_comparison_json"]) == {
        "ER": "c1",
        "IP": "tie",
        "EX": "c2",
    }
    assert json.loads(run_rows[0]["judgment_1_casel_comparisons_json"]) == {
        "自我觉察引导": "c1",
        "关系技能培养": "tie",
    }
    assert list(summary_rows[0].keys()) == SUMMARY_COLUMNS
    assert summary_rows[0]["pair_id"] == "sample-3"
    assert summary_rows[0]["activated_casel_json"] == '["自我觉察引导", "关系技能培养"]'
    assert summary_rows[0]["stable_votes_c1"] == "2"
    assert summary_rows[0]["unstable_count"] == "1"
    assert summary_rows[0]["winner_id"] == "c1"
    assert summary_rows[0]["pairwise_confidence"] == "majority_with_unstable"
    assert manifest["input_pairs"] == 1
    assert manifest["judged_pairs"] == 1
    assert manifest["pairwise_sample_count"] == 3
    assert manifest["critic_model"] == "deepseek-v4-pro"
    assert manifest["critic_thinking"] == "enabled"
    assert manifest["llm_timeout"] == 10.0
    assert manifest["generator_models"] == ["deepseek-v4-flash"]
    assert manifest["generator_thinking_values"] == ["disabled"]
    assert manifest["f3_prompt_bundle_hashes"] == ["hash-1"]
    assert manifest["generator_run_ids"] == ["run-1"]
    assert service.calls[0][0].history[0].text == "前文"
    assert service.calls[0][0].activated_casel == ["自我觉察引导", "关系技能培养"]
    assert service.calls[0][1].candidate_id == "c1"
