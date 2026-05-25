from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


BLIND_COLUMNS = [
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
]

F4_HOLDOUT_COLUMNS = ["sample_no", "F4_ER", "F4_IP", "F4_EX"]


@dataclass(frozen=True)
class CandidateRow:
    candidate_db_id: int
    turn_id: int
    source_session_id: str
    candidate_id: str
    scenario: str
    orientation: str
    user_message: str
    history: str
    candidate_text: str
    f4_er: int
    f4_ip: int
    f4_ex: int
    weighted_total: float
    boundary_flag: bool
    boundary_reason: str


@dataclass(frozen=True)
class SampledCandidate:
    sample_no: int
    row: CandidateRow
    score_bucket: str


@dataclass(frozen=True)
class F9ExportResult:
    output_dir: Path
    blind_annotation_path: Path
    f4_holdout_path: Path
    manifest_path: Path
    sample_count: int
    source_candidate_count: int


def _prefix_clause(prefixes: list[str], params: list[str]) -> str:
    if not prefixes:
        return ""
    params.extend(f"{prefix}%" for prefix in prefixes)
    return "(" + " OR ".join("t.session_id LIKE ?" for _ in prefixes) + ")"


def _exclude_clause(scenarios: list[str], params: list[str]) -> str:
    if not scenarios:
        return ""
    params.extend(scenarios)
    return "COALESCE(t.scenario, '') NOT IN (" + ",".join("?" for _ in scenarios) + ")"


def _turn_histories(con: sqlite3.Connection) -> dict[int, str]:
    rows = con.execute(
        """
        SELECT id, session_id, user_message, assistant_message
        FROM turns
        WHERE status = 'answered'
        ORDER BY session_id, id
        """
    ).fetchall()
    histories: dict[int, str] = {}
    prior_by_session: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        session_id = str(row["session_id"])
        histories[int(row["id"])] = json.dumps(
            prior_by_session[session_id], ensure_ascii=False
        )
        prior_by_session[session_id].extend(
            [
                {"role": "student", "text": row["user_message"]},
                {"role": "assistant", "text": row["assistant_message"]},
            ]
        )
    return histories


def load_candidate_rows(
    database_path: str | Path,
    session_prefixes: Iterable[str] | None = None,
    exclude_scenarios: Iterable[str] | None = None,
) -> list[CandidateRow]:
    con = sqlite3.connect(database_path)
    con.row_factory = sqlite3.Row
    try:
        histories = _turn_histories(con)
        params: list[str] = []
        where_parts = ["t.status = 'answered'"]
        prefix_clause = _prefix_clause(list(session_prefixes or []), params)
        if prefix_clause:
            where_parts.append(prefix_clause)
        exclude_clause = _exclude_clause(list(exclude_scenarios or []), params)
        if exclude_clause:
            where_parts.append(exclude_clause)
        where_sql = " AND ".join(where_parts)
        rows = con.execute(
            f"""
            SELECT
                c.id AS candidate_db_id,
                t.id AS turn_id,
                t.session_id AS source_session_id,
                c.candidate_id,
                COALESCE(t.scenario, '') AS scenario,
                c.orientation,
                t.user_message,
                c.text AS candidate_text,
                c.epitome_er,
                c.epitome_ip,
                c.epitome_ex,
                c.weighted_total,
                c.boundary_flag,
                c.boundary_reason
            FROM candidates c
            JOIN turns t ON t.id = c.turn_id
            WHERE {where_sql}
            ORDER BY c.id
            """,
            params,
        ).fetchall()
    finally:
        con.close()

    return [
        CandidateRow(
            candidate_db_id=int(row["candidate_db_id"]),
            turn_id=int(row["turn_id"]),
            source_session_id=str(row["source_session_id"]),
            candidate_id=str(row["candidate_id"]),
            scenario=str(row["scenario"]),
            orientation=str(row["orientation"]),
            user_message=str(row["user_message"]),
            history=histories.get(int(row["turn_id"]), "[]"),
            candidate_text=str(row["candidate_text"]),
            f4_er=int(row["epitome_er"]),
            f4_ip=int(row["epitome_ip"]),
            f4_ex=int(row["epitome_ex"]),
            weighted_total=float(row["weighted_total"]),
            boundary_flag=bool(row["boundary_flag"]),
            boundary_reason=str(row["boundary_reason"] or ""),
        )
        for row in rows
    ]


def _score_thresholds(rows: list[CandidateRow]) -> tuple[float, float]:
    scores = sorted(row.weighted_total for row in rows)
    if not scores:
        return 0.0, 0.0
    low_index = int((len(scores) - 1) / 3)
    high_index = int((len(scores) - 1) * 2 / 3)
    return scores[low_index], scores[high_index]


def _score_bucket(row: CandidateRow, low_cut: float, high_cut: float) -> str:
    if row.weighted_total <= low_cut:
        return "low"
    if row.weighted_total <= high_cut:
        return "mid"
    return "high"


def _allocate_evenly(
    available_by_key: dict[str, int], total: int, rng: random.Random
) -> dict[str, int]:
    if total > sum(available_by_key.values()):
        raise ValueError("sample_size exceeds available candidates")

    quotas = {key: 0 for key in available_by_key}
    while sum(quotas.values()) < total:
        eligible = [
            key
            for key in sorted(available_by_key)
            if quotas[key] < available_by_key[key]
        ]
        if not eligible:
            break
        rng.shuffle(eligible)
        for key in eligible:
            if sum(quotas.values()) >= total:
                break
            quotas[key] += 1
    return quotas


def select_stratified_sample(
    rows: list[CandidateRow],
    sample_size: int,
    seed: int,
) -> list[SampledCandidate]:
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    if sample_size > len(rows):
        raise ValueError(
            f"sample_size {sample_size} exceeds available candidates {len(rows)}"
        )

    rng = random.Random(seed)
    low_cut, high_cut = _score_thresholds(rows)
    bucket_by_row = {
        row: _score_bucket(row, low_cut=low_cut, high_cut=high_cut) for row in rows
    }
    rows_by_scenario: dict[str, list[CandidateRow]] = defaultdict(list)
    for row in rows:
        rows_by_scenario[row.scenario].append(row)

    scenario_quotas = _allocate_evenly(
        {key: len(value) for key, value in rows_by_scenario.items()},
        sample_size,
        rng,
    )
    selected: list[CandidateRow] = []

    for scenario in sorted(scenario_quotas):
        scenario_rows = rows_by_scenario[scenario]
        rows_by_orientation: dict[str, list[CandidateRow]] = defaultdict(list)
        for row in scenario_rows:
            rows_by_orientation[row.orientation].append(row)
        orientation_quotas = _allocate_evenly(
            {key: len(value) for key, value in rows_by_orientation.items()},
            scenario_quotas[scenario],
            rng,
        )

        for orientation in sorted(orientation_quotas):
            orientation_rows = rows_by_orientation[orientation]
            rows_by_bucket: dict[str, list[CandidateRow]] = defaultdict(list)
            for row in orientation_rows:
                rows_by_bucket[bucket_by_row[row]].append(row)
            bucket_quotas = _allocate_evenly(
                {key: len(value) for key, value in rows_by_bucket.items()},
                orientation_quotas[orientation],
                rng,
            )

            for bucket in sorted(bucket_quotas):
                bucket_rows = sorted(
                    rows_by_bucket[bucket], key=lambda row: row.candidate_db_id
                )
                rng.shuffle(bucket_rows)
                selected.extend(bucket_rows[: bucket_quotas[bucket]])

    if len(selected) < sample_size:
        selected_ids = {row.candidate_db_id for row in selected}
        remaining = [
            row for row in rows if row.candidate_db_id not in selected_ids
        ]
        rng.shuffle(remaining)
        selected.extend(remaining[: sample_size - len(selected)])

    selected = selected[:sample_size]
    rng.shuffle(selected)
    return [
        SampledCandidate(
            sample_no=index,
            row=row,
            score_bucket=bucket_by_row[row],
        )
        for index, row in enumerate(selected, start=1)
    ]


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _sample_distribution(sampled: list[SampledCandidate]) -> dict[str, dict[str, int]]:
    return {
        "scenario": dict(Counter(item.row.scenario for item in sampled)),
        "orientation": dict(Counter(item.row.orientation for item in sampled)),
        "score_bucket": dict(Counter(item.score_bucket for item in sampled)),
        "boundary_flag": dict(Counter(str(item.row.boundary_flag) for item in sampled)),
    }


def export_f9_annotation_package(
    database_path: str | Path,
    output_dir: str | Path,
    sample_size: int = 40,
    seed: int = 20260525,
    session_prefixes: Iterable[str] | None = None,
    exclude_scenarios: Iterable[str] | None = None,
) -> F9ExportResult:
    prefixes = list(session_prefixes or [])
    excluded = list(exclude_scenarios or [])
    rows = load_candidate_rows(
        database_path=database_path,
        session_prefixes=prefixes,
        exclude_scenarios=excluded,
    )
    sampled = select_stratified_sample(rows, sample_size=sample_size, seed=seed)

    output = Path(output_dir)
    blind_annotation_path = output / "f9_blind_annotation.csv"
    f4_holdout_path = output / "f9_f4_scores_holdout.csv"
    manifest_path = output / "f9_sampling_manifest.json"

    _write_csv(
        blind_annotation_path,
        BLIND_COLUMNS,
        [
            {
                "sample_no": item.sample_no,
                "scenario": item.row.scenario,
                "orientation": item.row.orientation,
                "用户倾诉": item.row.user_message,
                "对话历史": item.row.history,
                "候选文本": item.row.candidate_text,
                "A_ER": "",
                "A_IP": "",
                "A_EX": "",
                "B_ER": "",
                "B_IP": "",
                "B_EX": "",
            }
            for item in sampled
        ],
    )
    _write_csv(
        f4_holdout_path,
        F4_HOLDOUT_COLUMNS,
        [
            {
                "sample_no": item.sample_no,
                "F4_ER": item.row.f4_er,
                "F4_IP": item.row.f4_ip,
                "F4_EX": item.row.f4_ex,
            }
            for item in sampled
        ],
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "database_path": str(Path(database_path)),
                "sample_size": sample_size,
                "seed": seed,
                "session_prefixes": prefixes,
                "exclude_scenarios": excluded,
                "source_candidate_count": len(rows),
                "selected_candidate_count": len(sampled),
                "blind_annotation_path": str(blind_annotation_path),
                "f4_holdout_path": str(f4_holdout_path),
                "sample_distribution": _sample_distribution(sampled),
                "samples": [
                    {
                        "sample_no": item.sample_no,
                        "source_session_id": item.row.source_session_id,
                        "turn_id": item.row.turn_id,
                        "candidate_db_id": item.row.candidate_db_id,
                        "candidate_id": item.row.candidate_id,
                        "scenario": item.row.scenario,
                        "orientation": item.row.orientation,
                        "weighted_total": item.row.weighted_total,
                        "score_bucket": item.score_bucket,
                        "boundary_flag": item.row.boundary_flag,
                        "boundary_reason": item.row.boundary_reason,
                    }
                    for item in sampled
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return F9ExportResult(
        output_dir=output,
        blind_annotation_path=blind_annotation_path,
        f4_holdout_path=f4_holdout_path,
        manifest_path=manifest_path,
        sample_count=len(sampled),
        source_candidate_count=len(rows),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export F9 blind annotation package.")
    parser.add_argument("--database-path", default="local-dev.sqlite")
    parser.add_argument("--output-dir", default="docs/corpus/f9/baseline")
    parser.add_argument("--sample-size", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260525)
    parser.add_argument(
        "--session-prefix",
        action="append",
        default=[],
        help="Only include turns whose session_id starts with this prefix.",
    )
    parser.add_argument(
        "--exclude-scenario",
        action="append",
        default=[],
        help="Exclude a scenario label from the sampling frame.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = export_f9_annotation_package(
        database_path=args.database_path,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        seed=args.seed,
        session_prefixes=args.session_prefix,
        exclude_scenarios=args.exclude_scenario,
    )
    print(f"blind_annotation_path={result.blind_annotation_path}")
    print(f"f4_holdout_path={result.f4_holdout_path}")
    print(f"manifest_path={result.manifest_path}")
    print(f"sample_count={result.sample_count}")
    print(f"source_candidate_count={result.source_candidate_count}")


if __name__ == "__main__":
    main()
