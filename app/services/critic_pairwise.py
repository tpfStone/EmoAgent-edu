import json
from dataclasses import dataclass, field
from math import ceil

from app.config import Settings
from app.schemas.safety import ConversationMessage
from app.services.llm_client import LLMClientProtocol


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


@dataclass(frozen=True)
class PairwiseOrderResult:
    displayed_first_id: str
    displayed_second_id: str
    raw_winner: str
    winner_id: str | None
    reason: str
    boundary_concern: bool
    boundary_reason: str
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

        stable = (
            first.winner_id is not None
            and first.winner_id == second.winner_id
        )
        return PairwiseSampleResult(
            pair_id=context.pair_id,
            sample_no=sample_no,
            judgment_1_winner_id=first.winner_id,
            judgment_2_winner_id=second.winner_id,
            stable=stable,
            stable_winner_id=first.winner_id if stable else None,
            invalid=False,
            reason=first.reason or second.reason,
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
            data = self._parse_response(raw_response)
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

    @staticmethod
    def _parse_response(raw_response: str) -> dict:
        data = json.loads(_extract_json(raw_response))
        winner = str(data.get("winner", "")).strip()
        if winner not in {"A", "B", "tie", "难分"}:
            raise ValueError("winner must be A, B, tie, or 难分")
        data["winner"] = winner
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
    def _build_prompt(
        context: PairwiseContext,
        first: PairwiseCandidate,
        second: PairwiseCandidate,
    ) -> str:
        history_text = "\n".join(
            f"{item.role}: {item.text}" for item in context.history
        ) or "无"
        return f"""你是一个中文情感教育系统的回应质量评估模块，面向中国初中生（12-15岁）。请只比较两条候选回应哪一条更适合作为最终回复。

判断标准按重要性排序：
1. 是否让孩子真正感到被具体地看见，而不是泛泛安慰。
2. 是否准确接住孩子没明说、但藏在话里的情绪或担忧。
3. 是否不审问、不说教、不替别人开脱，同时给孩子一点继续表达的空间。
4. 语气是否像可信任、稍年长的朋友，而不是居高临下。

只根据回应文本判断，不脑补没写出的内容，不因为更长就认为更好。

请输出严格 JSON：
{{
  "winner": "A/B/tie",
  "reason": "一句中文理由",
  "boundary_concern": true/false,
  "boundary_reason": "若有越界风险则说明，否则为空字符串"
}}

【用户倾诉】{context.user_message}
【对话历史】{history_text}
【回应A】({first.candidate_id}, {first.orientation}) {first.text}
【回应B】({second.candidate_id}, {second.orientation}) {second.text}
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
