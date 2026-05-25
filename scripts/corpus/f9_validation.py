import argparse
import asyncio
import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.config import Settings
from app.schemas.critic import CandidateInput, CandidateScore, CriticEvaluateRequest
from app.schemas.generator import GeneratorGenerateRequest, GeneratorOrientation
from app.schemas.safety import ConversationMessage
from app.services.critic_service import CriticService
from app.services.generator_service import GENERATOR_FALLBACK_TEXT, GeneratorService
from app.services.llm_client import DeepSeekLLMClient, MockLLMClient


GOLDEN_SAMPLE_NOS = [3, 11, 16, 19, 22, 25, 27, 31, 40, 15]

F9_BLIND_COLUMNS = [
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

SAMPLE_PROHIBITED_PATTERNS = {
    3: ["说明你很在乎", "先停在这儿也没关系", "先停在这也没关系"],
    11: ["唯一的空档"],
    16: ["别人可能", "省力的方法"],
    19: ["没顾上看你"],
    22: ["有主见"],
    25: ["我懂", "换个角度", "说明你"],
    27: ["坐得近", "话题没兴趣"],
    31: ["班主任觉得", "扛得住"],
    40: ["轻轻递给你一个视角", "递给你一个视角"],
}

GLOBAL_QUALITY_PROBES = [
    "说明你",
    "可见你",
    "从这里能看出",
    "这本身说明",
    "这本身就说明",
    "这本身就是",
    "挺难得",
    "很有数",
    "很有主见",
    "判断力",
]

GENERATED_GLOBAL_QUALITY_FLAG_MAX = 2
RERUN_GLOBAL_QUALITY_FLAG_MAX = 4

LOW_SCORE_REVIEW_SAMPLE_NOS = {3, 6, 14, 19, 22, 25, 27, 35, 36}
LOW_SCORE_REVIEW_COLUMNS = [
    "sample_no",
    "candidate_id",
    "orientation",
    "F4_ER",
    "F4_IP",
    "F4_EX",
    "detected_flags",
    "global_quality_flags",
    "rationale",
    "候选文本",
]


@dataclass(frozen=True)
class F9Case:
    sample_no: int
    scenario: str
    orientation: str
    user_message: str
    history: list[ConversationMessage]
    history_json: str
    old_candidate: str
    issue_types: str = ""
    template_flags: str = ""


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: str | Path, fieldnames: list[str], rows: list[dict]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parse_history(raw_history: str) -> tuple[list[ConversationMessage], str]:
    raw_history = (raw_history or "").strip()
    if not raw_history:
        return [], "[]"
    data = json.loads(raw_history)
    history = [ConversationMessage(**item) for item in data]
    return history, json.dumps([item.model_dump() for item in history], ensure_ascii=False)


def load_cases(
    analysis_path: str | Path,
    blind_path: str | Path,
    sample_nos: Iterable[int],
) -> list[F9Case]:
    analysis_by_sample = {
        int(row["sample_no"]): row for row in _read_csv(analysis_path)
    }
    blind_by_sample = {int(row["sample_no"]): row for row in _read_csv(blind_path)}
    cases: list[F9Case] = []
    for sample_no in sample_nos:
        analysis = analysis_by_sample[int(sample_no)]
        blind = blind_by_sample.get(int(sample_no), {})
        history, history_json = _parse_history(blind.get("对话历史", ""))
        cases.append(
            F9Case(
                sample_no=int(sample_no),
                scenario=analysis["scenario"],
                orientation=analysis["orientation"],
                user_message=analysis["用户倾诉"],
                history=history,
                history_json=history_json,
                old_candidate=analysis["候选文本"],
                issue_types=analysis.get("issue_types", ""),
                template_flags=analysis.get("template_flags", ""),
            )
        )
    return cases


def detect_f3_regression_flags(sample_no: int, text: str) -> list[str]:
    return [
        f"contains:{pattern}"
        for pattern in SAMPLE_PROHIBITED_PATTERNS.get(int(sample_no), [])
        if pattern in text
    ]


def detect_f3_global_quality_flags(text: str) -> list[str]:
    return [
        f"global_contains:{pattern}"
        for pattern in GLOBAL_QUALITY_PROBES
        if pattern in text
    ]


def f4_expectation_passed(
    sample_no: int,
    er: int,
    ip: int,
    ex: int,
    boundary: bool,
) -> bool:
    sample_no = int(sample_no)
    if sample_no in {3, 25}:
        return not (er == 2 and ip == 2)
    if sample_no in {11, 27}:
        return boundary or ip <= 1 or er <= 1
    if sample_no in {19, 31}:
        return ip <= 1
    if sample_no == 16:
        return not boundary
    if sample_no == 22:
        return not boundary and (er <= 1 or ip <= 1)
    if sample_no == 40:
        return ex <= 1
    if sample_no == 15:
        return not boundary and er >= 1 and ip >= 1
    return True


def make_blind_row(
    sample_no: int,
    scenario: str,
    orientation: str,
    user_message: str,
    history_json: str,
    candidate_text: str,
) -> dict[str, str]:
    return {
        "sample_no": str(sample_no),
        "scenario": scenario,
        "orientation": orientation,
        "用户倾诉": user_message,
        "对话历史": history_json,
        "候选文本": candidate_text,
        "A_ER": "",
        "A_IP": "",
        "A_EX": "",
        "B_ER": "",
        "B_IP": "",
        "B_EX": "",
    }


def _make_llm_client(settings: Settings):
    if settings.LLM_PROVIDER.lower() == "deepseek":
        return DeepSeekLLMClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
        )
    return MockLLMClient()


async def _generate_case(
    generator: GeneratorService,
    case: F9Case,
):
    return await generator.generate(
        GeneratorGenerateRequest(
            session_id=f"f9-validation-{case.sample_no}",
            user_message=case.user_message,
            history=case.history,
            scenario=case.scenario,
            rag_examples=[],
        )
    )


async def _score_candidates(
    critic: CriticService,
    case: F9Case,
    candidates: list[CandidateInput],
):
    return await critic.evaluate(
        CriticEvaluateRequest(
            session_id=f"f9-validation-{case.sample_no}",
            user_message=case.user_message,
            history=case.history,
            activated_casel=[],
            candidates=candidates,
        )
    )


def _score_row(
    case: F9Case,
    candidate_id: str,
    orientation: str,
    text: str,
    score: CandidateScore,
    source: str,
) -> dict[str, str]:
    sample_flags = detect_f3_regression_flags(case.sample_no, text)
    global_flags = detect_f3_global_quality_flags(text)
    return {
        "sample_no": str(case.sample_no),
        "source": source,
        "candidate_id": candidate_id,
        "scenario": case.scenario,
        "orientation": orientation,
        "用户倾诉": case.user_message,
        "候选文本": text,
        "issue_types": case.issue_types,
        "template_flags": case.template_flags,
        "detected_flags": ";".join(sample_flags),
        "global_quality_flags": ";".join(global_flags),
        "f3_regression_pass": str(
            not sample_flags and not global_flags and text != GENERATOR_FALLBACK_TEXT
        ).lower(),
        "F4_ER": score.epitome.ER,
        "F4_IP": score.epitome.IP,
        "F4_EX": score.epitome.EX,
        "boundary_flag": str(score.boundary_flag).lower(),
        "boundary_reason": score.boundary_reason,
        "weighted_total": f"{score.weighted_total:.3f}",
        "f4_expectation_pass": str(
            f4_expectation_passed(
                case.sample_no,
                score.epitome.ER,
                score.epitome.IP,
                score.epitome.EX,
                score.boundary_flag,
            )
        ).lower(),
        "rationale": score.rationale,
    }


def _score_fieldnames() -> list[str]:
    return [
        "sample_no",
        "source",
        "candidate_id",
        "scenario",
        "orientation",
        "用户倾诉",
        "候选文本",
        "issue_types",
        "template_flags",
        "detected_flags",
        "global_quality_flags",
        "f3_regression_pass",
        "F4_ER",
        "F4_IP",
        "F4_EX",
        "boundary_flag",
        "boundary_reason",
        "weighted_total",
        "f4_expectation_pass",
        "rationale",
    ]


def low_score_review_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    review_rows: list[dict[str, str]] = []
    for row in rows:
        sample_no = int(row["sample_no"])
        if sample_no not in LOW_SCORE_REVIEW_SAMPLE_NOS:
            continue
        if str(row["F4_ER"]) == "2" and str(row["F4_IP"]) == "2":
            continue
        review_rows.append(
            {column: row.get(column, "") for column in LOW_SCORE_REVIEW_COLUMNS}
        )
    return review_rows


def _candidate_input(candidate_id: str, orientation: str, text: str) -> CandidateInput:
    return CandidateInput(candidate_id=candidate_id, orientation=orientation, text=text)


def _selected_orientation_candidate(generated_response, orientation: str):
    for candidate in generated_response.candidates:
        if candidate.orientation == orientation:
            return candidate
    raise ValueError(f"generated response has no orientation {orientation!r}")


async def run_validation(
    analysis_path: str | Path,
    blind_path: str | Path,
    output_dir: str | Path,
    settings: Settings,
    f9_limit: int | None = None,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    llm_client = _make_llm_client(settings)
    generator = GeneratorService(llm_client, settings)
    critic = CriticService(llm_client, None, settings)

    golden_cases = load_cases(analysis_path, blind_path, GOLDEN_SAMPLE_NOS)
    generated_rows: list[dict[str, str]] = []
    old_rows: list[dict[str, str]] = []

    for case in golden_cases:
        generated = await _generate_case(generator, case)
        generated_inputs = [
            _candidate_input(candidate.candidate_id, candidate.orientation, candidate.text)
            for candidate in generated.candidates
        ]
        generated_scores = await _score_candidates(critic, case, generated_inputs)
        scores_by_id = {score.candidate_id: score for score in generated_scores.scores}
        for candidate in generated.candidates:
            generated_rows.append(
                _score_row(
                    case,
                    candidate.candidate_id,
                    candidate.orientation,
                    candidate.text,
                    scores_by_id[candidate.candidate_id],
                    "generated",
                )
            )

        old_input = [_candidate_input("old", case.orientation, case.old_candidate)]
        old_scores = await _score_candidates(critic, case, old_input)
        old_rows.append(
            _score_row(
                case,
                "old",
                case.orientation,
                case.old_candidate,
                old_scores.scores[0],
                "old_candidate",
            )
        )

    golden_output = output / "golden"
    rerun_output = output / "rerun"
    generated_path = golden_output / "f9_golden_generated_scores.csv"
    old_path = golden_output / "f9_golden_existing_f4_scores.csv"
    _write_csv(generated_path, _score_fieldnames(), generated_rows)
    _write_csv(old_path, _score_fieldnames(), old_rows)

    all_cases = load_cases(
        analysis_path,
        blind_path,
        [int(row["sample_no"]) for row in _read_csv(analysis_path)],
    )
    if f9_limit is not None:
        all_cases = all_cases[:f9_limit]

    blind_rows: list[dict[str, str]] = []
    holdout_rows: list[dict[str, str]] = []
    rerun_score_rows: list[dict[str, str]] = []
    for case in all_cases:
        generated = await _generate_case(generator, case)
        selected = _selected_orientation_candidate(generated, case.orientation)
        selected_input = [
            _candidate_input(selected.candidate_id, selected.orientation, selected.text)
        ]
        selected_scores = await _score_candidates(critic, case, selected_input)
        score = selected_scores.scores[0]
        blind_rows.append(
            make_blind_row(
                case.sample_no,
                case.scenario,
                selected.orientation,
                case.user_message,
                case.history_json,
                selected.text,
            )
        )
        holdout_rows.append(
            {
                "sample_no": str(case.sample_no),
                "F4_ER": score.epitome.ER,
                "F4_IP": score.epitome.IP,
                "F4_EX": score.epitome.EX,
            }
        )
        rerun_score_rows.append(
            _score_row(
                case,
                selected.candidate_id,
                selected.orientation,
                selected.text,
                score,
                "f9_rerun_selected",
            )
        )

    blind_output_path = rerun_output / "f9_rerun_blind_annotation.csv"
    holdout_output_path = rerun_output / "f9_rerun_f4_scores_holdout.csv"
    rerun_scores_path = rerun_output / "f9_rerun_selected_scores.csv"
    review_queue_path = rerun_output / "f9_low_score_review_queue.csv"
    manifest_path = rerun_output / "f9_rerun_manifest.json"
    report_path = output / "f9_validation_report.md"
    _write_csv(blind_output_path, F9_BLIND_COLUMNS, blind_rows)
    _write_csv(holdout_output_path, F4_HOLDOUT_COLUMNS, holdout_rows)
    _write_csv(rerun_scores_path, _score_fieldnames(), rerun_score_rows)
    review_queue_rows = low_score_review_rows(rerun_score_rows)
    _write_csv(review_queue_path, LOW_SCORE_REVIEW_COLUMNS, review_queue_rows)

    manifest = {
        "golden_sample_nos": GOLDEN_SAMPLE_NOS,
        "f9_rerun_rows": len(blind_rows),
        "llm_provider": settings.LLM_PROVIDER,
        "deepseek_model": settings.DEEPSEEK_MODEL,
        "critic_sample_count": settings.CRITIC_SAMPLE_COUNT,
        "generated_scores_path": str(generated_path),
        "old_candidate_scores_path": str(old_path),
        "blind_annotation_path": str(blind_output_path),
        "f4_holdout_path": str(holdout_output_path),
        "rerun_scores_path": str(rerun_scores_path),
        "low_score_review_queue_path": str(review_queue_path),
        "low_score_review_queue_rows": len(review_queue_rows),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(
        build_report(generated_rows, old_rows, rerun_score_rows, manifest),
        encoding="utf-8",
    )
    return {
        "generated_scores": generated_path,
        "old_candidate_scores": old_path,
        "blind_annotation": blind_output_path,
        "f4_holdout": holdout_output_path,
        "rerun_scores": rerun_scores_path,
        "low_score_review_queue": review_queue_path,
        "manifest": manifest_path,
        "report": report_path,
    }


def _pass_counter(rows: list[dict[str, str]], column: str) -> Counter:
    return Counter(row[column] for row in rows)


def _epitome_distribution(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    return {
        dim: dict(Counter(str(row[f"F4_{dim}"]) for row in rows))
        for dim in ["ER", "IP", "EX"]
    }


def _all_er_ip_are_two(rows: list[dict[str, str]]) -> bool:
    return bool(rows) and all(
        str(row["F4_ER"]) == "2" and str(row["F4_IP"]) == "2" for row in rows
    )


def _count_er_ip_both_two(rows: list[dict[str, str]]) -> int:
    return sum(
        1 for row in rows if str(row["F4_ER"]) == "2" and str(row["F4_IP"]) == "2"
    )


def _count_epitome_two(rows: list[dict[str, str]], dim: str) -> int:
    return sum(1 for row in rows if str(row[f"F4_{dim}"]) == "2")


def _minimum_count(total: int, ratio: float) -> int:
    return math.ceil(total * ratio)


def _maximum_count(total: int, ratio: float) -> int:
    return math.floor(total * ratio)


def _gate_assessment(
    generated_rows: list[dict[str, str]],
    generated_flags: list[dict[str, str]],
    generated_global_quality_flags: list[dict[str, str]],
    old_rows: list[dict[str, str]],
    rerun_rows: list[dict[str, str]],
    rerun_flags: list[dict[str, str]],
    rerun_global_quality_flags: list[dict[str, str]],
    fallback_rows: list[dict[str, str]],
) -> dict:
    old_total = len(old_rows)
    old_pass = sum(1 for row in old_rows if row["f4_expectation_pass"] == "true")
    old_pass_min = _minimum_count(old_total, 0.8) if old_total else 0
    old_er_ip_two = _count_er_ip_both_two(old_rows)
    old_er_ip_two_max = _maximum_count(old_total, 0.2) if old_total else 0

    rerun_total = len(rerun_rows)
    rerun_er_two = _count_epitome_two(rerun_rows, "ER")
    rerun_ip_two = _count_epitome_two(rerun_rows, "IP")
    rerun_two_max = _maximum_count(rerun_total, 0.8) if rerun_total else 0

    blocking_reasons: list[str] = []
    if not old_rows:
        blocking_reasons.append("缺少旧坏候选 F4 复评数据。")
    elif old_pass < old_pass_min:
        blocking_reasons.append(
            f"旧坏候选 F4 复评通过 {old_pass}/{old_total}，低于 {old_pass_min}/{old_total} 门槛。"
        )
    if old_rows and old_er_ip_two > old_er_ip_two_max:
        blocking_reasons.append(
            f"旧坏候选 ER/IP 同时 2/2 为 {old_er_ip_two}/{old_total}，高于 {old_er_ip_two_max}/{old_total} 上限。"
        )

    if not rerun_rows:
        blocking_reasons.append("缺少重跑样本数据。")
    elif rerun_er_two > rerun_two_max or rerun_ip_two > rerun_two_max:
        blocking_reasons.append(
            f"重跑样本 ER=2 为 {rerun_er_two}/{rerun_total}，IP=2 为 {rerun_ip_two}/{rerun_total}，仍接近满分饱和。"
        )

    if generated_flags:
        blocking_reasons.append(
            f"F3 golden 检测到 {len(generated_flags)} 条 flagged rows，需清除第三方事实/动机补全等残留。"
        )
    if rerun_flags:
        blocking_reasons.append(
            f"重跑样本检测到 {len(rerun_flags)} 条 flagged rows，不应进入正式人工 F9。"
        )
    if len(generated_global_quality_flags) > GENERATED_GLOBAL_QUALITY_FLAG_MAX:
        blocking_reasons.append(
            "F3 golden 全局品质化总结探针命中 "
            f"{len(generated_global_quality_flags)}/{len(generated_rows)}，"
            f"高于 {GENERATED_GLOBAL_QUALITY_FLAG_MAX}/{len(generated_rows)} 上限。"
        )
    if len(rerun_global_quality_flags) > RERUN_GLOBAL_QUALITY_FLAG_MAX:
        blocking_reasons.append(
            "重跑样本全局品质化总结探针命中 "
            f"{len(rerun_global_quality_flags)}/{len(rerun_rows)}，"
            f"高于 {RERUN_GLOBAL_QUALITY_FLAG_MAX}/{len(rerun_rows)} 上限。"
        )
    if fallback_rows:
        blocking_reasons.append(
            f"生成器 fallback 行数为 {len(fallback_rows)}，需先排除生成失败。"
        )

    return {
        "decision": "FAIL" if blocking_reasons else "PASS",
        "blocking_reasons": blocking_reasons,
        "old_pass": old_pass,
        "old_total": old_total,
        "old_pass_min": old_pass_min,
        "old_er_ip_two": old_er_ip_two,
        "old_er_ip_two_max": old_er_ip_two_max,
        "rerun_total": rerun_total,
        "rerun_er_two": rerun_er_two,
        "rerun_ip_two": rerun_ip_two,
        "rerun_two_max": rerun_two_max,
        "generated_flag_count": len(generated_flags),
        "rerun_flag_count": len(rerun_flags),
        "generated_global_quality_flag_count": len(generated_global_quality_flags),
        "generated_global_quality_flag_max": GENERATED_GLOBAL_QUALITY_FLAG_MAX,
        "rerun_global_quality_flag_count": len(rerun_global_quality_flags),
        "rerun_global_quality_flag_max": RERUN_GLOBAL_QUALITY_FLAG_MAX,
        "fallback_count": len(fallback_rows),
    }


def build_report(
    generated_rows: list[dict[str, str]],
    old_rows: list[dict[str, str]],
    rerun_rows: list[dict[str, str]],
    manifest: dict,
) -> str:
    generated_flags = [row for row in generated_rows if row["detected_flags"]]
    generated_global_quality_flags = [
        row for row in generated_rows if row["global_quality_flags"]
    ]
    old_failed = [row for row in old_rows if row["f4_expectation_pass"] != "true"]
    rerun_flags = [row for row in rerun_rows if row["detected_flags"]]
    rerun_global_quality_flags = [
        row for row in rerun_rows if row["global_quality_flags"]
    ]
    review_queue = low_score_review_rows(rerun_rows)
    fallback_rows = [
        row
        for row in generated_rows + rerun_rows
        if row["候选文本"] == GENERATOR_FALLBACK_TEXT
    ]

    gate = _gate_assessment(
        generated_rows=generated_rows,
        generated_flags=generated_flags,
        generated_global_quality_flags=generated_global_quality_flags,
        old_rows=old_rows,
        rerun_rows=rerun_rows,
        rerun_flags=rerun_flags,
        rerun_global_quality_flags=rerun_global_quality_flags,
        fallback_rows=fallback_rows,
    )

    lines = [
        "# F9 Golden/F4 Rerun Validation Report",
        "",
        "## Run Config",
        "",
        f"- llm_provider: {manifest['llm_provider']}",
        f"- deepseek_model: {manifest['deepseek_model']}",
        f"- critic_sample_count: {manifest['critic_sample_count']}",
        f"- golden_sample_nos: {manifest['golden_sample_nos']}",
        f"- f9_rerun_rows: {manifest['f9_rerun_rows']}",
        "",
        "## Gate Decision",
        "",
        f"- decision: {gate['decision']}",
        f"- old_candidate_expectation_pass: {gate['old_pass']}/{gate['old_total']} (门槛: >= {gate['old_pass_min']}/{gate['old_total']})",
        f"- old_candidate_ER_IP_2_2: {gate['old_er_ip_two']}/{gate['old_total']} (上限: <= {gate['old_er_ip_two_max']}/{gate['old_total']})",
        f"- rerun_ER_2: {gate['rerun_er_two']}/{gate['rerun_total']} (上限: <= {gate['rerun_two_max']}/{gate['rerun_total']})",
        f"- rerun_IP_2: {gate['rerun_ip_two']}/{gate['rerun_total']} (上限: <= {gate['rerun_two_max']}/{gate['rerun_total']})",
        f"- generated_detected_flags: {gate['generated_flag_count']} (门槛: 0)",
        f"- rerun_detected_flags: {gate['rerun_flag_count']} (门槛: 0)",
        f"- generated_global_quality_flagged_rows: {gate['generated_global_quality_flag_count']}/{len(generated_rows)} (上限: <= {gate['generated_global_quality_flag_max']}/{len(generated_rows)})",
        f"- rerun_global_quality_flagged_rows: {gate['rerun_global_quality_flag_count']}/{gate['rerun_total']} (上限: <= {gate['rerun_global_quality_flag_max']}/{gate['rerun_total']})",
        f"- generator_fallback_rows: {gate['fallback_count']} (门槛: 0)",
        "",
        "## Automatic Gate Criteria",
        "",
        "- 旧坏候选 F4 复评通过率至少 80%。",
        "- 旧坏候选 ER/IP 同时 2/2 的比例不超过 20%。",
        "- 重跑样本 ER=2 与 IP=2 的比例都不超过 80%，避免接近满分饱和。",
        "- F4 rationale 若识别模板化、第三方解释、事实补全、强行重构，分数必须实际降下来。",
        "- F3 golden 与重跑样本不得出现检测到的第三方事实/动机补全等 regression flags。",
        "- F3 全局品质化总结探针在 golden generated rows 中最多 2/20，在 rerun selected rows 中最多 4/40。",
        "- 样本级 hard regression flags 与全局 quality probes 分开统计；hard flags 必须为 0。",
        "- 生成器不得 fallback。",
        "",
        "## Blocking Reasons",
        "",
        *(
            [f"- {reason}" for reason in gate["blocking_reasons"]]
            if gate["blocking_reasons"]
            else ["- 无；自动准入通过，可进入人工 F9 准备。"]
        ),
        "",
        "## Golden Generated Candidates",
        "",
        f"- generated_candidate_rows: {len(generated_rows)}",
        f"- f3_regression_pass_distribution: {dict(_pass_counter(generated_rows, 'f3_regression_pass'))}",
        f"- rows_with_detected_flags: {len(generated_flags)}",
        f"- ER/IP_all_2: {_all_er_ip_are_two(generated_rows)}",
        f"- F4_distribution: {_epitome_distribution(generated_rows)}",
        "",
        "## Existing Bad Candidate F4 Re-score",
        "",
        f"- old_candidate_rows: {len(old_rows)}",
        f"- f4_expectation_pass_distribution: {dict(_pass_counter(old_rows, 'f4_expectation_pass'))}",
        f"- expectation_failed_rows: {len(old_failed)}",
        f"- ER/IP_all_2: {_all_er_ip_are_two(old_rows)}",
        f"- F4_distribution: {_epitome_distribution(old_rows)}",
        "",
        "## F9 Rerun Package",
        "",
        f"- blind_annotation_path: `{manifest['blind_annotation_path']}`",
        f"- f4_holdout_path: `{manifest['f4_holdout_path']}`",
        f"- rerun_scores_path: `{manifest['rerun_scores_path']}`",
        f"- low_score_review_queue_path: `{manifest.get('low_score_review_queue_path', '')}`",
        f"- low_score_review_queue_rows: {len(review_queue)}",
        f"- f3_detected_flags_in_selected_rows: {len(rerun_flags)}",
        f"- generator_fallback_rows: {len(fallback_rows)}",
        f"- ER/IP_all_2: {_all_er_ip_are_two(rerun_rows)}",
        f"- F4_distribution: {_epitome_distribution(rerun_rows)}",
    ]
    if generated_flags:
        lines.extend(["", "## Generated Flagged Rows", "", "| sample_no | candidate_id | flags |", "|---:|---|---|"])
        for row in generated_flags:
            lines.append(f"| {row['sample_no']} | {row['candidate_id']} | {row['detected_flags']} |")
    if generated_global_quality_flags:
        lines.extend(["", "## Generated Global Quality Flagged Rows", "", "| sample_no | candidate_id | flags |", "|---:|---|---|"])
        for row in generated_global_quality_flags:
            lines.append(f"| {row['sample_no']} | {row['candidate_id']} | {row['global_quality_flags']} |")
    if old_failed:
        lines.extend(["", "## F4 Expectation Failed Rows", "", "| sample_no | F4_ER | F4_IP | F4_EX | boundary |", "|---:|---:|---:|---:|---|"])
        for row in old_failed:
            lines.append(
                f"| {row['sample_no']} | {row['F4_ER']} | {row['F4_IP']} | {row['F4_EX']} | {row['boundary_flag']} |"
            )
    if rerun_flags:
        lines.extend(["", "## F9 Rerun Selected Flagged Rows", "", "| sample_no | flags |", "|---:|---|"])
        for row in rerun_flags:
            lines.append(f"| {row['sample_no']} | {row['detected_flags']} |")
    if rerun_global_quality_flags:
        lines.extend(["", "## Rerun Global Quality Flagged Rows", "", "| sample_no | candidate_id | flags |", "|---:|---|---|"])
        for row in rerun_global_quality_flags:
            lines.append(f"| {row['sample_no']} | {row['candidate_id']} | {row['global_quality_flags']} |")
    if review_queue:
        lines.extend(["", "## Manual Low-Score Review Queue", "", "| sample_no | candidate_id | F4_ER | F4_IP | F4_EX |", "|---:|---|---:|---:|---:|"])
        for row in review_queue:
            lines.append(f"| {row['sample_no']} | {row['candidate_id']} | {row['F4_ER']} | {row['F4_IP']} | {row['F4_EX']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run F9 golden regression, F4 re-score, and rerun package export."
    )
    parser.add_argument(
        "--analysis-path",
        default="docs/corpus/f9/error-analysis/f9_error_analysis_draft.csv",
    )
    parser.add_argument(
        "--blind-path",
        default="docs/corpus/f9/baseline/f9_blind_annotation.csv",
    )
    parser.add_argument("--output-dir", default="docs/corpus/f9/validation")
    parser.add_argument("--critic-sample-count", type=int, default=None)
    parser.add_argument("--f9-limit", type=int, default=None)
    args = parser.parse_args()

    settings_kwargs = {}
    if args.critic_sample_count is not None:
        settings_kwargs["CRITIC_SAMPLE_COUNT"] = args.critic_sample_count
    settings = Settings(**settings_kwargs)

    result = asyncio.run(
        run_validation(
            args.analysis_path,
            args.blind_path,
            args.output_dir,
            settings,
            f9_limit=args.f9_limit,
        )
    )
    for key, path in result.items():
        print(f"{key}={path}")


if __name__ == "__main__":
    main()
