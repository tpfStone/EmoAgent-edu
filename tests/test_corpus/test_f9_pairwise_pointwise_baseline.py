import csv
from pathlib import Path

import pytest

from app.schemas.critic import CandidateScore, CriticEvaluateResponse, EpitomeScore
from scripts.corpus.f9_pairwise_pointwise_baseline import (
    BASELINE_COLUMNS,
    run_pointwise_baseline,
)


class FakeCriticService:
    def __init__(self, response):
        self.response = response
        self.requests = []

    async def evaluate(self, request):
        self.requests.append(request)
        return self.response


def _score(candidate_id: str, total: float, boundary: bool = False) -> CandidateScore:
    return CandidateScore(
        candidate_id=candidate_id,
        epitome=EpitomeScore(ER=2, IP=1, EX=1),
        casel={},
        boundary_flag=boundary,
        boundary_reason="boundary" if boundary else "",
        weighted_total=total,
        rationale="pointwise",
    )


def _write_pairs(path: Path):
    fields = [
        "pair_id",
        "sample_no",
        "scenario",
        "user_text",
        "history_json",
        "c1_orientation",
        "c1_text",
        "c2_orientation",
        "c2_text",
        "source_run",
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
                "user_text": "他们没叫我进小群。",
                "history_json": "[]",
                "c1_orientation": "共情型",
                "c1_text": "候选一",
                "c2_orientation": "引导反思型",
                "c2_text": "候选二",
                "source_run": "generated",
                "notes": "",
            }
        )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.asyncio
async def test_run_pointwise_baseline_writes_weighted_total_winner(tmp_path):
    pair_path = tmp_path / "pairs.csv"
    output_path = tmp_path / "baseline.csv"
    _write_pairs(pair_path)
    critic = FakeCriticService(
        CriticEvaluateResponse(
            best_candidate_id="c2",
            scores=[_score("c1", 3.0), _score("c2", 4.0)],
            preference_pair=None,
        )
    )

    written = await run_pointwise_baseline(
        pair_package_path=pair_path,
        output_path=output_path,
        critic_service=critic,
    )
    rows = _read_csv(written)

    assert written == output_path
    assert output_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert list(rows[0].keys()) == BASELINE_COLUMNS
    assert rows[0]["pair_id"] == "sample-3"
    assert rows[0]["c1_weighted_total"] == "3.000"
    assert rows[0]["c2_weighted_total"] == "4.000"
    assert rows[0]["pointwise_winner"] == "c2"
    assert rows[0]["pointwise_tie"] == "false"
    assert critic.requests[0].candidates[0].candidate_id == "c1"


@pytest.mark.asyncio
async def test_run_pointwise_baseline_marks_equal_totals_as_tie(tmp_path):
    pair_path = tmp_path / "pairs.csv"
    output_path = tmp_path / "baseline.csv"
    _write_pairs(pair_path)
    critic = FakeCriticService(
        CriticEvaluateResponse(
            best_candidate_id="c1",
            scores=[_score("c1", 4.0), _score("c2", 4.0)],
            preference_pair=None,
        )
    )

    await run_pointwise_baseline(pair_path, output_path, critic)
    rows = _read_csv(output_path)

    assert rows[0]["pointwise_winner"] == "tie"
    assert rows[0]["pointwise_tie"] == "true"
