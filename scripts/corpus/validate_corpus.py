from __future__ import annotations

import argparse
import asyncio
import csv
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas.safety import SafetyGateRequest
from app.services.llm_client import DeepSeekLLMClient, MockLLMClient
from app.services.safety_gate_service import SafetyGateService
from scripts.corpus.models import RejectedUtterance, read_jsonl, write_jsonl


MIN_TEXT_LENGTH = 20
ACCEPT_TEXT_LENGTH_MAX = 180
REVIEW_TEXT_LENGTH_MAX = 220

EXPLICIT_CRISIS_TERMS = [
    "自杀",
    "自残",
    "伤害自己",
    "活着没意思",
    "不想活",
    "不想存在",
    "消失算了",
    "结束生命",
]
NON_STUDENT_MARKERS = [
    "建议回复",
    "系统回应",
    "作为老师",
    "作为心理咨询师",
    "以下是",
    "可以这样说",
    "倾诉内容：",
]


@dataclass(frozen=True)
class ValidationResult:
    output_dir: Path
    accepted_path: Path
    rejected_path: Path
    quarantine_path: Path
    length_review_path: Path
    review_path: Path
    summary_path: Path
    accepted_count: int
    rejected_count: int
    quarantined_count: int
    length_review_count: int


def normalize_text(text: str) -> str:
    return re.sub(r"[\s，。！？、,.!?；;：:\"'“”‘’（）()《》<>-]+", "", text)


def char_ngrams(text: str, n: int = 3) -> set[str]:
    normalized = normalize_text(text)
    if len(normalized) <= n:
        return {normalized} if normalized else set()
    return {normalized[index : index + n] for index in range(len(normalized) - n + 1)}


def jaccard_similarity(left: str, right: str) -> float:
    left_grams = char_ngrams(left)
    right_grams = char_ngrams(right)
    if not left_grams and not right_grams:
        return 1.0
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams & right_grams) / len(left_grams | right_grams)


def text_similarity(left: str, right: str) -> float:
    return max(
        jaccard_similarity(left, right),
        difflib.SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio(),
    )


def sentence_count(text: str) -> int:
    parts = [part.strip() for part in re.split(r"[。！？!?]+", text) if part.strip()]
    return len(parts)


def _mechanical_rejection(row: dict[str, Any]) -> str | None:
    required = ["id", "persona", "persona_basis", "scenario", "text"]
    missing = [field for field in required if not row.get(field)]
    if missing:
        return f"missing_fields:{','.join(missing)}"
    text = str(row["text"]).strip()
    if _has_explicit_crisis(text):
        return None
    if len(text) < MIN_TEXT_LENGTH or len(text) > REVIEW_TEXT_LENGTH_MAX:
        return "text_length_out_of_range"
    count = sentence_count(text)
    if count < 1 or count > 5:
        return "sentence_count_out_of_range"
    if any(marker in text for marker in NON_STUDENT_MARKERS):
        return "non_student_or_prompt_marker"
    return None


def _needs_length_review(row: dict[str, Any]) -> bool:
    text = str(row["text"]).strip()
    return ACCEPT_TEXT_LENGTH_MAX < len(text) <= REVIEW_TEXT_LENGTH_MAX


def _has_explicit_crisis(text: str) -> bool:
    return any(term in text for term in EXPLICIT_CRISIS_TERMS)


def _build_safety_service() -> SafetyGateService:
    settings = Settings()
    if settings.LLM_PROVIDER.lower() == "deepseek":
        llm_client = DeepSeekLLMClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            thinking_type=settings.DEEPSEEK_THINKING,
        )
    else:
        llm_client = MockLLMClient()
    return SafetyGateService(llm_client, None, settings)


async def _f1_screen(row: dict[str, Any], safety_service) -> tuple[bool, str, str]:
    try:
        response = await safety_service.evaluate(
            SafetyGateRequest(
                session_id=f"{row.get('run_id', 'corpus')}-{row['id']}-safety",
                current_message=row["text"],
                history=[],
            )
        )
    except Exception as exc:
        return False, "f1_exception", str(exc)
    if response.risk_level != "green":
        return False, "f1_non_green", response.rationale
    return True, "", response.rationale


def _duplicate_reason(
    row: dict[str, Any],
    accepted: list[dict[str, Any]],
    cell_threshold: float,
    global_threshold: float,
) -> str | None:
    text = row["text"]
    key = (row["persona"], row["scenario"])
    normalized = normalize_text(text)
    for existing in accepted:
        existing_text = existing["text"]
        if normalize_text(existing_text) == normalized:
            return "duplicate_exact"
        similarity = text_similarity(text, existing_text)
        existing_key = (existing["persona"], existing["scenario"])
        if existing_key == key and similarity >= cell_threshold:
            return "duplicate_in_cell"
        if similarity >= global_threshold:
            return "duplicate_global"
    return None


async def validate_corpus(
    raw_path: str | Path,
    output_dir: str | Path,
    safety_service=None,
    cell_similarity_threshold: float = 0.82,
    global_similarity_threshold: float = 0.90,
) -> ValidationResult:
    raw_rows = read_jsonl(Path(raw_path))
    output = Path(output_dir)
    accepted_path = output / "accepted.json"
    rejected_path = output / "rejected.jsonl"
    quarantine_path = output / "quarantine_safety_only.jsonl"
    length_review_path = output / "length_review.jsonl"
    review_path = output / "review.csv"
    summary_path = output / "summary_validation.md"
    output.mkdir(parents=True, exist_ok=True)
    safety = safety_service or _build_safety_service()

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    length_review: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    for row in raw_rows:
        mechanical_reason = _mechanical_rejection(row)
        if mechanical_reason is not None:
            rejected.append(
                RejectedUtterance(row, mechanical_reason).to_dict()
            )
            continue
        if _has_explicit_crisis(row["text"]):
            quarantined.append(
                RejectedUtterance(row, "explicit_crisis_signal").to_dict()
            )
            continue
        f1_ok, f1_reason, f1_detail = await _f1_screen(row, safety)
        row["f1_risk_level"] = "green" if f1_ok else "non_green_or_error"
        row["f1_rationale"] = f1_detail
        if not f1_ok:
            quarantined.append(RejectedUtterance(row, f1_reason, f1_detail).to_dict())
            continue
        if _needs_length_review(row):
            row["quality_status"] = "needs_length_repair"
            row.setdefault("check_note", "181-220 chars; shorten to <=180 and rerun validation.")
            length_review.append(
                RejectedUtterance(row, "length_review_required").to_dict()
            )
            review_rows.append(
                {
                    "id": row["id"],
                    "persona": row["persona"],
                    "scenario": row["scenario"],
                    "subscenario": row.get("subscenario", ""),
                    "text": row["text"],
                    "quality_status": row["quality_status"],
                    "manual_decision": "",
                    "manual_note": row["check_note"],
                }
            )
            continue
        duplicate_reason = _duplicate_reason(
            row,
            accepted,
            cell_similarity_threshold,
            global_similarity_threshold,
        )
        if duplicate_reason is not None:
            rejected.append(RejectedUtterance(row, duplicate_reason).to_dict())
            continue
        row["quality_status"] = "accepted_pending_human_review"
        row.setdefault("check_note", "")
        accepted.append(row)
        review_rows.append(
            {
                "id": row["id"],
                "persona": row["persona"],
                "scenario": row["scenario"],
                "subscenario": row.get("subscenario", ""),
                "text": row["text"],
                "quality_status": row["quality_status"],
                "manual_decision": "",
                "manual_note": "",
            }
        )

    accepted_path.write_text(
        json.dumps(
            {
                "_meta": {
                    "source_raw": str(raw_path),
                    "total": len(accepted),
                    "note": "F1 green, mechanically valid, deduplicated synthetic single-turn utterances.",
                },
                "samples": accepted,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_jsonl(rejected_path, rejected)
    write_jsonl(quarantine_path, quarantined)
    write_jsonl(length_review_path, length_review)
    with review_path.open("w", encoding="utf-8-sig", newline="") as file:
        fieldnames = [
            "id",
            "persona",
            "scenario",
            "subscenario",
            "text",
            "quality_status",
            "manual_decision",
            "manual_note",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(review_rows)
    summary_path.write_text(
        "\n".join(
            [
                "# Corpus Validation Summary",
                "",
                f"- raw_rows: {len(raw_rows)}",
                f"- accepted: {len(accepted)}",
                f"- rejected: {len(rejected)}",
                f"- quarantined: {len(quarantined)}",
                f"- length_review: {len(length_review)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return ValidationResult(
        output_dir=output,
        accepted_path=accepted_path,
        rejected_path=rejected_path,
        quarantine_path=quarantine_path,
        length_review_path=length_review_path,
        review_path=review_path,
        summary_path=summary_path,
        accepted_count=len(accepted),
        rejected_count=len(rejected),
        quarantined_count=len(quarantined),
        length_review_count=len(length_review),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated EmoEdu corpus.")
    parser.add_argument("--raw-path", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    asyncio.run(validate_corpus(args.raw_path, args.output_dir))


if __name__ == "__main__":
    main()
