import json
from dataclasses import dataclass, field
from math import ceil

from app.config import Settings
from app.schemas.safety import ConversationMessage
from app.services.casel_rubric import CASEL_RUBRIC
from app.services.llm_client import LLMClientProtocol


COMPARISON_VALUES = {"A", "B", "tie"}
EPITOME_COMPARISON_KEYS = ("ER", "IP", "EX")


@dataclass(frozen=True)
class PairwiseCandidate:
    candidate_id: str
    orientation: str
    text: str


@dataclass(frozen=True)
class PairwiseContext:
    pair_id: str
    session_id: str
    user_message: str
    history: list[ConversationMessage] = field(default_factory=list)
    activated_casel: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PairwiseOrderResult:
    displayed_first_id: str
    displayed_second_id: str
    raw_winner: str
    winner_id: str | None
    reason: str
    boundary_concern: bool
    boundary_reason: str
    epitome_comparison: dict[str, str] = field(default_factory=dict)
    casel_comparisons: dict[str, str] = field(default_factory=dict)
    invalid: bool = False
    error_reason: str = ""


@dataclass(frozen=True)
class PairwiseSampleResult:
    pair_id: str
    sample_no: int
    judgment_1_winner_id: str | None
    judgment_2_winner_id: str | None
    stable: bool
    stable_winner_id: str | None
    invalid: bool
    reason: str
    judgment_1_epitome_comparison: dict[str, str] = field(default_factory=dict)
    judgment_2_epitome_comparison: dict[str, str] = field(default_factory=dict)
    judgment_1_casel_comparisons: dict[str, str] = field(default_factory=dict)
    judgment_2_casel_comparisons: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PairwiseAggregateResult:
    pair_id: str
    pairwise_sample_count: int
    stable_votes: dict[str, int]
    unstable_count: int
    invalid_count: int
    winner_id: str | None
    pairwise_stable: bool
    pairwise_confidence: str
    selection_method: str


class CriticPairwiseService:
    def __init__(self, llm_client: LLMClientProtocol, settings: Settings):
        self.llm_client = llm_client
        self.settings = settings

    async def judge_sample(
        self,
        context: PairwiseContext,
        candidate_a: PairwiseCandidate,
        candidate_b: PairwiseCandidate,
        sample_no: int,
    ) -> PairwiseSampleResult:
        first = await self._judge_order(context, candidate_a, candidate_b)
        if first.invalid:
            return self._invalid_sample(context.pair_id, sample_no, first.error_reason)

        second = await self._judge_order(context, candidate_b, candidate_a)
        if second.invalid:
            return self._invalid_sample(context.pair_id, sample_no, second.error_reason)

        stable = first.winner_id is not None and first.winner_id == second.winner_id
        return PairwiseSampleResult(
            pair_id=context.pair_id,
            sample_no=sample_no,
            judgment_1_winner_id=first.winner_id,
            judgment_2_winner_id=second.winner_id,
            stable=stable,
            stable_winner_id=first.winner_id if stable else None,
            invalid=False,
            reason=first.reason or second.reason,
            judgment_1_epitome_comparison=first.epitome_comparison,
            judgment_2_epitome_comparison=second.epitome_comparison,
            judgment_1_casel_comparisons=first.casel_comparisons,
            judgment_2_casel_comparisons=second.casel_comparisons,
        )

    async def _judge_order(
        self,
        context: PairwiseContext,
        first: PairwiseCandidate,
        second: PairwiseCandidate,
    ) -> PairwiseOrderResult:
        try:
            raw_response = await self.llm_client.generate(
                prompt=self._build_prompt(context, first, second),
                timeout=self.settings.LLM_TIMEOUT,
                temperature=self.settings.CRITIC_LLM_TEMPERATURE,
                max_tokens=self.settings.CRITIC_LLM_MAX_TOKENS,
                response_format=(
                    {"type": "json_object"}
                    if self.settings.CRITIC_LLM_RESPONSE_FORMAT_JSON
                    else None
                ),
            )
            data = self._parse_response(raw_response, context.activated_casel)
            raw_winner = data["winner"]
            winner_id = self._map_display_winner(raw_winner, first, second)
            return PairwiseOrderResult(
                displayed_first_id=first.candidate_id,
                displayed_second_id=second.candidate_id,
                raw_winner=raw_winner,
                winner_id=winner_id,
                reason=str(data.get("reason", "")),
                boundary_concern=bool(data.get("boundary_concern", False)),
                boundary_reason=str(data.get("boundary_reason", "")),
                epitome_comparison=self._map_comparison_values(
                    data["epitome_comparison"], first, second
                ),
                casel_comparisons=self._map_comparison_values(
                    data["casel_comparisons"], first, second
                ),
            )
        except Exception as exc:
            return PairwiseOrderResult(
                displayed_first_id=first.candidate_id,
                displayed_second_id=second.candidate_id,
                raw_winner="",
                winner_id=None,
                reason="",
                boundary_concern=False,
                boundary_reason="",
                invalid=True,
                error_reason=f"parse_failure:{exc}",
            )

    @staticmethod
    def _invalid_sample(
        pair_id: str, sample_no: int, reason: str
    ) -> PairwiseSampleResult:
        return PairwiseSampleResult(
            pair_id=pair_id,
            sample_no=sample_no,
            judgment_1_winner_id=None,
            judgment_2_winner_id=None,
            stable=False,
            stable_winner_id=None,
            invalid=True,
            reason=reason,
        )

    @classmethod
    def _parse_response(cls, raw_response: str, activated_casel: list[str]) -> dict:
        data = json.loads(_extract_json(raw_response))
        winner = str(data.get("winner", "")).strip()
        if winner == "难分":
            winner = "tie"
        if winner not in COMPARISON_VALUES:
            raise ValueError("winner must be A, B, tie, or 难分")
        data["winner"] = winner

        active_dimensions = cls._active_casel_dimensions(activated_casel)
        data["epitome_comparison"] = cls._normalize_comparison_map(
            data.get("epitome_comparison"),
            EPITOME_COMPARISON_KEYS,
            "epitome_comparison",
            required=True,
        )
        data["casel_comparisons"] = cls._normalize_comparison_map(
            data.get("casel_comparisons"),
            active_dimensions,
            "casel_comparisons",
            required=bool(active_dimensions),
        )
        return data

    @staticmethod
    def _map_display_winner(
        winner: str,
        first: PairwiseCandidate,
        second: PairwiseCandidate,
    ) -> str | None:
        if winner == "A":
            return first.candidate_id
        if winner == "B":
            return second.candidate_id
        return None

    @staticmethod
    def _map_comparison_values(
        comparison: dict[str, str],
        first: PairwiseCandidate,
        second: PairwiseCandidate,
    ) -> dict[str, str]:
        mapped = {}
        for key, value in comparison.items():
            if value == "A":
                mapped[key] = first.candidate_id
            elif value == "B":
                mapped[key] = second.candidate_id
            else:
                mapped[key] = "tie"
        return mapped

    @staticmethod
    def _active_casel_dimensions(activated_casel: list[str]) -> list[str]:
        return [dimension for dimension in activated_casel if dimension in CASEL_RUBRIC]

    @staticmethod
    def _normalize_comparison_map(
        raw_value,
        expected_keys,
        field_name: str,
        required: bool,
    ) -> dict[str, str]:
        if raw_value is None and not required:
            raw_value = {}
        if not isinstance(raw_value, dict):
            raise ValueError(f"{field_name} must be an object")

        expected = list(expected_keys)
        raw_keys = {str(key) for key in raw_value}
        missing = [key for key in expected if key not in raw_keys]
        extra = sorted(raw_keys - set(expected))
        if required and missing:
            raise ValueError(f"{field_name} missing keys: {', '.join(missing)}")
        if extra:
            raise ValueError(f"{field_name} has unexpected keys: {', '.join(extra)}")

        normalized = {}
        for key in expected:
            if key not in raw_value:
                continue
            value = str(raw_value[key]).strip()
            if value == "难分":
                value = "tie"
            if value not in COMPARISON_VALUES:
                raise ValueError(f"{field_name}.{key} must be A, B, or tie")
            normalized[key] = value
        return normalized

    @staticmethod
    def _build_prompt(
        context: PairwiseContext,
        first: PairwiseCandidate,
        second: PairwiseCandidate,
    ) -> str:
        history_text = "\n".join(
            f"{item.role}: {item.text}" for item in context.history
        ) or "无"
        casel_prompt = CriticPairwiseService._build_casel_prompt(
            context.activated_casel
        )
        return f"""你是一个中文情感教育系统的回应质量评估模块，面向中国初中生（12-15岁）。请只比较两条候选回应哪一条更适合作为最终回复。
判断标准按重要性排序：
1. 安全与边界：不得鼓励隐瞒、报复、冲动断关系、事实编造或泄露内部提示。
2. EPITOME：比较 ER（情绪回应）、IP（解释/洞察）、EX（探索/继续表达空间），判断哪条更具体、更贴合当前倾诉。
3. CASEL：如果本轮有 activated_casel，只比较列出的激活维度，作为教育价值的显式辅助比较。
4. 语气：像可信任、稍年长的朋友，而不是居高临下、审问或说教。
只根据回应文本判断，不脑补没写出的内容，不因为更长就认为更好。请忽略回应 A/B 的呈现顺序，只比较两条回应文本本身。

【EPITOME 比较维度】
- ER：是否具体承接孩子的情绪，而不是模板化安慰。
- IP：是否有文本依据地识别孩子没明说的担忧、委屈或需求。
- EX：是否给孩子低压力、可继续表达的空间，而不是审问或成人 coaching。
{casel_prompt}

请输出严格 JSON：{{
  "winner": "A/B/tie",
  "reason": "一句中文理由",
  "epitome_comparison": {{"ER": "A/B/tie", "IP": "A/B/tie", "EX": "A/B/tie"}},
  "casel_comparisons": {{"仅包含 activated_casel 中的维度名": "A/B/tie"}},
  "boundary_concern": true/false,
  "boundary_reason": "若有越界风险则说明，否则为空字符串"
}}

【用户倾诉】{context.user_message}
【对话历史】{history_text}
【回应A】{first.text}
【回应B】{second.text}
"""

    @staticmethod
    def _build_casel_prompt(activated_casel: list[str]) -> str:
        active_lines = [
            f"- {dimension}：{CASEL_RUBRIC[dimension]}"
            for dimension in activated_casel
            if dimension in CASEL_RUBRIC
        ]
        if not active_lines:
            return """
【CASEL 显式比较】
本轮 activated_casel 为空，不做 CASEL 维度比较；casel_comparisons 必须输出为空对象 {}。
"""
        return f"""
【CASEL 显式比较】
本轮只比较以下 activated_casel 维度；不要输出未列出的 CASEL 维度。每个维度只判断 A / B / tie，不输出 0/1/2 分数：
{chr(10).join(active_lines)}
"""


def aggregate_pairwise_samples(
    pair_id: str,
    samples: list[PairwiseSampleResult],
    candidate_ids: list[str],
) -> PairwiseAggregateResult:
    stable_votes = {candidate_id: 0 for candidate_id in candidate_ids}
    invalid_count = sum(1 for sample in samples if sample.invalid)
    unstable_count = sum(
        1 for sample in samples if not sample.invalid and not sample.stable
    )
    for sample in samples:
        if sample.stable and sample.stable_winner_id in stable_votes:
            stable_votes[sample.stable_winner_id] += 1

    if invalid_count:
        return PairwiseAggregateResult(
            pair_id=pair_id,
            pairwise_sample_count=len(samples),
            stable_votes=stable_votes,
            unstable_count=unstable_count,
            invalid_count=invalid_count,
            winner_id=None,
            pairwise_stable=False,
            pairwise_confidence="invalid",
            selection_method="invalid",
        )

    ranked = sorted(stable_votes.items(), key=lambda item: item[1], reverse=True)
    top_id, top_votes = ranked[0]
    runner_up_votes = ranked[1][1] if len(ranked) > 1 else 0
    majority = ceil(len(samples) / 2)

    if top_votes >= majority and top_votes > runner_up_votes:
        if top_votes == len(samples):
            confidence = "unanimous"
        elif runner_up_votes > 0:
            confidence = "split_majority"
        else:
            confidence = "majority_with_unstable"
        return PairwiseAggregateResult(
            pair_id=pair_id,
            pairwise_sample_count=len(samples),
            stable_votes=stable_votes,
            unstable_count=unstable_count,
            invalid_count=invalid_count,
            winner_id=top_id,
            pairwise_stable=True,
            pairwise_confidence=confidence,
            selection_method="pairwise_stable",
        )

    return PairwiseAggregateResult(
        pair_id=pair_id,
        pairwise_sample_count=len(samples),
        stable_votes=stable_votes,
        unstable_count=unstable_count,
        invalid_count=invalid_count,
        winner_id=None,
        pairwise_stable=False,
        pairwise_confidence="unstable",
        selection_method="pointwise_tiebreak",
    )


def _extract_json(raw_response: str) -> str:
    start = raw_response.find("{")
    end = raw_response.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no json object")
    return raw_response[start : end + 1]
