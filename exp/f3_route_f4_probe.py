from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from app.schemas.critic import CandidateInput, CriticEvaluateRequest
from app.schemas.generator import GeneratorGenerateRequest
from app.schemas.safety import ConversationMessage
from app.services.critic_service import CriticService
from app.services.f3_support_service import F3SupportService
from app.services.generator_service import GeneratorService, f3_prompt_bundle_hash
from app.services.llm_client import DeepSeekLLMClient
from app.services.scenario_service import ScenarioService


RUNS_DIR = Path("exp/runs/f3_route_f4_probe")
DEFAULT_MODEL = "qwen3.7-plus"

FIXED_SAMPLES: list[dict[str, Any]] = [
    {
        "sample_id": "emo_academic_first_01",
        "target_group": "strong_negative_c1",
        "expected_support_mode": "emotion_first",
        "expected_policy_choice": "c1",
        "dialogue_stage": "first_contact",
        "current_message": "我这次月考考砸了，晚上躺下就一直想排名，心跳很快，感觉自己完了。",
        "history": [],
    },
    {
        "sample_id": "emo_peer_first_01",
        "target_group": "strong_negative_c1",
        "expected_support_mode": "emotion_first",
        "expected_policy_choice": "c1",
        "dialogue_stage": "first_contact",
        "current_message": "今天午休她们聊天突然安静下来，我一走开又笑，我觉得自己像被排除在外，特别丢脸。",
        "history": [],
    },
    {
        "sample_id": "emo_parent_first_01",
        "target_group": "strong_negative_c1",
        "expected_support_mode": "emotion_first",
        "expected_policy_choice": "c1",
        "dialogue_stage": "first_contact",
        "current_message": "我妈又拿我和表姐比，说我什么都不如她，我当时一句话都说不出来，真的很委屈。",
        "history": [],
    },
    {
        "sample_id": "help_academic_first_01",
        "target_group": "solution_seeking_c2",
        "expected_support_mode": "solution_seeking",
        "expected_policy_choice": "c2",
        "dialogue_stage": "first_contact",
        "current_message": "我一到考试前就睡不着，越怕考不好越睡不着，我到底应该怎么办？",
        "history": [],
    },
    {
        "sample_id": "help_peer_first_01",
        "target_group": "solution_seeking_c2",
        "expected_support_mode": "solution_seeking",
        "expected_policy_choice": "c2",
        "dialogue_stage": "first_contact",
        "current_message": "我朋友最近总是不回我消息，我很想问清楚但又怕尴尬，我该怎么做？",
        "history": [],
    },
    {
        "sample_id": "help_parent_first_01",
        "target_group": "solution_seeking_c2",
        "expected_support_mode": "solution_seeking",
        "expected_policy_choice": "c2",
        "dialogue_stage": "first_contact",
        "current_message": "我爸总是检查我手机，我说了他也不听，我应该怎么跟他说才不会又吵起来？",
        "history": [],
    },
    {
        "sample_id": "follow_academic_01",
        "target_group": "follow_up_cbt_support",
        "expected_support_mode": "solution_seeking",
        "expected_policy_choice": "c2",
        "dialogue_stage": "follow_up",
        "current_message": "那我今晚又开始担心明天考试睡不着的时候，可以先做什么？",
        "history": [
            {"role": "student", "text": "我最近考试压力很大，晚上总是睡不着。"},
            {"role": "assistant", "text": "你躺下以后脑子还在转考试这件事，那种停不下来的紧绷确实很累。"},
        ],
    },
    {
        "sample_id": "follow_peer_01",
        "target_group": "follow_up_cbt_support",
        "expected_support_mode": "solution_seeking",
        "expected_policy_choice": "c2",
        "dialogue_stage": "follow_up",
        "current_message": "我还是很想知道是不是我哪里不好，所以她们才不叫我，我要怎么想会好一点？",
        "history": [
            {"role": "student", "text": "她们周末出去玩没有叫我，我翻了好几遍群消息。"},
            {"role": "assistant", "text": "你反复翻群消息，是想确认自己是不是被落下了，这种感觉会很堵。"},
        ],
    },
    {
        "sample_id": "balanced_parent_first_01",
        "target_group": "balanced_no_rhetorical_first",
        "expected_support_mode": "balanced",
        "expected_policy_choice": "",
        "dialogue_stage": "first_contact",
        "current_message": "妈妈说是为我好，可她总替我决定补课和周末安排，我知道她辛苦，但我也觉得喘不过气。",
        "history": [],
    },
]


RISKY_AUDIT_TAGS = {
    "forced_positive_reframe",
    "unsupported_third_party_motive",
    "third_party_excuse",
    "unsupported_fact_completion",
    "hard_boundary_fabrication",
    "relationship_decision_risk",
    "adult_coaching_question",
}

PUSHY_QUESTION_PATTERNS = (
    "你觉得呢",
    "你怎么想",
    "难道",
    "你不觉得",
    "有没有想过",
    "为什么不",
    "是不是应该",
    "该不该",
    "要不要",
)


def compact(text: str, limit: int = 360) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def to_messages(raw_history: list[dict[str, str]]) -> list[ConversationMessage]:
    return [ConversationMessage(role=item["role"], text=item["text"]) for item in raw_history]


def model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def extract_audit_tags(rationale: str) -> list[str]:
    match = re.search(r"audit_tags=([A-Za-z0-9_,\-]+)", rationale or "")
    if not match:
        return []
    return [item for item in match.group(1).split(",") if item]


def question_stats(text: str) -> dict[str, Any]:
    value = str(text or "")
    question_count = value.count("？") + value.count("?")
    pushy_patterns = [pattern for pattern in PUSHY_QUESTION_PATTERNS if pattern in value]
    return {
        "question_count": question_count,
        "has_question": question_count > 0,
        "pushy_patterns": pushy_patterns,
        "has_pushy_or_rhetorical_question": bool(pushy_patterns),
    }


def candidate_quality(score, *, min_weighted_total: float) -> dict[str, Any]:
    tags = extract_audit_tags(score.rationale)
    risky_tags = [tag for tag in tags if tag in RISKY_AUDIT_TAGS]
    pass_quality = (
        not score.boundary_flag
        and score.weighted_total >= min_weighted_total
        and not risky_tags
    )
    return {
        "pass_quality": pass_quality,
        "audit_tags": tags,
        "risky_audit_tags": risky_tags,
    }


def choose_after_quality(
    *,
    support_mode: str,
    critic_best_id: str | None,
    quality_by_id: dict[str, dict[str, Any]],
) -> str | None:
    passing = [
        candidate_id
        for candidate_id, quality in quality_by_id.items()
        if quality.get("pass_quality")
    ]
    if not passing:
        return None
    if len(passing) == 1:
        return passing[0]
    if support_mode == "emotion_first" and "c1" in passing:
        return "c1"
    if support_mode == "solution_seeking" and "c2" in passing:
        return "c2"
    if critic_best_id in passing:
        return critic_best_id
    return passing[0]


def scenario_fallback_casel(scenario: str) -> list[str]:
    mapping = {
        "学业压力": ["自我觉察引导", "自我管理引导", "负责任决策引导"],
        "同伴关系": ["自我觉察引导", "社会觉察培养", "关系技能培养"],
        "亲子摩擦": ["自我觉察引导", "自我管理引导", "社会觉察培养", "关系技能培养"],
        "其他": ["自我觉察引导"],
    }
    return mapping.get(scenario, mapping["其他"])


async def run_sample(
    sample: dict[str, Any],
    *,
    scenario_service: ScenarioService,
    generator_service: GeneratorService,
    critic_service: CriticService,
    support_service: F3SupportService,
    args: argparse.Namespace,
) -> dict[str, Any]:
    started = time.perf_counter()
    history = to_messages(sample["history"])
    base = {
        "sample_id": sample["sample_id"],
        "target_group": sample["target_group"],
        "expected_support_mode": sample["expected_support_mode"],
        "expected_policy_choice": sample["expected_policy_choice"],
        "expected_dialogue_stage": sample["dialogue_stage"],
        "current_message": sample["current_message"],
        "history": sample["history"],
    }
    try:
        scenario = await scenario_service.analyze(
            request=scenario_service_request(
                sample["sample_id"], sample["current_message"], history
            )
        )
        if scenario.secondary_safety.action.block_generation:
            return {
                **base,
                "status": "blocked_by_f2",
                "scenario": model_dump(scenario),
                "support_context": {},
                "candidates": [],
                "critic": {},
                "checks": {},
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "error": "",
            }

        dialogue_stage = "first_contact" if not history else "follow_up"
        generated = await generator_service.generate(
            GeneratorGenerateRequest(
                session_id=sample["sample_id"],
                user_message=sample["current_message"],
                history=history,
                scenario=scenario.scenario,
                support_mode=scenario.support_mode,
                emotion_intensity=scenario.emotion_intensity,
                help_seeking=scenario.help_seeking,
                dialogue_stage=dialogue_stage,
                rag_examples=[],
            )
        )
        support_context = support_service.build_context(
            scenario=scenario.scenario,
            user_message=sample["current_message"],
            external_examples=[],
        )
        critic = await critic_service.evaluate(
            CriticEvaluateRequest(
                session_id=sample["sample_id"],
                user_message=sample["current_message"],
                history=history,
                activated_casel=scenario.activated_casel
                or scenario_fallback_casel(scenario.scenario),
                candidates=[
                    CandidateInput(
                        candidate_id=candidate.candidate_id,
                        orientation=candidate.orientation,
                        text=candidate.text,
                    )
                    for candidate in generated.candidates
                ],
            )
        )

        candidates = [model_dump(candidate) for candidate in generated.candidates]
        scores = [model_dump(score) for score in critic.scores]
        score_by_id = {score.candidate_id: score for score in critic.scores}
        quality_by_id = {
            candidate_id: candidate_quality(score, min_weighted_total=args.min_weighted_total)
            for candidate_id, score in score_by_id.items()
        }
        selected_after_filter = choose_after_quality(
            support_mode=scenario.support_mode,
            critic_best_id=critic.best_candidate_id,
            quality_by_id=quality_by_id,
        )
        questions_by_id = {
            candidate["candidate_id"]: question_stats(candidate["text"])
            for candidate in candidates
        }
        first_turn = dialogue_stage == "first_contact"
        checks = {
            "f2_support_mode_matches_expected": scenario.support_mode
            == sample["expected_support_mode"],
            "dialogue_stage_matches_expected": dialogue_stage
            == sample["dialogue_stage"],
            "recommended_candidate_after_f4": selected_after_filter,
            "expected_policy_choice_met": (
                True
                if not sample["expected_policy_choice"]
                else selected_after_filter == sample["expected_policy_choice"]
            ),
            "first_turn_no_question": (
                True
                if not first_turn
                else not any(item["has_question"] for item in questions_by_id.values())
            ),
            "first_turn_no_pushy_or_rhetorical_question": (
                True
                if not first_turn
                else not any(
                    item["has_pushy_or_rhetorical_question"]
                    for item in questions_by_id.values()
                )
            ),
            "c1_er_gt_c2_er": (
                score_by_id["c1"].epitome.ER > score_by_id["c2"].epitome.ER
                if "c1" in score_by_id and "c2" in score_by_id
                else False
            ),
            "c2_ip_gt_c1_ip": (
                score_by_id["c2"].epitome.IP > score_by_id["c1"].epitome.IP
                if "c1" in score_by_id and "c2" in score_by_id
                else False
            ),
            "all_candidates_pass_f4_quality": all(
                item["pass_quality"] for item in quality_by_id.values()
            ),
            "at_least_one_candidate_passes_f4_quality": any(
                item["pass_quality"] for item in quality_by_id.values()
            ),
        }
        return {
            **base,
            "status": "ok",
            "scenario": model_dump(scenario),
            "support_context": {
                "strategy_prior": support_context.strategy_prior,
                "support_cards": support_context.support_cards,
            },
            "candidates": candidates,
            "critic": {
                "best_candidate_id": critic.best_candidate_id,
                "scores": scores,
                "preference_pair": (
                    model_dump(critic.preference_pair)
                    if critic.preference_pair is not None
                    else None
                ),
                "fallback_message": critic.fallback_message,
            },
            "quality_by_id": quality_by_id,
            "questions_by_id": questions_by_id,
            "checks": checks,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": "",
        }
    except Exception as exc:
        return {
            **base,
            "status": "failed",
            "scenario": {},
            "support_context": {},
            "candidates": [],
            "critic": {},
            "checks": {},
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }


def scenario_service_request(session_id: str, current_message: str, history: list[ConversationMessage]):
    from app.schemas.scenario import ScenarioAnalyzeRequest

    return ScenarioAnalyzeRequest(
        session_id=session_id,
        current_message=current_message,
        history=history,
    )


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row["status"] == "ok"]
    failed_rows = [row for row in rows if row["status"] == "failed"]
    blocked_rows = [row for row in rows if row["status"] == "blocked_by_f2"]

    def rate(key: str, subset: list[dict[str, Any]] | None = None) -> float:
        target = ok_rows if subset is None else subset
        if not target:
            return 0.0
        return round(sum(1 for row in target if row["checks"].get(key)) / len(target), 4)

    by_group: dict[str, dict[str, Any]] = {}
    for group in sorted({row["target_group"] for row in ok_rows}):
        group_rows = [row for row in ok_rows if row["target_group"] == group]
        by_group[group] = {
            "n": len(group_rows),
            "f2_support_mode_match_rate": rate("f2_support_mode_matches_expected", group_rows),
            "expected_policy_choice_met_rate": rate("expected_policy_choice_met", group_rows),
            "first_turn_no_pushy_or_rhetorical_question_rate": rate(
                "first_turn_no_pushy_or_rhetorical_question", group_rows
            ),
            "at_least_one_candidate_passes_f4_quality_rate": rate(
                "at_least_one_candidate_passes_f4_quality", group_rows
            ),
        }

    selected_distribution = Counter(
        row["checks"].get("recommended_candidate_after_f4") or "none"
        for row in ok_rows
    )
    f2_mode_distribution = Counter(
        row["scenario"].get("support_mode", "unknown") for row in ok_rows
    )
    critic_best_distribution = Counter(
        row["critic"].get("best_candidate_id") or "none" for row in ok_rows
    )
    return {
        "total": len(rows),
        "ok": len(ok_rows),
        "failed": len(failed_rows),
        "blocked_by_f2": len(blocked_rows),
        "f2_support_mode_match_rate": rate("f2_support_mode_matches_expected"),
        "expected_policy_choice_met_rate": rate("expected_policy_choice_met"),
        "first_turn_no_question_rate": rate("first_turn_no_question"),
        "first_turn_no_pushy_or_rhetorical_question_rate": rate(
            "first_turn_no_pushy_or_rhetorical_question"
        ),
        "c1_er_gt_c2_er_rate": rate("c1_er_gt_c2_er"),
        "c2_ip_gt_c1_ip_rate": rate("c2_ip_gt_c1_ip"),
        "all_candidates_pass_f4_quality_rate": rate("all_candidates_pass_f4_quality"),
        "at_least_one_candidate_passes_f4_quality_rate": rate(
            "at_least_one_candidate_passes_f4_quality"
        ),
        "avg_duration_ms": round(mean(row["duration_ms"] for row in ok_rows), 1)
        if ok_rows
        else 0.0,
        "selected_after_filter_distribution": dict(selected_distribution),
        "critic_best_distribution": dict(critic_best_distribution),
        "f2_support_mode_distribution": dict(f2_mode_distribution),
        "by_group": by_group,
        "errors": Counter(row["error"][:180] for row in failed_rows).most_common(5),
    }


def write_human_template(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    path = run_dir / "human_review_template.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        fieldnames = [
            "sample_id",
            "target_group",
            "f2_support_mode",
            "critic_best",
            "selected_after_filter",
            "human_preference",
            "notes",
            "current_message",
            "c1_text",
            "c2_text",
            "c1_score",
            "c2_score",
            "c1_questions",
            "c2_questions",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            c_by_id = {item.get("candidate_id"): item for item in row.get("candidates", [])}
            s_by_id = {
                item.get("candidate_id"): item
                for item in row.get("critic", {}).get("scores", [])
            }
            q_by_id = row.get("questions_by_id", {})
            writer.writerow(
                {
                    "sample_id": row.get("sample_id"),
                    "target_group": row.get("target_group"),
                    "f2_support_mode": row.get("scenario", {}).get("support_mode", ""),
                    "critic_best": row.get("critic", {}).get("best_candidate_id", ""),
                    "selected_after_filter": row.get("checks", {}).get(
                        "recommended_candidate_after_f4", ""
                    ),
                    "human_preference": "",
                    "notes": "",
                    "current_message": row.get("current_message"),
                    "c1_text": c_by_id.get("c1", {}).get("text", ""),
                    "c2_text": c_by_id.get("c2", {}).get("text", ""),
                    "c1_score": json.dumps(s_by_id.get("c1", {}), ensure_ascii=False),
                    "c2_score": json.dumps(s_by_id.get("c2", {}), ensure_ascii=False),
                    "c1_questions": json.dumps(q_by_id.get("c1", {}), ensure_ascii=False),
                    "c2_questions": json.dumps(q_by_id.get("c2", {}), ensure_ascii=False),
                }
            )


def write_report(run_dir: Path, metadata: dict[str, Any], summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# F3 Route + F4 Quality Probe",
        "",
        f"- run_id: `{metadata['run_id']}`",
        f"- model: `{metadata['model']}`",
        f"- sample_count: `{metadata['sample_count']}`",
        f"- critic_sample_count: `{metadata['critic_sample_count']}`",
        f"- prompt_hash: `{metadata['prompt_hash']}`",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "|---|---:|",
    ]
    for key, value in summary.items():
        if isinstance(value, (dict, list)):
            continue
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Distributions",
            "",
            "```json",
            json.dumps(
                {
                    "selected_after_filter_distribution": summary[
                        "selected_after_filter_distribution"
                    ],
                    "critic_best_distribution": summary["critic_best_distribution"],
                    "f2_support_mode_distribution": summary[
                        "f2_support_mode_distribution"
                    ],
                    "by_group": summary["by_group"],
                    "errors": summary["errors"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "## Cases",
            "",
        ]
    )
    for row in rows:
        lines.extend(
            [
                f"### {row['sample_id']} / {row['target_group']} / {row['status']}",
                "",
                f"Input: {row['current_message']}",
                "",
            ]
        )
        if row["status"] != "ok":
            lines.extend([f"Error: {row.get('error')}", ""])
            continue
        scenario = row["scenario"]
        checks = row["checks"]
        scores = {
            score["candidate_id"]: score
            for score in row.get("critic", {}).get("scores", [])
        }
        candidates = {item["candidate_id"]: item for item in row["candidates"]}
        lines.extend(
            [
                f"- F2 scenario/support: `{scenario.get('scenario')}` / `{scenario.get('support_mode')}` / intensity `{scenario.get('emotion_intensity')}` / help `{scenario.get('help_seeking')}`",
                f"- critic_best: `{row['critic'].get('best_candidate_id')}`",
                f"- selected_after_filter: `{checks.get('recommended_candidate_after_f4')}`",
                f"- expected_policy_choice_met: `{checks.get('expected_policy_choice_met')}`",
                f"- first_turn_no_pushy_or_rhetorical_question: `{checks.get('first_turn_no_pushy_or_rhetorical_question')}`",
                f"- c1 score: `{scores.get('c1', {})}`",
                f"- c2 score: `{scores.get('c2', {})}`",
                "",
                f"c1: {compact(candidates.get('c1', {}).get('text', ''), 420)}",
                "",
                f"c2: {compact(candidates.get('c2', {}).get('text', ''), 420)}",
                "",
            ]
        )
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def main_async(args: argparse.Namespace) -> None:
    load_dotenv()
    api_key = args.api_key or os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is required")

    run_id = args.run_id or datetime.now().strftime("route-f4-qwen37-plus-%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        LLM_PROVIDER="deepseek",
        DEEPSEEK_API_KEY=api_key,
        DEEPSEEK_BASE_URL=args.base_url,
        DEEPSEEK_MODEL=args.model,
        CRITIC_DEEPSEEK_MODEL=args.model,
        LLM_TIMEOUT=args.timeout,
        LLM_MAX_TOKENS=args.generator_max_tokens,
        CRITIC_LLM_MAX_TOKENS=args.critic_max_tokens,
        GENERATOR_LLM_TEMPERATURE=args.generator_temperature,
        SCENARIO_LLM_TEMPERATURE=0.0,
        CRITIC_LLM_TEMPERATURE=0.0,
        CRITIC_SAMPLE_COUNT=args.critic_sample_count,
        F3_SUPPORT_TOP_K=args.support_top_k,
        F3_SUPPORT_MIN_SCORE=args.support_min_score,
    )
    llm_client = DeepSeekLLMClient(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        thinking_type=None,
    )
    scenario_service = ScenarioService(llm_client, settings)
    support_service = F3SupportService(settings)
    generator_service = GeneratorService(llm_client, settings, support_service)
    critic_service = CriticService(llm_client, None, settings)

    samples = FIXED_SAMPLES[: args.limit] if args.limit else FIXED_SAMPLES
    metadata = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "base_url": args.base_url,
        "sample_count": len(samples),
        "critic_sample_count": args.critic_sample_count,
        "prompt_hash": f3_prompt_bundle_hash(),
        "generator_temperature": args.generator_temperature,
        "min_weighted_total": args.min_weighted_total,
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "fixed_samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Run directory: {run_dir}")
    print(f"Model: {args.model}; samples={len(samples)}")
    results: list[dict[str, Any]] = []
    results_path = run_dir / "results.jsonl"
    started = time.perf_counter()
    for index, sample in enumerate(samples, start=1):
        row = await run_sample(
            sample,
            scenario_service=scenario_service,
            generator_service=generator_service,
            critic_service=critic_service,
            support_service=support_service,
            args=args,
        )
        append_jsonl(results_path, row)
        results.append(row)
        print(
            f"[{index}/{len(samples)}] {row['sample_id']} status={row['status']} "
            f"selected={row.get('checks', {}).get('recommended_candidate_after_f4')} "
            f"elapsed={time.perf_counter() - started:.1f}s"
        )

    summary = summarize(results)
    (run_dir / "summary.json").write_text(
        json.dumps({"metadata": metadata, "summary": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_human_template(run_dir, results)
    write_report(run_dir, metadata, summary, results)
    print(json.dumps({"metadata": metadata, "summary": summary}, ensure_ascii=False, indent=2))
    print(f"Report: {run_dir / 'report.md'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fixed-input probe for F2 route, F3 c1/c2 generation, and F4 quality filtering."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--generator-temperature", type=float, default=0.8)
    parser.add_argument("--generator-max-tokens", type=int, default=420)
    parser.add_argument("--critic-max-tokens", type=int, default=1600)
    parser.add_argument("--critic-sample-count", type=int, default=1)
    parser.add_argument("--support-top-k", type=int, default=2)
    parser.add_argument("--support-min-score", type=float, default=0.10)
    parser.add_argument("--min-weighted-total", type=float, default=3.0)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main_async(parse_args()))
