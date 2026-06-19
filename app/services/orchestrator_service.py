import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Protocol

from app.config import Settings
from app.dao.chat_turn_dao import ChatTurnDAO
from app.schemas.chat import ChatRequest, ChatResponse, ChatStatus
from app.schemas.critic import (
    CandidateInput,
    CandidateScore,
    CriticEvaluateRequest,
    CriticGuidanceStatusResponse,
    PreferencePair,
)
from app.schemas.generator import GeneratorCandidate, GeneratorGenerateRequest
from app.schemas.safety import ConversationMessage, SafetyGateRequest, SafetyGateResponse
from app.schemas.scenario import ScenarioAnalyzeRequest, ScenarioLabel
from app.services.critic_service import CriticService
from app.services.generator_service import (
    GeneratorService,
    ORIENTATION_ORDER,
    clean_generator_output,
)
from app.services.history_store import HistoryStoreProtocol
from app.services.scenario_service import ScenarioService


AUDIT_TAGS_RE = re.compile(r"audit_tags=([A-Za-z0-9_,\-]+)")


class SafetyGateProtocol(Protocol):
    async def evaluate(self, request: SafetyGateRequest) -> SafetyGateResponse:
        ...


class OrchestratorService:
    """Runtime orchestrator.

    Product path:
    - first turn: F1 -> F2 -> one F3 answer -> return immediately -> async F4.
    - follow-up turns: lightweight CBT-style one-call generation, with finished F4
      guidance if available. Pending F4 never blocks the student.

    The full generator-critic chain is still available through module endpoints and
    offline experiments; it is no longer the blocking runtime path for every turn.
    """

    def __init__(
        self,
        safety_service: SafetyGateProtocol,
        scenario_service: ScenarioService,
        generator_service: GeneratorService,
        critic_service: CriticService,
        history_store: HistoryStoreProtocol,
        chat_turn_dao: ChatTurnDAO,
        settings: Settings,
    ):
        self.safety_service = safety_service
        self.scenario_service = scenario_service
        self.generator_service = generator_service
        self.critic_service = critic_service
        self.history_store = history_store
        self.chat_turn_dao = chat_turn_dao
        self.settings = settings

    async def chat(self, request: ChatRequest) -> ChatResponse:
        max_messages = self.settings.HISTORY_WINDOW_N * 2
        history = await self.history_store.get_history(request.session_id, max_messages)
        if history:
            return await self._chat_follow_up(request, history, max_messages)
        return await self._chat_first_turn(request, history, max_messages)

    async def stream_chat(self, request: ChatRequest):
        max_messages = self.settings.HISTORY_WINDOW_N * 2
        history = await self.history_store.get_history(request.session_id, max_messages)
        if history:
            async for event in self._stream_follow_up(request, history, max_messages):
                yield event
            return
        async for event in self._stream_first_turn(request, history, max_messages):
            yield event

    async def _stream_first_turn(
        self,
        request: ChatRequest,
        history: list[ConversationMessage],
        max_messages: int,
    ):
        try:
            safety = await self.safety_service.evaluate(
                SafetyGateRequest(
                    session_id=request.session_id,
                    current_message=request.current_message,
                    history=history,
                )
            )
        except Exception as exc:
            response = await self._module_failed(
                request=request,
                failed_module="safety",
                exc=exc,
                risk_level="yellow",
                history_window=max_messages,
            )
            async for event in self._buffered_response_events(response):
                yield event
            return

        if safety.action.block_generation:
            response = await self._finalize(
                request=request,
                status="blocked_by_safety",
                reply_text=safety.action.referral_message
                or self.settings.CHAT_FALLBACK_MESSAGE,
                risk_level=safety.risk_level,
                scenario=None,
                activated_casel=[],
                candidates=[],
                scores=[],
                best_candidate_id=None,
                preference_pair=None,
                support_mode=None,
                emotion_intensity=None,
                help_seeking=None,
                selected_by=None,
                failed_module=None,
                failure_reason="",
                fallback_message="",
                history_window=max_messages,
            )
            async for event in self._buffered_response_events(response):
                yield event
            return

        try:
            scenario = await self.scenario_service.analyze(
                ScenarioAnalyzeRequest(
                    session_id=request.session_id,
                    current_message=request.current_message,
                    history=history,
                )
            )
        except Exception as exc:
            response = await self._module_failed(
                request=request,
                failed_module="scenario",
                exc=exc,
                risk_level=safety.risk_level,
                history_window=max_messages,
            )
            async for event in self._buffered_response_events(response):
                yield event
            return

        if scenario.secondary_safety.action.block_generation:
            response = await self._finalize(
                request=request,
                status="blocked_by_safety",
                reply_text=scenario.secondary_safety.action.referral_message
                or self.settings.CHAT_FALLBACK_MESSAGE,
                risk_level=scenario.secondary_safety.risk_level,
                scenario=scenario.scenario,
                activated_casel=scenario.activated_casel,
                candidates=[],
                scores=[],
                best_candidate_id=None,
                preference_pair=None,
                support_mode=scenario.support_mode,
                emotion_intensity=scenario.emotion_intensity,
                help_seeking=scenario.help_seeking,
                selected_by=None,
                failed_module=None,
                failure_reason="",
                fallback_message="",
                history_window=max_messages,
            )
            async for event in self._buffered_response_events(response):
                yield event
            return

        candidate_id = self._first_turn_candidate_id(
            scenario.support_mode,
            scenario.emotion_intensity,
        )
        pending = ChatResponse(
            session_id=request.session_id,
            anonymous_user_id=request.anonymous_user_id,
            status="answered",
            reply_text="",
            risk_level=safety.risk_level,
            scenario=scenario.scenario,
            support_mode=scenario.support_mode,
            emotion_intensity=scenario.emotion_intensity,
            help_seeking=scenario.help_seeking,
            selected_by="fast_first_turn_stream",
            activated_casel=scenario.activated_casel,
            best_candidate_id=candidate_id,
            candidates=[],
            scores=[],
            preference_pair=None,
        )
        yield ("metadata", pending.model_dump(exclude={"reply_text"}))

        generator_request = GeneratorGenerateRequest(
            session_id=request.session_id,
            user_message=request.current_message,
            history=history,
            scenario=scenario.scenario,
            support_mode=scenario.support_mode,
            emotion_intensity=scenario.emotion_intensity,
            help_seeking=scenario.help_seeking,
            dialogue_stage="first_contact",
            rag_examples=[],
        )
        chunks: list[str] = []
        async for chunk in self.generator_service.stream_one_text(
            generator_request, candidate_id=candidate_id
        ):
            chunks.append(chunk)
            yield ("delta", {"text": chunk})
        reply_text = clean_generator_output("".join(chunks))
        if not reply_text:
            reply_text = self.settings.CHAT_FALLBACK_MESSAGE
        selected = GeneratorCandidate(
            candidate_id=candidate_id,
            orientation=self._candidate_orientation(candidate_id),
            text=reply_text,
        )
        response = await self._finalize(
            request=request,
            status="answered",
            reply_text=selected.text,
            risk_level=safety.risk_level,
            scenario=scenario.scenario,
            activated_casel=scenario.activated_casel,
            candidates=[selected],
            scores=[],
            best_candidate_id=selected.candidate_id,
            preference_pair=None,
            support_mode=scenario.support_mode,
            emotion_intensity=scenario.emotion_intensity,
            help_seeking=scenario.help_seeking,
            selected_by="fast_first_turn_stream",
            failed_module=None,
            failure_reason="",
            fallback_message="",
            history_window=max_messages,
        )
        self._schedule_background_critic(
            session_id=request.session_id,
            user_message=request.current_message,
            history=history,
            activated_casel=scenario.activated_casel,
            candidates=[selected],
        )
        yield ("done", response.model_dump())

    async def _stream_follow_up(
        self,
        request: ChatRequest,
        history: list[ConversationMessage],
        max_messages: int,
    ):
        try:
            safety = await self.safety_service.evaluate(
                SafetyGateRequest(
                    session_id=request.session_id,
                    current_message=request.current_message,
                    history=history,
                )
            )
        except Exception as exc:
            response = await self._module_failed(
                request=request,
                failed_module="safety",
                exc=exc,
                risk_level="yellow",
                history_window=max_messages,
            )
            async for event in self._buffered_response_events(response):
                yield event
            return

        if safety.action.block_generation:
            response = await self._finalize(
                request=request,
                status="blocked_by_safety",
                reply_text=safety.action.referral_message
                or self.settings.CHAT_FALLBACK_MESSAGE,
                risk_level=safety.risk_level,
                scenario=None,
                activated_casel=[],
                candidates=[],
                scores=[],
                best_candidate_id=None,
                preference_pair=None,
                support_mode=None,
                emotion_intensity=None,
                help_seeking=None,
                selected_by=None,
                failed_module=None,
                failure_reason="",
                fallback_message="",
                history_window=max_messages,
            )
            async for event in self._buffered_response_events(response):
                yield event
            return

        guidance = await self._load_f4_guidance(request.session_id)
        selected_by = (
            "fast_cbt_followup_stream_with_f4_guidance"
            if guidance
            else "fast_cbt_followup_stream"
        )
        pending = ChatResponse(
            session_id=request.session_id,
            anonymous_user_id=request.anonymous_user_id,
            status="answered",
            reply_text="",
            risk_level=safety.risk_level,
            scenario=None,
            support_mode=None,
            emotion_intensity=None,
            help_seeking=None,
            selected_by=selected_by,
            activated_casel=[],
            best_candidate_id="cbt",
            candidates=[],
            scores=[],
            preference_pair=None,
        )
        yield ("metadata", pending.model_dump(exclude={"reply_text"}))

        chunks: list[str] = []
        async for chunk in self.generator_service.stream_followup_text(
            user_message=request.current_message,
            history=history,
            f4_guidance=guidance,
        ):
            chunks.append(chunk)
            yield ("delta", {"text": chunk})
        reply_text = clean_generator_output("".join(chunks))
        if not reply_text:
            reply_text = self.settings.CHAT_FALLBACK_MESSAGE
        selected = GeneratorCandidate(
            candidate_id="cbt",
            orientation=self._candidate_orientation("c2"),
            text=reply_text,
        )
        response = await self._finalize(
            request=request,
            status="answered",
            reply_text=selected.text,
            risk_level=safety.risk_level,
            scenario=None,
            activated_casel=[],
            candidates=[selected],
            scores=[],
            best_candidate_id=selected.candidate_id,
            preference_pair=None,
            support_mode=None,
            emotion_intensity=None,
            help_seeking=None,
            selected_by=selected_by,
            failed_module=None,
            failure_reason="",
            fallback_message="",
            history_window=max_messages,
        )
        yield ("done", response.model_dump())

    async def _buffered_response_events(self, response: ChatResponse):
        yield ("metadata", response.model_dump(exclude={"reply_text"}))
        chunk_size = self.settings.CHAT_STREAM_CHUNK_SIZE
        safe_size = max(chunk_size, 1)
        for index in range(0, len(response.reply_text), safe_size):
            yield ("delta", {"text": response.reply_text[index : index + safe_size]})
            await asyncio.sleep(0)
        yield ("done", response.model_dump())

    async def _chat_first_turn(
        self,
        request: ChatRequest,
        history: list[ConversationMessage],
        max_messages: int,
    ) -> ChatResponse:
        try:
            safety = await self.safety_service.evaluate(
                SafetyGateRequest(
                    session_id=request.session_id,
                    current_message=request.current_message,
                    history=history,
                )
            )
        except Exception as exc:
            return await self._module_failed(
                request=request,
                failed_module="safety",
                exc=exc,
                risk_level="yellow",
                history_window=max_messages,
            )

        if safety.action.block_generation:
            reply_text = safety.action.referral_message or self.settings.CHAT_FALLBACK_MESSAGE
            return await self._finalize(
                request=request,
                status="blocked_by_safety",
                reply_text=reply_text,
                risk_level=safety.risk_level,
                scenario=None,
                activated_casel=[],
                candidates=[],
                scores=[],
                best_candidate_id=None,
                preference_pair=None,
                support_mode=None,
                emotion_intensity=None,
                help_seeking=None,
                selected_by=None,
                failed_module=None,
                failure_reason="",
                fallback_message="",
                history_window=max_messages,
            )

        try:
            scenario = await self.scenario_service.analyze(
                ScenarioAnalyzeRequest(
                    session_id=request.session_id,
                    current_message=request.current_message,
                    history=history,
                )
            )
        except Exception as exc:
            return await self._module_failed(
                request=request,
                failed_module="scenario",
                exc=exc,
                risk_level=safety.risk_level,
                history_window=max_messages,
            )

        if scenario.secondary_safety.action.block_generation:
            reply_text = (
                scenario.secondary_safety.action.referral_message
                or self.settings.CHAT_FALLBACK_MESSAGE
            )
            return await self._finalize(
                request=request,
                status="blocked_by_safety",
                reply_text=reply_text,
                risk_level=scenario.secondary_safety.risk_level,
                scenario=scenario.scenario,
                activated_casel=scenario.activated_casel,
                candidates=[],
                scores=[],
                best_candidate_id=None,
                preference_pair=None,
                support_mode=scenario.support_mode,
                emotion_intensity=scenario.emotion_intensity,
                help_seeking=scenario.help_seeking,
                selected_by=None,
                failed_module=None,
                failure_reason="",
                fallback_message="",
                history_window=max_messages,
            )

        generator_request = GeneratorGenerateRequest(
            session_id=request.session_id,
            user_message=request.current_message,
            history=history,
            scenario=scenario.scenario,
            support_mode=scenario.support_mode,
            emotion_intensity=scenario.emotion_intensity,
            help_seeking=scenario.help_seeking,
            dialogue_stage="first_contact",
            rag_examples=[],
        )
        candidate_id = self._first_turn_candidate_id(
            scenario.support_mode,
            scenario.emotion_intensity,
        )

        try:
            selected = await self.generator_service.generate_one(
                generator_request, candidate_id=candidate_id
            )
        except Exception as exc:
            return await self._module_failed(
                request=request,
                failed_module="generator",
                exc=exc,
                risk_level=safety.risk_level,
                scenario=scenario.scenario,
                activated_casel=scenario.activated_casel,
                support_mode=scenario.support_mode,
                emotion_intensity=scenario.emotion_intensity,
                help_seeking=scenario.help_seeking,
                history_window=max_messages,
            )

        response = await self._finalize(
            request=request,
            status="answered",
            reply_text=selected.text,
            risk_level=safety.risk_level,
            scenario=scenario.scenario,
            activated_casel=scenario.activated_casel,
            candidates=[selected],
            scores=[],
            best_candidate_id=selected.candidate_id,
            preference_pair=None,
            support_mode=scenario.support_mode,
            emotion_intensity=scenario.emotion_intensity,
            help_seeking=scenario.help_seeking,
            selected_by="fast_first_turn",
            failed_module=None,
            failure_reason="",
            fallback_message="",
            history_window=max_messages,
        )
        self._schedule_background_critic(
            session_id=request.session_id,
            user_message=request.current_message,
            history=history,
            activated_casel=scenario.activated_casel,
            candidates=[selected],
        )
        return response

    async def _chat_follow_up(
        self,
        request: ChatRequest,
        history: list[ConversationMessage],
        max_messages: int,
    ) -> ChatResponse:
        try:
            safety = await self.safety_service.evaluate(
                SafetyGateRequest(
                    session_id=request.session_id,
                    current_message=request.current_message,
                    history=history,
                )
            )
        except Exception as exc:
            return await self._module_failed(
                request=request,
                failed_module="safety",
                exc=exc,
                risk_level="yellow",
                history_window=max_messages,
            )

        if safety.action.block_generation:
            return await self._finalize(
                request=request,
                status="blocked_by_safety",
                reply_text=safety.action.referral_message
                or self.settings.CHAT_FALLBACK_MESSAGE,
                risk_level=safety.risk_level,
                scenario=None,
                activated_casel=[],
                candidates=[],
                scores=[],
                best_candidate_id=None,
                preference_pair=None,
                support_mode=None,
                emotion_intensity=None,
                help_seeking=None,
                selected_by=None,
                failed_module=None,
                failure_reason="",
                fallback_message="",
                history_window=max_messages,
            )

        guidance = await self._load_f4_guidance(request.session_id)
        try:
            selected = await self.generator_service.generate_followup(
                session_id=request.session_id,
                user_message=request.current_message,
                history=history,
                f4_guidance=guidance,
            )
        except Exception as exc:
            return await self._module_failed(
                request=request,
                failed_module="followup_generator",
                exc=exc,
                risk_level=safety.risk_level,
                history_window=max_messages,
            )

        return await self._finalize(
            request=request,
            status="answered",
            reply_text=selected.text,
            risk_level=safety.risk_level,
            scenario=None,
            activated_casel=[],
            candidates=[selected],
            scores=[],
            best_candidate_id=selected.candidate_id,
            preference_pair=None,
            support_mode=None,
            emotion_intensity=None,
            help_seeking=None,
            selected_by="fast_cbt_followup_with_f4_guidance"
            if guidance
            else "fast_cbt_followup",
            failed_module=None,
            failure_reason="",
            fallback_message="",
            history_window=max_messages,
        )

    async def _module_failed(
        self,
        request: ChatRequest,
        failed_module: str,
        exc: Exception,
        risk_level: str,
        history_window: int,
        scenario: ScenarioLabel | None = None,
        activated_casel: list[str] | None = None,
        candidates: list[GeneratorCandidate] | None = None,
        support_mode: str | None = None,
        emotion_intensity: str | None = None,
        help_seeking: bool | None = None,
    ) -> ChatResponse:
        fallback_message = self.settings.CHAT_FALLBACK_MESSAGE
        return await self._finalize(
            request=request,
            status="module_failed",
            reply_text=fallback_message,
            risk_level=risk_level,
            scenario=scenario,
            activated_casel=activated_casel or [],
            candidates=candidates or [],
            scores=[],
            best_candidate_id=None,
            preference_pair=None,
            support_mode=support_mode,
            emotion_intensity=emotion_intensity,
            help_seeking=help_seeking,
            selected_by=None,
            failed_module=failed_module,
            failure_reason=str(exc),
            fallback_message=fallback_message,
            history_window=history_window,
        )

    async def _finalize(
        self,
        request: ChatRequest,
        status: ChatStatus,
        reply_text: str,
        risk_level: str,
        scenario: ScenarioLabel | None,
        activated_casel: list[str],
        candidates: list[GeneratorCandidate],
        scores: list[CandidateScore],
        best_candidate_id: str | None,
        preference_pair: PreferencePair | None,
        support_mode: str | None,
        emotion_intensity: str | None,
        help_seeking: bool | None,
        selected_by: str | None,
        failed_module: str | None,
        failure_reason: str,
        fallback_message: str,
        history_window: int,
    ) -> ChatResponse:
        await self.chat_turn_dao.create_turn(
            session_id=request.session_id,
            user_message=request.current_message,
            assistant_message=reply_text,
            status=status,
            risk_level=risk_level,
            scenario=scenario,
            activated_casel=activated_casel,
            candidates=candidates,
            scores=scores,
            best_candidate_id=best_candidate_id,
            preference_pair=preference_pair,
            failed_module=failed_module,
            failure_reason=failure_reason,
            fallback_message=fallback_message,
        )
        await self.history_store.append_messages(
            request.session_id,
            [
                ConversationMessage(role="student", text=request.current_message),
                ConversationMessage(role="assistant", text=reply_text),
            ],
            history_window,
        )
        return ChatResponse(
            session_id=request.session_id,
            anonymous_user_id=request.anonymous_user_id,
            status=status,
            reply_text=reply_text,
            risk_level=risk_level,
            scenario=scenario,
            support_mode=support_mode,
            emotion_intensity=emotion_intensity,
            help_seeking=help_seeking,
            selected_by=selected_by,
            activated_casel=activated_casel,
            best_candidate_id=best_candidate_id,
            candidates=candidates,
            scores=scores,
            preference_pair=preference_pair,
            failed_module=failed_module,
            failure_reason=failure_reason,
        )

    def _schedule_background_critic(
        self,
        *,
        session_id: str,
        user_message: str,
        history: list[ConversationMessage],
        activated_casel: list[str],
        candidates: list[GeneratorCandidate],
    ) -> None:
        task = self._run_background_critic(
            session_id=session_id,
            user_message=user_message,
            history=history,
            activated_casel=activated_casel,
            candidates=candidates,
        )
        try:
            asyncio.create_task(task)
        except RuntimeError:
            pass

    async def _run_background_critic(
        self,
        *,
        session_id: str,
        user_message: str,
        history: list[ConversationMessage],
        activated_casel: list[str],
        candidates: list[GeneratorCandidate],
    ) -> None:
        await self._save_f4_guidance(
            session_id,
            {
                "status": "pending",
                "guidance": "",
                "source": "f4_background",
            },
        )
        try:
            critic = await self.critic_service.evaluate(
                CriticEvaluateRequest(
                    session_id=session_id,
                    user_message=user_message,
                    history=history,
                    activated_casel=activated_casel,
                    candidates=[
                        CandidateInput(
                            candidate_id=candidate.candidate_id,
                            orientation=candidate.orientation,
                            text=candidate.text,
                        )
                        for candidate in candidates
                    ],
                )
            )
            await self._save_f4_guidance(
                session_id,
                {
                    "status": "ready",
                    "guidance": self._guidance_from_scores(critic.scores),
                    "best_candidate_id": critic.best_candidate_id,
                    "scores": [score.model_dump() for score in critic.scores],
                    "source": "f4_background",
                },
            )
        except Exception as exc:
            await self._save_f4_guidance(
                session_id,
                {
                    "status": "failed",
                    "guidance": "",
                    "error": str(exc),
                    "source": "f4_background",
                },
            )

    async def _load_f4_guidance(self, session_id: str) -> str:
        redis = getattr(self.history_store, "redis", None)
        if redis is None:
            return ""
        raw = await redis.get(self._guidance_key(session_id))
        if not raw:
            return ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return ""
        if payload.get("status") != "ready":
            return ""
        return str(payload.get("guidance") or "").strip()

    async def get_f4_guidance_status(
        self, session_id: str
    ) -> CriticGuidanceStatusResponse:
        redis = getattr(self.history_store, "redis", None)
        if redis is None:
            return CriticGuidanceStatusResponse(
                session_id=session_id,
                status="missing",
            )
        raw = await redis.get(self._guidance_key(session_id))
        if not raw:
            return CriticGuidanceStatusResponse(
                session_id=session_id,
                status="missing",
            )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return CriticGuidanceStatusResponse(
                session_id=session_id,
                status="failed",
                error="invalid guidance payload",
            )

        status = str(payload.get("status") or "missing").lower()
        if status not in {"pending", "ready", "failed"}:
            status = "missing"
        guidance = (
            str(payload.get("guidance") or "").strip()
            if status == "ready"
            else ""
        )
        error = str(payload.get("error") or "").strip() if status == "failed" else ""
        updated_at = str(payload.get("updated_at") or "").strip() or None
        return CriticGuidanceStatusResponse(
            session_id=session_id,
            status=status,
            guidance=guidance,
            error=error,
            updated_at=updated_at,
        )

    async def _save_f4_guidance(self, session_id: str, payload: dict[str, Any]) -> None:
        redis = getattr(self.history_store, "redis", None)
        if redis is None:
            return
        payload = dict(payload)
        payload.setdefault("updated_at", self._utc_now())
        await redis.set(
            self._guidance_key(session_id),
            json.dumps(payload, ensure_ascii=False),
            ex=self.settings.CHAT_HISTORY_TTL_SECONDS,
        )

    @staticmethod
    def _guidance_key(session_id: str) -> str:
        return f"emoedu:f4_guidance:{session_id}"

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _first_turn_candidate_id(support_mode: str, emotion_intensity: str) -> str:
        if support_mode == "emotion_first" or emotion_intensity == "high":
            return "c1"
        return "c2"

    @staticmethod
    def _guidance_from_scores(scores: list[CandidateScore]) -> str:
        if not scores:
            return ""
        score = scores[0]
        guidance: list[str] = []
        if score.boundary_flag:
            guidance.append(
                "Last reply had a boundary concern; keep the next reply safer, shorter, "
                "and avoid adding facts or giving strong advice."
            )
        if score.epitome.ER < 2:
            guidance.append(
                "Use a more concrete emotional acknowledgment before moving forward."
            )
        if score.epitome.IP < 2:
            guidance.append(
                "Name the student's specific stuck point instead of using generic comfort."
            )
        if score.epitome.EX < 1:
            guidance.append(
                "For follow-up, offer one low-pressure next step or one very easy way to continue."
            )
        audit_tags = OrchestratorService._audit_tags(score.rationale)
        if "unsupported_fact_completion" in audit_tags:
            guidance.append("Do not infer details the student did not say.")
        if "adult_coaching_question" in audit_tags:
            guidance.append("Avoid adult-like coaching questions and broad rhetorical questions.")
        if "template_low_information" in audit_tags:
            guidance.append("Avoid template reassurance; respond to the exact scene.")
        return " ".join(guidance[:4])

    @staticmethod
    def _audit_tags(rationale: str) -> list[str]:
        match = AUDIT_TAGS_RE.search(rationale or "")
        if match is None:
            return []
        return [tag for tag in match.group(1).split(",") if tag]

    @staticmethod
    def _candidate_orientation(candidate_id: str):
        for item_id, orientation in ORIENTATION_ORDER:
            if item_id == candidate_id:
                return orientation
        return ORIENTATION_ORDER[-1][1]
