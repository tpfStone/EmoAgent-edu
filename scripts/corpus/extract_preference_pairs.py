from __future__ import annotations

import argparse
from collections import Counter
import json
from statistics import median
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scripts.corpus.models import PreferencePairRecord, write_jsonl


@dataclass(frozen=True)
class PreferenceExtractionResult:
    output_dir: Path
    chat_results_path: Path
    preference_pairs_path: Path
    summary_path: Path
    chat_count: int
    pair_count: int


def _load_samples(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return list(data.get("samples", []))


def _post_chat(api_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_lookup(scores: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(score.get("candidate_id")): score
        for score in scores
        if score.get("candidate_id")
    }


def _epitome_score(score: dict[str, Any], key: str) -> float | None:
    epitome = score.get("epitome")
    if not isinstance(epitome, dict):
        return None
    return _as_float(epitome.get(key))


def _casel_average(score: dict[str, Any]) -> float | None:
    casel = score.get("casel")
    if not isinstance(casel, dict) or not casel:
        return None
    values = [_as_float(value) for value in casel.values()]
    numeric_values = [value for value in values if value is not None]
    if len(numeric_values) != len(values):
        return None
    return sum(numeric_values) / len(numeric_values)


def _delta_summary(name: str, values: list[float]) -> str:
    if not values:
        return f"- {name}: not_available"
    sorted_values = sorted(values)
    return (
        f"- {name}: min={sorted_values[0]:.2f}, "
        f"median={median(sorted_values):.2f}, max={sorted_values[-1]:.2f}"
    )


def _metric_delta(
    pair: dict[str, Any], metric: Callable[[dict[str, Any]], float | None]
) -> float | None:
    scores = _score_lookup(list(pair.get("scores", [])))
    winner = scores.get(str(pair.get("winner_id")))
    loser = scores.get(str(pair.get("loser_id")))
    if winner is None or loser is None:
        return None
    winner_value = metric(winner)
    loser_value = metric(loser)
    if winner_value is None or loser_value is None:
        return None
    return winner_value - loser_value


def _build_dpo_diversity_summary(pair_rows: list[dict[str, Any]]) -> list[str]:
    lines = ["", "## DPO Diversity", ""]
    if not pair_rows:
        return lines + ["- preference_pairs: 0"]

    pattern_counts = Counter(
        f"{row['winner_id']} > {row['loser_id']}" for row in pair_rows
    )
    lines.extend(["### Winner/Loser Pattern", ""])
    for pattern, count in sorted(
        pattern_counts.items(), key=lambda item: (-item[1], item[0])
    ):
        lines.append(f"- {pattern}: {count}")

    score_deltas = [
        value
        for value in (
            _metric_delta(row, lambda score: _as_float(score.get("weighted_total")))
            for row in pair_rows
        )
        if value is not None
    ]
    ex_deltas = [
        value
        for value in (
            _metric_delta(row, lambda score: _epitome_score(score, "EX"))
            for row in pair_rows
        )
        if value is not None
    ]
    casel_deltas = [
        value
        for value in (_metric_delta(row, _casel_average) for row in pair_rows)
        if value is not None
    ]
    lines.extend(
        [
            "",
            "### Score Deltas",
            "",
            _delta_summary("score_delta", score_deltas),
            _delta_summary("EX_delta", ex_deltas),
            _delta_summary("CASEL_avg_delta", casel_deltas),
        ]
    )

    cell_pattern_counts = Counter(
        (
            f"{row.get('persona', '')} × {row.get('scenario', '')}",
            f"{row['winner_id']} > {row['loser_id']}",
        )
        for row in pair_rows
    )
    lines.extend(
        [
            "",
            "### Cell Pair Pattern",
            "",
            "| cell | pattern | count |",
            "|---|---:|---:|",
        ]
    )
    for (cell, pattern), count in sorted(
        cell_pattern_counts.items(), key=lambda item: (item[0][0], item[0][1])
    ):
        lines.append(f"| {cell} | {pattern} | {count} |")
    return lines


def extract_preference_pairs(
    accepted_path: str | Path,
    output_dir: str | Path,
    run_id: str,
    api_url: str = "http://127.0.0.1:8000/chat",
    chat_client: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    chat_attempt: int = 1,
) -> PreferenceExtractionResult:
    samples = _load_samples(Path(accepted_path))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    chat_results_path = output / "chat_results.jsonl"
    preference_pairs_path = output / "preference_pairs.jsonl"
    summary_path = output / "summary_pairs.md"
    chat_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    client = chat_client or (lambda payload: _post_chat(api_url, payload))

    for sample in samples:
        session_id = f"{run_id}-{sample['id']}-chat-{chat_attempt:02d}"
        payload = {
            "session_id": session_id,
            "current_message": sample["text"],
        }
        try:
            chat = client(payload)
            request_ok = True
            failure_reason = ""
        except Exception as exc:
            chat = {}
            request_ok = False
            failure_reason = str(exc)
        chat_row = {
            "sample": sample,
            "request": payload,
            "request_ok": request_ok,
            "failure_reason": failure_reason,
            "chat": chat,
        }
        chat_rows.append(chat_row)
        preference_pair = chat.get("preference_pair") if request_ok else None
        if chat.get("status") != "answered" or not preference_pair:
            continue
        pair_rows.append(
            PreferencePairRecord(
                sample_id=sample["id"],
                run_id=run_id,
                session_id=session_id,
                persona=sample.get("persona", ""),
                scenario=sample.get("scenario", chat.get("scenario", "")),
                user_message=sample["text"],
                winner_id=preference_pair["winner_id"],
                loser_id=preference_pair["loser_id"],
                candidates=list(chat.get("candidates", [])),
                scores=list(chat.get("scores", [])),
                chat_response=chat,
            ).to_dict()
        )

    write_jsonl(chat_results_path, chat_rows)
    write_jsonl(preference_pairs_path, pair_rows)
    accepted_count = len(samples)
    pair_rate = len(pair_rows) / accepted_count if accepted_count else 0.0
    summary_path.write_text(
        "\n".join(
            [
                "# Preference Pair Extraction Summary",
                "",
                f"- run_id: `{run_id}`",
                f"- accepted_samples: {accepted_count}",
                f"- chat_requests: {len(chat_rows)}",
                f"- preference_pairs: {len(pair_rows)}",
                f"- pair_rate: {pair_rate:.1%}",
            ]
            + _build_dpo_diversity_summary(pair_rows)
        )
        + "\n",
        encoding="utf-8",
    )
    return PreferenceExtractionResult(
        output_dir=output,
        chat_results_path=chat_results_path,
        preference_pairs_path=preference_pairs_path,
        summary_path=summary_path,
        chat_count=len(chat_rows),
        pair_count=len(pair_rows),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract preference pairs via /chat.")
    parser.add_argument("--accepted-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/chat")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    extract_preference_pairs(
        accepted_path=args.accepted_path,
        output_dir=args.output_dir,
        run_id=args.run_id,
        api_url=args.api_url,
    )


if __name__ == "__main__":
    main()
