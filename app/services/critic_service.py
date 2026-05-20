import json
from statistics import median

from app.config import Settings
from app.schemas.critic import (
    CandidateInput,
    CandidateScore,
    CriticEvaluateRequest,
    CriticEvaluateResponse,
    EpitomeScore,
    PreferencePair,
)
from app.services.llm_client import LLMClientProtocol


CRITIC_FALLBACK_MESSAGE = "所有候选回应均未通过边界检查，请转人工复核。"


class CriticService:
    def __init__(
        self,
        llm_client: LLMClientProtocol,
        critic_run_dao,
        settings: Settings,
    ):
        self.llm_client = llm_client
        self.critic_run_dao = critic_run_dao
        self.settings = settings

    async def evaluate(self, request: CriticEvaluateRequest) -> CriticEvaluateResponse:
        scores = [
            await self._score_candidate(request, candidate)
            for candidate in request.candidates
        ]
        valid_scores = [score for score in scores if not score.boundary_flag]

        best_candidate_id: str | None = None
        fallback_message = ""
        if valid_scores:
            best_score = max(valid_scores, key=lambda score: score.weighted_total)
            best_candidate_id = best_score.candidate_id
        else:
            fallback_message = CRITIC_FALLBACK_MESSAGE

        preference_pair = self._build_preference_pair(valid_scores)
        response = CriticEvaluateResponse(
            best_candidate_id=best_candidate_id,
            scores=scores,
            preference_pair=preference_pair,
            fallback_message=fallback_message,
        )
        if self.critic_run_dao is not None:
            await self.critic_run_dao.create_run(
                session_id=request.session_id,
                user_message=request.user_message,
                history=[item.model_dump() for item in request.history],
                activated_casel=request.activated_casel,
                candidates=[candidate.model_dump() for candidate in request.candidates],
                scores=[score.model_dump() for score in scores],
                best_candidate_id=best_candidate_id,
                preference_pair=(
                    preference_pair.model_dump() if preference_pair is not None else None
                ),
                fallback_message=fallback_message,
            )
        return response

    async def _score_candidate(
        self, request: CriticEvaluateRequest, candidate: CandidateInput
    ) -> CandidateScore:
        samples = []
        for _ in range(self.settings.CRITIC_SAMPLE_COUNT):
            samples.append(await self._score_once(request, candidate))

        er = int(median(sample["ER"] for sample in samples))
        ip = int(median(sample["IP"] for sample in samples))
        ex = int(median(sample["EX"] for sample in samples))
        boundary_samples = [sample for sample in samples if sample["boundary_flag"]]
        boundary_flag = bool(boundary_samples)
        boundary_reason = (
            str(boundary_samples[0]["boundary_reason"]) if boundary_samples else ""
        )
        rationale = str(samples[0].get("rationale", ""))
        weighted_total = float(er + ip + ex)

        return CandidateScore(
            candidate_id=candidate.candidate_id,
            epitome=EpitomeScore(ER=er, IP=ip, EX=ex),
            casel={},
            boundary_flag=boundary_flag,
            boundary_reason=boundary_reason,
            weighted_total=weighted_total,
            rationale=rationale,
        )

    async def _score_once(
        self, request: CriticEvaluateRequest, candidate: CandidateInput
    ) -> dict:
        try:
            raw_response = await self.llm_client.generate(
                prompt=self._build_prompt(request, candidate),
                timeout=self.settings.LLM_TIMEOUT,
                temperature=self.settings.CRITIC_LLM_TEMPERATURE,
                max_tokens=self.settings.LLM_MAX_TOKENS,
            )
            return self._parse_score(raw_response)
        except ValueError:
            return self._failed_score("llm_parse_failure")
        except Exception:
            return self._failed_score("llm_failure")

    def _build_prompt(
        self, request: CriticEvaluateRequest, candidate: CandidateInput
    ) -> str:
        history_text = "\n".join(f"{item.role}: {item.text}" for item in request.history)
        return f"""你是一个情感教育系统的回应质量评估模块，面向中国初中生（12–15岁）。给定用户的倾诉和一条候选回应，你要按 EPITOME 框架为这条回应打分。你不改写回应，只打分。

【EPITOME 三个维度，每维打 0 / 1 / 2】
- ER 情绪反应：回应是否表达了温暖、关切、同情。0=冷漠无关切；1=礼貌但泛泛（如"别难过"）；2=具体真诚地表达关切，让对方感到被在乎。
- IP 解释：回应是否传达"理解了对方的处境和感受"。0=误解或答非所问；1=只复述表面；2=准确点出对方没明说的情绪或担忧。
- EX 探索：回应是否邀请对方进一步表达。0=关闭对话或转移；1=没有主动探索；2=用开放式问题温和引导对方多说（对初中生要温和，不要像审问）。

【打分原则】
1. 只根据回应文本打分，不脑补回应里没有的内容。
2. 不要因为回应更长就给更高分。
3. 三个维度各自独立打分。
4. 同时检查：回应是否包含不适合初中生的内容、是否有事实编造、是否越界（如替代专业心理治疗、鼓励隐瞒家长老师）。若有，单独标记。

请输出严格 JSON：
{{
  "ER": 0/1/2, "IP": 0/1/2, "EX": 0/1/2,
  "boundary_flag": true/false,
  "boundary_reason": "若flag为true，说明原因；否则空字符串",
  "rationale": "一句话中文理由"
}}

【用户倾诉】{request.user_message}
【对话历史】{history_text}
【候选回应】{candidate.text}
"""

    def _parse_score(self, raw_response: str) -> dict:
        data = json.loads(self._extract_json(raw_response))
        return {
            "ER": self._score_value(data.get("ER")),
            "IP": self._score_value(data.get("IP")),
            "EX": self._score_value(data.get("EX")),
            "boundary_flag": bool(data.get("boundary_flag", False)),
            "boundary_reason": str(data.get("boundary_reason", "")),
            "rationale": str(data.get("rationale", "")),
        }

    @staticmethod
    def _extract_json(raw_response: str) -> str:
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("no json object")
        return raw_response[start : end + 1]

    @staticmethod
    def _score_value(value) -> int:
        score = int(value)
        if score < 0 or score > 2:
            raise ValueError("score out of range")
        return score

    @staticmethod
    def _failed_score(reason: str) -> dict:
        return {
            "ER": 0,
            "IP": 0,
            "EX": 0,
            "boundary_flag": True,
            "boundary_reason": reason,
            "rationale": reason,
        }

    @staticmethod
    def _build_preference_pair(
        valid_scores: list[CandidateScore],
    ) -> PreferencePair | None:
        if len(valid_scores) < 2:
            return None
        ranked = sorted(
            valid_scores,
            key=lambda score: score.weighted_total,
            reverse=True,
        )
        if ranked[0].weighted_total == ranked[1].weighted_total:
            return None
        return PreferencePair(
            winner_id=ranked[0].candidate_id,
            loser_id=ranked[1].candidate_id,
        )
