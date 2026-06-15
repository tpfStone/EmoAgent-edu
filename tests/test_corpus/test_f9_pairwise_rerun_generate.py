import csv
import json
from pathlib import Path

import pytest

from app.config import Settings
from app.schemas.critic import CandidateScore, CriticEvaluateResponse, EpitomeScore
from app.schemas.generator import (
    GeneratorCandidate,
    GeneratorGenerateResponse,
)
from app.services.generator_service import GENERATOR_FALLBACK_TEXT
from scripts.corpus.f9_pairwise_rerun_generate import (
    RERUN_CANDIDATE_COLUMNS,
    build_filtered_pair_rows,
    run_pairwise_rerun_generation,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _candidate_row(
    sample_no: str,
    candidate_id: str,
    *,
    scenario: str = "学业压力",
    user_text: str | None = None,
    candidate_text: str | None = None,
    boundary: str = "false",
) -> dict[str, str]:
    return {
        "sample_no": sample_no,
        "source": "phase-a-rerun",
        "candidate_id": candidate_id,
        "scenario": scenario,
        "orientation": "共情型" if candidate_id == "c1" else "引导反思型",
        "user_text": user_text or f"用户倾诉 {sample_no}",
        "history_json": "[]",
        "candidate_text": candidate_text or f"候选 {sample_no} {candidate_id}",
        "boundary_flag": boundary,
        "boundary_reason": "boundary" if boundary == "true" else "",
        "F4_ER": "2",
        "F4_IP": "2",
        "F4_EX": "1",
        "weighted_total": "5.000",
        "rationale": "ok",
        "generator_run_id": "run-1",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "generator_model": "deepseek-v4-flash",
        "generator_thinking": "disabled",
        "f3_prompt_bundle_hash": "hash-1",
    }


def test_build_filtered_pair_rows_filters_bad_pairs_and_duplicate_user_text():
    rows = [
        _candidate_row("1", "c1"),
        _candidate_row("1", "c2"),
        _candidate_row("2", "c1", candidate_text=GENERATOR_FALLBACK_TEXT),
        _candidate_row("2", "c2"),
        _candidate_row("3", "c1", boundary="true"),
        _candidate_row("3", "c2", boundary="true"),
        _candidate_row("4", "c1", user_text="same user text"),
        _candidate_row("4", "c2", user_text="same user text"),
        _candidate_row("5", "c1", user_text="same user text"),
        _candidate_row("5", "c2", user_text="same user text"),
    ]

    pair_rows, excluded = build_filtered_pair_rows(rows, target_pair_count=24)

    assert [row["pair_id"] for row in pair_rows] == ["sample-1", "sample-4"]
    assert excluded == {
        "generator_fallback": 1,
        "double_boundary": 1,
        "duplicate_user_text": 1,
    }


def test_build_filtered_pair_rows_balances_scenarios_before_filling_remainder():
    rows = []
    for scenario in ["学业压力", "同伴关系", "亲子摩擦"]:
        for sample_no in range(len(rows) + 1, len(rows) + 7, 2):
            rows.append(_candidate_row(str(sample_no), "c1", scenario=scenario))
            rows.append(_candidate_row(str(sample_no), "c2", scenario=scenario))

    pair_rows, excluded = build_filtered_pair_rows(rows, target_pair_count=6)

    assert excluded == {}
    assert len(pair_rows) == 6
    scenario_counts = {}
    for row in pair_rows:
        scenario_counts[row["scenario"]] = scenario_counts.get(row["scenario"], 0) + 1
    assert scenario_counts == {"学业压力": 2, "同伴关系": 2, "亲子摩擦": 2}


class FakeGeneratorService:
    def __init__(self):
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        sample_no = request.session_id.rsplit("-", 1)[-1]
        return GeneratorGenerateResponse(
            candidates=[
                GeneratorCandidate(
                    candidate_id="c1",
                    orientation="共情型",
                    text=f"生成候选 {sample_no} c1",
                ),
                GeneratorCandidate(
                    candidate_id="c2",
                    orientation="引导反思型",
                    text=f"生成候选 {sample_no} c2",
                ),
            ]
        )


class FakeCriticService:
    def __init__(self):
        self.requests = []

    async def evaluate(self, request):
        self.requests.append(request)
        return CriticEvaluateResponse(
            best_candidate_id="c1",
            scores=[
                CandidateScore(
                    candidate_id=candidate.candidate_id,
                    epitome=EpitomeScore(ER=2, IP=2, EX=1),
                    casel={},
                    boundary_flag=False,
                    boundary_reason="",
                    weighted_total=5.0,
                    rationale="ok",
                )
                for candidate in request.candidates
            ],
            preference_pair=None,
        )


@pytest.mark.asyncio
async def test_run_pairwise_rerun_generation_writes_outputs_and_manifest(tmp_path):
    analysis_path = tmp_path / "analysis.csv"
    blind_path = tmp_path / "blind.csv"
    output_root = tmp_path / "pairwise-selection-pilot"
    _write_csv(
        analysis_path,
        ["sample_no", "scenario", "orientation", "用户倾诉", "候选文本"],
        [
            {
                "sample_no": "1",
                "scenario": "学业压力",
                "orientation": "共情型",
                "用户倾诉": "作业太多了。",
                "候选文本": "old",
            },
            {
                "sample_no": "2",
                "scenario": "同伴关系",
                "orientation": "共情型",
                "用户倾诉": "朋友没叫我。",
                "候选文本": "old",
            },
            {
                "sample_no": "3",
                "scenario": "亲子摩擦",
                "orientation": "共情型",
                "用户倾诉": "我妈误会我。",
                "候选文本": "old",
            },
        ],
    )
    _write_csv(
        blind_path,
        ["sample_no", "对话历史"],
        [
            {"sample_no": "1", "对话历史": "[]"},
            {"sample_no": "2", "对话历史": "[]"},
            {"sample_no": "3", "对话历史": "[]"},
        ],
    )

    paths = await run_pairwise_rerun_generation(
        analysis_path=analysis_path,
        blind_path=blind_path,
        output_root=output_root,
        settings=Settings(
            _env_file=None,
            LLM_PROVIDER="mock",
            DEEPSEEK_MODEL="deepseek-v4-flash",
            DEEPSEEK_THINKING="disabled",
            CRITIC_DEEPSEEK_MODEL="deepseek-v4-pro",
            CRITIC_DEEPSEEK_THINKING="enabled",
        ),
        target_pair_count=3,
        generator_service=FakeGeneratorService(),
        critic_service=FakeCriticService(),
        run_id="run-test",
        generated_at="2026-05-27T00:00:00+00:00",
        prompt_bundle_hash="hash-test",
    )

    candidates = _read_csv(paths["candidates"])
    pairs = _read_csv(paths["pairs"])
    annotations = _read_csv(paths["annotations"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

    assert list(candidates[0].keys()) == RERUN_CANDIDATE_COLUMNS
    assert len(candidates) == 6
    assert len(pairs) == 3
    assert annotations[0]["human_preference"] == ""
    assert pairs[0]["generator_run_id"] == "run-test"
    assert pairs[0]["generator_model"] == "deepseek-v4-flash"
    assert pairs[0]["generator_thinking"] == "disabled"
    assert pairs[0]["f3_prompt_bundle_hash"] == "hash-test"
    assert manifest["selected_pairs"] == 3
    assert manifest["target_pair_count"] == 3
    assert manifest["generator_model"] == "deepseek-v4-flash"
    assert manifest["generator_thinking"] == "disabled"
    assert manifest["critic_model"] == "deepseek-v4-pro"
    assert manifest["critic_thinking"] == "enabled"
    assert manifest["excluded_counts"] == {}


@pytest.mark.asyncio
async def test_run_pairwise_rerun_generation_can_limit_sample_nos(tmp_path):
    analysis_path = tmp_path / "analysis.csv"
    blind_path = tmp_path / "blind.csv"
    output_root = tmp_path / "pairwise-selection-pilot"
    _write_csv(
        analysis_path,
        ["sample_no", "scenario", "orientation", "用户倾诉", "候选文本"],
        [
            {
                "sample_no": "1",
                "scenario": "学业压力",
                "orientation": "共情型",
                "用户倾诉": "作业太多了。",
                "候选文本": "old",
            },
            {
                "sample_no": "2",
                "scenario": "同伴关系",
                "orientation": "共情型",
                "用户倾诉": "朋友没叫我。",
                "候选文本": "old",
            },
            {
                "sample_no": "3",
                "scenario": "亲子摩擦",
                "orientation": "共情型",
                "用户倾诉": "我妈误会我。",
                "候选文本": "old",
            },
        ],
    )
    _write_csv(
        blind_path,
        ["sample_no", "对话历史"],
        [
            {"sample_no": "1", "对话历史": "[]"},
            {"sample_no": "2", "对话历史": "[]"},
            {"sample_no": "3", "对话历史": "[]"},
        ],
    )
    generator = FakeGeneratorService()

    paths = await run_pairwise_rerun_generation(
        analysis_path=analysis_path,
        blind_path=blind_path,
        output_root=output_root,
        settings=Settings(_env_file=None, LLM_PROVIDER="mock"),
        target_pair_count=2,
        sample_nos=[1, 3],
        generator_service=generator,
        critic_service=FakeCriticService(),
        run_id="run-test",
        generated_at="2026-05-27T00:00:00+00:00",
        prompt_bundle_hash="hash-test",
    )

    pairs = _read_csv(paths["pairs"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

    assert [row["sample_no"] for row in pairs] == ["1", "3"]
    assert [request.session_id for request in generator.requests] == [
        "f9-pairwise-rerun-1",
        "f9-pairwise-rerun-3",
    ]
    assert manifest["source_sample_nos"] == [1, 3]


class FailingCriticService:
    async def evaluate(self, request):
        raise AssertionError("critic should not be called when score_candidates=False")


@pytest.mark.asyncio
async def test_run_pairwise_rerun_generation_can_skip_critic_for_sidecar(tmp_path):
    analysis_path = tmp_path / "analysis.csv"
    blind_path = tmp_path / "blind.csv"
    output_root = tmp_path / "pairwise-selection-pilot"
    _write_csv(
        analysis_path,
        ["sample_no", "scenario", "orientation", "用户倾诉", "候选文本"],
        [
            {
                "sample_no": "1",
                "scenario": "学业压力",
                "orientation": "共情型",
                "用户倾诉": "作业太多了。",
                "候选文本": "old",
            }
        ],
    )
    _write_csv(blind_path, ["sample_no", "对话历史"], [{"sample_no": "1", "对话历史": "[]"}])

    paths = await run_pairwise_rerun_generation(
        analysis_path=analysis_path,
        blind_path=blind_path,
        output_root=output_root,
        settings=Settings(_env_file=None, LLM_PROVIDER="mock"),
        target_pair_count=1,
        sample_nos=[1],
        score_candidates=False,
        generator_service=FakeGeneratorService(),
        critic_service=FailingCriticService(),
        run_id="run-test",
        generated_at="2026-05-27T00:00:00+00:00",
        prompt_bundle_hash="hash-test",
    )

    candidates = _read_csv(paths["candidates"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

    assert candidates[0]["boundary_flag"] == "false"
    assert candidates[0]["F4_ER"] == ""
    assert manifest["score_candidates"] is False
