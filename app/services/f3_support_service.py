from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings


POSITIVE_USE_TIERS = {"direct_exemplar", "strategy_reference"}
DIRECT_USE_TIER = "direct_exemplar"
POSITIVE_QUALITY = {"good", "rewrite"}
SAFE_LEVELS = {"green"}

DISPLAY_STRATEGY = {
    "Restatement": "具体复述",
    "Approval and Reassurance": "温和承接",
    "Interpretation": "处境澄清",
    "Direct Guidance": "行动建议",
    "Information": "信息补充",
    "Self-disclosure": "自我暴露",
    "Others": "其他",
}

PROMPT_USEFUL_STRATEGIES = {
    "Restatement",
    "Approval and Reassurance",
    "Interpretation",
    "Information",
}

UNSUITABLE_FRAGMENT_PATTERNS = (
    "楼主",
    "题主",
    "抱抱",
    "咨询师",
    "心理咨询",
    "诊断",
    "治疗",
    "药物",
    "你可以",
    "建议你",
    "我建议",
    "我们需要",
    "校园欺凌事件",
    "你就是你",
    "最棒",
    "爱着你",
    "世界和我",
    "未来道路",
    "与怪物无关",
    "加油",
    "祝",
)


@dataclass(frozen=True)
class F3SupportExample:
    source_index: int | str
    use_tier: str
    scenario: str
    input_text: str
    strategy_sequence: tuple[str, ...]
    strategy_segments: tuple[dict[str, str], ...]
    tokens: frozenset[str]


@dataclass(frozen=True)
class F3SupportContext:
    strategy_prior: str = ""
    support_cards: list[str] = field(default_factory=list)

    @property
    def support_cards_text(self) -> str:
        return "\n\n".join(self.support_cards) if self.support_cards else "无"


class F3SupportService:
    """从 PsyQA 标注数据生成 F3 的策略先验和轻量 RAG 支持卡。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(getattr(settings, "F3_SUPPORT_ENABLE", True))
        self.top_k = int(getattr(settings, "F3_SUPPORT_TOP_K", 2))
        self.min_score = float(getattr(settings, "F3_SUPPORT_MIN_SCORE", 0.10))
        self.data_path = self._resolve_data_path(
            getattr(settings, "F3_PSYQA_LABELLED_PATH", "exp/data/psyqa_labelled.json")
        )
        self.rows = self._load_rows(self.data_path) if self.enabled else []
        self.strategy_stats = self._build_strategy_stats(self.rows)
        self.examples = self._build_examples(self.rows)
        self.direct_counts = Counter(
            item.scenario for item in self.examples if item.use_tier == DIRECT_USE_TIER
        )

    def build_context(
        self,
        *,
        scenario: str,
        user_message: str,
        external_examples: list[str] | None = None,
    ) -> F3SupportContext:
        if not self.enabled:
            return F3SupportContext(
                strategy_prior="",
                support_cards=self._format_external_examples(external_examples or []),
            )
        support_cards = self._retrieve_support_cards(scenario, user_message)
        support_cards.extend(self._format_external_examples(external_examples or []))
        return F3SupportContext(
            strategy_prior=self._format_strategy_prior(scenario),
            support_cards=support_cards[: self.top_k + len(external_examples or [])],
        )

    @staticmethod
    def _resolve_data_path(path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path
        cwd_path = Path.cwd() / path
        if cwd_path.exists():
            return cwd_path
        project_root = Path(__file__).resolve().parents[2]
        return project_root / path

    @staticmethod
    def _load_rows(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return []
        return value if isinstance(value, list) else []

    @staticmethod
    def _row_ok_for_stats(row: dict[str, Any]) -> bool:
        return (
            row.get("status") == "ok"
            and row.get("use_tier") in POSITIVE_USE_TIERS
            and row.get("quality_label") in POSITIVE_QUALITY
        )

    @staticmethod
    def _row_ok_for_direct_example(row: dict[str, Any]) -> bool:
        return (
            row.get("status") == "ok"
            and row.get("use_tier") == DIRECT_USE_TIER
            and row.get("quality_label") == "good"
            and row.get("safety_level") in SAFE_LEVELS
        )

    @staticmethod
    def _row_ok_for_reference_example(row: dict[str, Any]) -> bool:
        return (
            row.get("status") == "ok"
            and row.get("use_tier") == "strategy_reference"
            and row.get("quality_label") in POSITIVE_QUALITY
            and row.get("safety_level") in SAFE_LEVELS
        )

    def _build_strategy_stats(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "row_count": 0,
                "strategy": Counter(),
                "first": Counter(),
                "transition": Counter(),
            }
        )
        for row in rows:
            if not self._row_ok_for_stats(row):
                continue
            scenario = str(row.get("scenario") or "其他")
            sequence = tuple(str(item) for item in row.get("psyqa_strategy_sequence") or [])
            stats[scenario]["row_count"] += 1
            stats["__global__"]["row_count"] += 1
            if sequence:
                stats[scenario]["first"][sequence[0]] += 1
                stats["__global__"]["first"][sequence[0]] += 1
            for item in sequence:
                stats[scenario]["strategy"][item] += 1
                stats["__global__"]["strategy"][item] += 1
            for left, right in zip(sequence, sequence[1:]):
                transition = f"{left} -> {right}"
                stats[scenario]["transition"][transition] += 1
                stats["__global__"]["transition"][transition] += 1
        return dict(stats)

    def _build_examples(self, rows: list[dict[str, Any]]) -> list[F3SupportExample]:
        examples: list[F3SupportExample] = []
        for row in rows:
            if not (
                self._row_ok_for_direct_example(row)
                or self._row_ok_for_reference_example(row)
            ):
                continue
            input_text = str(row.get("input") or "")
            sequence = tuple(str(item) for item in row.get("psyqa_strategy_sequence") or [])
            raw_segments = row.get("psyqa_strategy_segments") or []
            segments = tuple(
                {
                    "strategy": str(item.get("strategy") or ""),
                    "text": str(item.get("text") or ""),
                }
                for item in raw_segments
                if isinstance(item, dict)
            )
            examples.append(
                F3SupportExample(
                    source_index=row.get("source_index", ""),
                    use_tier=str(row.get("use_tier") or ""),
                    scenario=str(row.get("scenario") or "其他"),
                    input_text=input_text,
                    strategy_sequence=sequence,
                    strategy_segments=segments,
                    tokens=frozenset(tokenize_for_support(input_text)),
                )
            )
        return examples

    def _format_strategy_prior(self, scenario: str) -> str:
        scenario_stats = self.strategy_stats.get(scenario) or self.strategy_stats.get(
            "__global__", {}
        )
        row_count = int(scenario_stats.get("row_count", 0))
        direct_count = int(self.direct_counts.get(scenario, 0))
        top_first = self._format_counter_items(scenario_stats.get("first", Counter()), 3)
        top_strategy = self._format_counter_items(
            scenario_stats.get("strategy", Counter()), 4
        )
        top_transition = self._format_counter_items(
            scenario_stats.get("transition", Counter()), 2
        )
        if row_count == 0:
            return (
                "当前场景缺少足够的 PsyQA 标注支撑。本轮只使用通用支持策略："
                "先具体复述，再温和承接或澄清处境；不要急着建议。"
            )
        return "\n".join(
            [
                f"统计支撑：{scenario} 可参考样本 {row_count} 条，其中直接样例 {direct_count} 条。",
                f"常见起手：{top_first or '无'}。",
                f"高频策略：{top_strategy or '无'}。",
                f"常见路径：{top_transition or '无'}。",
                "本轮使用方式：优先用具体复述、温和承接、处境澄清来支持 c1/c2；Direct Guidance 虽然在 PsyQA 高频，但第一轮默认延后，不主动给步骤化建议；Self-disclosure 不使用。",
                "c1 侧重情绪被接住，c2 侧重处境和担心被说准，两者都要短、口语、低负担。",
            ]
        )

    @staticmethod
    def _format_counter_items(counter: Counter[str], limit: int) -> str:
        parts = []
        for key, value in counter.most_common(limit):
            display_key = format_strategy_path(key)
            parts.append(f"{display_key}({value})")
        return "、".join(parts)

    def _retrieve_support_cards(self, scenario: str, user_message: str) -> list[str]:
        query_tokens = frozenset(tokenize_for_support(user_message))
        exact_direct = [
            item
            for item in self.examples
            if item.scenario == scenario and item.use_tier == DIRECT_USE_TIER
        ]
        exact_reference = [
            item
            for item in self.examples
            if item.scenario == scenario and item.use_tier != DIRECT_USE_TIER
        ]
        ranked = self._rank_examples(query_tokens, exact_direct)
        if len(ranked) < self.top_k:
            ranked.extend(self._rank_examples(query_tokens, exact_reference))
        if len(ranked) < self.top_k:
            ranked.extend(
                self._rank_examples(
                    query_tokens,
                    [item for item in self.examples if item.scenario != scenario],
                )
            )

        seen: set[int | str] = set()
        cards: list[str] = []
        for example in ranked:
            if example.source_index in seen:
                continue
            if raw_similarity(query_tokens, example.tokens) < self.min_score:
                continue
            seen.add(example.source_index)
            cards.append(self._format_support_card(example, len(cards) + 1))
            if len(cards) >= self.top_k:
                break
        return cards

    @staticmethod
    def _rank_examples(
        query_tokens: frozenset[str], examples: list[F3SupportExample]
    ) -> list[F3SupportExample]:
        return sorted(examples, key=lambda example: score_example(query_tokens, example), reverse=True)

    def _format_support_card(self, example: F3SupportExample, index: int) -> str:
        sequence = " -> ".join(
            format_strategy_path(item) for item in compress_sequence(example.strategy_sequence)
        )
        fragments = self._select_fragments(example)
        fragment_text = "\n".join(f"- {item}" for item in fragments) if fragments else "- 无可直接借鉴片段，只参考策略顺序。"
        direct_guidance_note = (
            "注意：样例含行动建议时，只把它当作后续可能方向，本轮不要照搬建议。"
            if "Direct Guidance" in example.strategy_sequence
            else "注意：只借鉴承接和澄清方式，不照抄原句。"
        )
        return "\n".join(
            [
                f"【支持卡 {index}｜{example.use_tier}｜{example.scenario}｜source={example.source_index}】",
                f"相似倾诉：{truncate_text(example.input_text, 90)}",
                f"策略路径：{sequence or '无'}",
                "可借鉴的语言动作：",
                fragment_text,
                direct_guidance_note,
            ]
        )

    @staticmethod
    def _select_fragments(example: F3SupportExample) -> list[str]:
        fragments: list[str] = []
        used_strategy: set[str] = set()
        for segment in example.strategy_segments:
            strategy = segment.get("strategy", "")
            text = clean_segment_text(segment.get("text", ""))
            if strategy not in PROMPT_USEFUL_STRATEGIES:
                continue
            if strategy in used_strategy:
                continue
            if not text:
                continue
            if len(text) < 8:
                continue
            if is_unsuitable_fragment(text):
                continue
            used_strategy.add(strategy)
            fragments.append(f"{format_strategy_path(strategy)}：{truncate_text(text, 54)}")
            if len(fragments) >= 3:
                break
        return fragments

    @staticmethod
    def _format_external_examples(examples: list[str]) -> list[str]:
        formatted = []
        for index, item in enumerate(examples, start=1):
            text = truncate_text(str(item), 180)
            if text:
                formatted.append(
                    f"【外部参考 {index}】{text}\n注意：外部参考只供风格和语气参考，不照抄。"
                )
        return formatted


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def tokenize_for_support(text: str) -> set[str]:
    value = normalize_text(text)
    tokens: set[str] = set()
    for word in re.findall(r"[a-zA-Z0-9_+-]{2,}", value):
        tokens.add(word)
    for block in re.findall(r"[\u4e00-\u9fff]+", value):
        if len(block) <= 2:
            tokens.add(block)
        for size in (2, 3):
            for index in range(max(0, len(block) - size + 1)):
                tokens.add(block[index : index + size])
    return tokens


def clean_segment_text(text: str) -> str:
    value = re.sub(r"<[^>]+>", "", str(text or ""))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def truncate_text(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def raw_similarity(query_tokens: frozenset[str], example_tokens: frozenset[str]) -> float:
    if not query_tokens or not example_tokens:
        return 0.0
    overlap = len(query_tokens & example_tokens)
    return overlap / math.sqrt(len(query_tokens) * len(example_tokens))


def score_example(query_tokens: frozenset[str], example: F3SupportExample) -> float:
    base = raw_similarity(query_tokens, example.tokens)
    tier_bonus = 0.08 if example.use_tier == DIRECT_USE_TIER else 0.0
    support_bonus = 0.02 * sum(
        1 for item in example.strategy_sequence[:4] if item in PROMPT_USEFUL_STRATEGIES
    )
    return base + tier_bonus + support_bonus


def is_unsuitable_fragment(text: str) -> bool:
    return any(pattern in text for pattern in UNSUITABLE_FRAGMENT_PATTERNS)


def compress_sequence(sequence: tuple[str, ...]) -> list[str]:
    compressed: list[str] = []
    for item in sequence:
        if item == "Others":
            continue
        if compressed and compressed[-1] == item:
            continue
        compressed.append(item)
        if len(compressed) >= 6:
            break
    return compressed


def format_strategy_path(value: str) -> str:
    parts = [part.strip() for part in value.split("->")]
    return " -> ".join(
        f"{DISPLAY_STRATEGY.get(part, part)}[{part}]" for part in parts if part
    )
