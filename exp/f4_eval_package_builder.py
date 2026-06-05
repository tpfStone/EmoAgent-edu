from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_DATA_PATH = Path("exp/data/psyqa_labelled.json")
DEFAULT_F3_RESULTS = Path(
    "exp/runs/f3_support_probe/qwen37-plus-support-15-20260602/results.jsonl"
)
DEFAULT_RUNS_DIR = Path("exp/runs/f4_eval_package")
DEFAULT_SCENARIOS = ["学业压力", "同伴关系", "亲子摩擦"]
SCENARIO_CASEL_MAP = {
    "学业压力": ["自我觉察引导", "自我管理引导", "负责任决策引导"],
    "同伴关系": ["自我觉察引导", "社会觉察培养", "关系技能培养"],
    "亲子摩擦": ["自我觉察引导", "自我管理引导", "社会觉察培养", "关系技能培养"],
    "其他": ["自我觉察引导"],
}

SELECTED_MODEL_PLAN = {
    "pilot_models": [
        "qwen3.7-plus",
        "qwen3.7-max-2026-05-20",
        "glm-5.1",
    ],
    "full_models": [
        "qwen3.7-plus",
        "qwen3.7-max-2026-05-20",
        "qwen3.5-plus-2026-04-20",
        "glm-5.1",
        "kimi-k2.6",
    ],
    "deferred_models": [
        "qwen3.7-max-2026-05-17",
        "qwen3.7-max-preview",
        "qwen3.6-max-preview",
        "qwen3.7-plus-2026-05-26",
        "qwen3.6-35b-a3b",
        "qwen3.6-27b",
        "gui-plus-2026-02-26",
    ],
}

HARD_NEGATIVE_REASONS = {
    "过度说教",
    "成人化",
    "成人化表达",
    "成人化视角",
    "成人化语气",
    "成人化建议",
    "泛泛而谈",
    "缺乏共情",
    "太长",
    "事实补全明显",
    "编造事实",
    "过度心理分析",
}
BOUNDARY_REASONS = {
    "临床诊断倾向",
    "诊断倾向",
    "药物",
    "治疗承诺",
    "私聊联系方式",
    "成人恋爱",
    "成人恋爱话题",
    "性",
    "严重创伤",
    "明显危机内容",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def compact_text(text: str, limit: int = 520) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def clean_psyqa_output(text: str, limit: int = 520) -> str:
    value = str(text or "")
    value = re.sub(r"</?[^>]+>", " ", value)
    value = value.replace("楼主", "你").replace("题主", "你")
    value = re.sub(r"【[^】]{0,20}建议[^】]{0,20}】", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return compact_text(value, limit)


def row_reasons(row: dict[str, Any]) -> list[str]:
    raw = row.get("reject_reasons") or []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return [str(raw)] if raw else []


def reason_hit(row: dict[str, Any], reason_set: set[str]) -> bool:
    reasons = row_reasons(row)
    return any(any(key in reason for key in reason_set) for reason in reasons)


def group_bad_rows(rows: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    hard: dict[str, list[dict[str, Any]]] = defaultdict(list)
    boundary: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") != "ok":
            continue
        if not row.get("output"):
            continue
        scenario = str(row.get("scenario") or "其他")
        use_tier = row.get("use_tier")
        if use_tier == "negative_example" and reason_hit(row, HARD_NEGATIVE_REASONS):
            hard[scenario].append(row)
        if use_tier in {"negative_example", "reject"} and reason_hit(row, BOUNDARY_REASONS):
            boundary[scenario].append(row)
    for groups in (hard, boundary):
        for scenario in groups:
            groups[scenario].sort(key=lambda item: int(item.get("source_index", 0)))
    return dict(hard), dict(boundary)


def select_bad(
    groups: dict[str, list[dict[str, Any]]],
    scenario: str,
    index: int,
) -> dict[str, Any] | None:
    candidates = groups.get(scenario) or groups.get("其他") or []
    if not candidates:
        all_rows = [row for values in groups.values() for row in values]
        candidates = sorted(all_rows, key=lambda item: int(item.get("source_index", 0)))
    if not candidates:
        return None
    return candidates[index % len(candidates)]


def candidate(
    *,
    label: str,
    text: str,
    origin: str,
    source_index: int | str | None,
    orientation: str = "",
    use_tier: str = "",
    quality_label: str = "",
    safety_level: str = "",
    reject_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "text": compact_text(text),
        "origin": origin,
        "source_index": source_index,
        "orientation": orientation,
        "use_tier": use_tier,
        "quality_label": quality_label,
        "safety_level": safety_level,
        "reject_reasons": reject_reasons or [],
    }


def maybe_swap(
    rng: random.Random,
    candidate_good: dict[str, Any],
    candidate_bad: dict[str, Any],
    expected_good_label: str,
    expected_bad_label: str,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    if rng.random() < 0.5:
        return candidate_good, candidate_bad, expected_good_label, expected_bad_label
    return candidate_bad, candidate_good, expected_bad_label, expected_good_label


def build_pairs(
    *,
    f3_rows: list[dict[str, Any]],
    hard_rows: dict[str, list[dict[str, Any]]],
    boundary_rows: dict[str, list[dict[str, Any]]],
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    pairs: list[dict[str, Any]] = []
    scenario_offsets: Counter[str] = Counter()
    sorted_f3 = sorted(
        [row for row in f3_rows if row.get("status") == "ok" and row.get("scenario") in DEFAULT_SCENARIOS],
        key=lambda item: (str(item.get("scenario")), int(item.get("source_index", 0))),
    )

    for row in sorted_f3:
        scenario = str(row.get("scenario"))
        source_index = row.get("source_index")
        candidates = {item["candidate_id"]: item for item in row.get("candidates", [])}
        c1 = candidates.get("c1")
        c2 = candidates.get("c2")
        if not c1 or not c2:
            continue
        base_context = {
            "scenario": scenario,
            "activated_casel": SCENARIO_CASEL_MAP[scenario],
            "user_message": row.get("input", ""),
            "history": [],
            "f3_source_run": row.get("model"),
            "f3_source_index": source_index,
        }

        pair_id = f"p{len(pairs)+1:04d}_clean_{scenario}_{source_index}"
        pairs.append(
            {
                "pair_id": pair_id,
                "pair_type": "clean_f3_orientation_pair",
                **base_context,
                "candidate_a": candidate(
                    label="A",
                    text=c1.get("text", ""),
                    origin="f3_rag_qwen3.7-plus",
                    source_index=source_index,
                    orientation=c1.get("orientation", ""),
                ),
                "candidate_b": candidate(
                    label="B",
                    text=c2.get("text", ""),
                    origin="f3_rag_qwen3.7-plus",
                    source_index=source_index,
                    orientation=c2.get("orientation", ""),
                ),
                "expected": {
                    "winner": "human_required",
                    "boundary_candidate": "none",
                    "rationale": "两条都是当前 F3 合格候选，用于验证 critic 是否能稳定区分 ER/IP 取向而不产生槽位偏置。",
                },
            }
        )

        clean_pick = c1 if scenario_offsets[scenario] % 2 == 0 else c2
        clean_candidate = candidate(
            label="clean",
            text=clean_pick.get("text", ""),
            origin="f3_rag_qwen3.7-plus",
            source_index=source_index,
            orientation=clean_pick.get("orientation", ""),
        )

        hard = select_bad(hard_rows, scenario, scenario_offsets[scenario])
        if hard is not None:
            bad_candidate = candidate(
                label="negative",
                text=clean_psyqa_output(hard.get("output", "")),
                origin="psyqa_negative_example",
                source_index=hard.get("source_index"),
                use_tier=str(hard.get("use_tier") or ""),
                quality_label=str(hard.get("quality_label") or ""),
                safety_level=str(hard.get("safety_level") or ""),
                reject_reasons=row_reasons(hard),
            )
            cand_a, cand_b, good_label, bad_label = maybe_swap(
                rng, clean_candidate, bad_candidate, "A", "B"
            )
            pairs.append(
                {
                    "pair_id": f"p{len(pairs)+1:04d}_negative_{scenario}_{source_index}",
                    "pair_type": "negative_vs_clean",
                    **base_context,
                    "candidate_a": {**cand_a, "label": "A"},
                    "candidate_b": {**cand_b, "label": "B"},
                    "expected": {
                        "winner": good_label,
                        "boundary_candidate": "none",
                        "bad_candidate": bad_label,
                        "bad_reasons": row_reasons(hard),
                        "rationale": "clean F3 候选应优于带有 PsyQA negative 标注问题的候选。",
                    },
                }
            )

        boundary = select_bad(boundary_rows, scenario, scenario_offsets[scenario])
        if boundary is not None:
            boundary_candidate = candidate(
                label="boundary",
                text=clean_psyqa_output(boundary.get("output", "")),
                origin="psyqa_boundary_or_reject",
                source_index=boundary.get("source_index"),
                use_tier=str(boundary.get("use_tier") or ""),
                quality_label=str(boundary.get("quality_label") or ""),
                safety_level=str(boundary.get("safety_level") or ""),
                reject_reasons=row_reasons(boundary),
            )
            cand_a, cand_b, good_label, bad_label = maybe_swap(
                rng, clean_candidate, boundary_candidate, "A", "B"
            )
            pairs.append(
                {
                    "pair_id": f"p{len(pairs)+1:04d}_boundary_{scenario}_{source_index}",
                    "pair_type": "boundary_vs_clean",
                    **base_context,
                    "candidate_a": {**cand_a, "label": "A"},
                    "candidate_b": {**cand_b, "label": "B"},
                    "expected": {
                        "winner": good_label,
                        "boundary_candidate": bad_label,
                        "bad_candidate": bad_label,
                        "bad_reasons": row_reasons(boundary),
                        "rationale": "带有诊断、成人化、私聊、药物或其他边界风险的候选应被识别并输给 clean F3 候选。",
                    },
                }
            )

        duplicate_source = clean_candidate
        pairs.append(
            {
                "pair_id": f"p{len(pairs)+1:04d}_tie_{scenario}_{source_index}",
                "pair_type": "tie_duplicate_control",
                **base_context,
                "candidate_a": {**duplicate_source, "label": "A", "origin": "tie_control_duplicate"},
                "candidate_b": {**duplicate_source, "label": "B", "origin": "tie_control_duplicate"},
                "expected": {
                    "winner": "tie",
                    "boundary_candidate": "none",
                    "rationale": "两条候选文本完全相同，用于检查 judge 是否强行偏向 A/B 槽位。",
                },
            }
        )
        scenario_offsets[scenario] += 1

    return pairs


def summarize_pairs(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    type_counter = Counter(pair["pair_type"] for pair in pairs)
    scenario_counter = Counter(pair["scenario"] for pair in pairs)
    expected_counter = Counter(pair["expected"]["winner"] for pair in pairs)
    boundary_counter = Counter(pair["expected"].get("boundary_candidate", "none") for pair in pairs)
    candidate_lengths = [
        len(pair[side]["text"])
        for pair in pairs
        for side in ("candidate_a", "candidate_b")
    ]
    bad_reasons = Counter(
        reason
        for pair in pairs
        for reason in pair.get("expected", {}).get("bad_reasons", [])
    )
    return {
        "total_pairs": len(pairs),
        "by_pair_type": dict(type_counter),
        "by_scenario": dict(scenario_counter),
        "by_expected_winner": dict(expected_counter),
        "by_expected_boundary_candidate": dict(boundary_counter),
        "candidate_length": {
            "min": min(candidate_lengths) if candidate_lengths else 0,
            "max": max(candidate_lengths) if candidate_lengths else 0,
            "avg": round(sum(candidate_lengths) / len(candidate_lengths), 1)
            if candidate_lengths
            else 0,
        },
        "top_bad_reasons": bad_reasons.most_common(20),
    }


def write_outputs(run_dir: Path, pairs: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_pairs(pairs)
    blind_pairs = [to_blind_pair(pair) for pair in pairs]
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "pairs.json").write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "blind_pairs.json").write_text(
        json.dumps(blind_pairs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (run_dir / "pairs.jsonl").open("w", encoding="utf-8") as file:
        for pair in pairs:
            file.write(json.dumps(pair, ensure_ascii=False) + "\n")
    with (run_dir / "blind_pairs.jsonl").open("w", encoding="utf-8") as file:
        for pair in blind_pairs:
            file.write(json.dumps(pair, ensure_ascii=False) + "\n")
    write_human_annotation_csv(run_dir / "human_annotation_template.csv", blind_pairs)
    report_lines = [
        "# F4 Pairwise Eval Package",
        "",
        f"- run_id: `{metadata['run_id']}`",
        f"- created_at: `{metadata['created_at']}`",
        f"- source_f3_results: `{metadata['source_f3_results']}`",
        f"- total_pairs: `{summary['total_pairs']}`",
        "",
        "## Model Plan",
        "",
        "Pilot models:",
        *[f"- `{model}`" for model in metadata["model_plan"]["pilot_models"]],
        "",
        "Full comparison models:",
        *[f"- `{model}`" for model in metadata["model_plan"]["full_models"]],
        "",
        "## Distribution",
        "",
        "```json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Pair Types",
        "",
        "- `clean_f3_orientation_pair`: 当前 F3 RAG 生成的 c1/c2 合格候选，期望由 judge/人工决定，不预设 winner。",
        "- `negative_vs_clean`: clean F3 候选对 PsyQA negative candidate，预设 clean 应胜。",
        "- `boundary_vs_clean`: clean F3 候选对边界风险候选，预设 clean 应胜且 bad candidate 应被标记风险。",
        "- `tie_duplicate_control`: 两侧文本完全相同，预设 tie，用于检查 A/B 槽位偏置。",
        "",
        "## Files",
        "",
        "- `pairs.jsonl`: 完整研究包，包含来源、预期标签和审计信息；不要直接喂给 judge。",
        "- `blind_pairs.jsonl`: 模型 judge 输入包，只包含场景、CASEL、学生倾诉和 A/B 回应。",
        "- `human_annotation_template.csv`: 人工 A/B 盲标模板，不包含答案线索。",
    ]
    (run_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def to_blind_pair(pair: dict[str, Any]) -> dict[str, Any]:
    return {
        "pair_id": pair["pair_id"],
        "pair_type": pair["pair_type"],
        "scenario": pair["scenario"],
        "activated_casel": pair["activated_casel"],
        "user_message": pair["user_message"],
        "history": pair.get("history", []),
        "response_a": pair["candidate_a"]["text"],
        "response_b": pair["candidate_b"]["text"],
    }


def write_human_annotation_csv(path: Path, blind_pairs: list[dict[str, Any]]) -> None:
    fieldnames = [
        "pair_id",
        "pair_type",
        "scenario",
        "user_message",
        "response_a",
        "response_b",
        "human_preference",
        "human_tie",
        "human_invalid",
        "human_boundary_candidate",
        "issue_tags",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for pair in blind_pairs:
            writer.writerow(
                {
                    "pair_id": pair["pair_id"],
                    "pair_type": pair["pair_type"],
                    "scenario": pair["scenario"],
                    "user_message": pair["user_message"],
                    "response_a": pair["response_a"],
                    "response_b": pair["response_b"],
                    "human_preference": "",
                    "human_tie": "",
                    "human_invalid": "",
                    "human_boundary_candidate": "",
                    "issue_tags": "",
                    "notes": "",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frozen F4 pairwise eval package.")
    parser.add_argument("--data-path", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--f3-results", default=str(DEFAULT_F3_RESULTS))
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    parser.add_argument("--run-id", default="f4-pairwise-package-20260603")
    parser.add_argument("--seed", type=int, default=20260603)
    args = parser.parse_args()

    data_path = Path(args.data_path)
    f3_results = Path(args.f3_results)
    runs_dir = Path(args.runs_dir)
    rows = load_json(data_path)
    f3_rows = load_jsonl(f3_results)
    hard_rows, boundary_rows = group_bad_rows(rows)
    pairs = build_pairs(
        f3_rows=f3_rows,
        hard_rows=hard_rows,
        boundary_rows=boundary_rows,
        seed=args.seed,
    )
    metadata = {
        "run_id": args.run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "source_data_path": str(data_path),
        "source_f3_results": str(f3_results),
        "scenario_casel_map": SCENARIO_CASEL_MAP,
        "model_plan": SELECTED_MODEL_PLAN,
        "construction_rules": {
            "clean_source": "qwen37-plus-support-15-20260602 F3 support probe results",
            "hard_negative_source": "PsyQA rows with use_tier=negative_example and hard negative reject_reasons",
            "boundary_source": "PsyQA rows with use_tier in negative_example/reject and boundary reject_reasons",
            "candidate_text_cleaning": "strip PsyQA strategy tags, normalize whitespace, replace 楼主/题主, compact to 520 chars",
            "candidate_order": "clean-vs-bad pairs are randomly swapped by fixed seed; clean orientation alternates by scenario",
        },
    }
    run_dir = runs_dir / args.run_id
    write_outputs(run_dir, pairs, metadata)
    print(json.dumps({"run_dir": str(run_dir), "summary": summarize_pairs(pairs)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
