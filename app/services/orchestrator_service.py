from app.config import Settings
from app.dao.chat_turn_dao import ChatTurnDAO
from app.schemas.chat import ChatRequest, ChatResponse, ChatStatus
from app.schemas.critic import (
    CandidateInput,
    CandidateScore,
    CriticEvaluateRequest,
    PreferencePair,
)
from app.schemas.generator import (
    GeneratorCandidate,
    GeneratorGenerateRequest,
)
from app.schemas.safety import ConversationMessage, SafetyGateRequest
from app.schemas.scenario import ScenarioAnalyzeRequest, ScenarioLabel
from app.services.critic_service import CriticService
from app.services.generator_service import GeneratorService
from app.services.history_store import HistoryStoreProtocol
from app.services.safety_gate_service import SafetyGateService
from app.services.scenario_service import ScenarioService


class OrchestratorService:
    def __init__(
        self,
        safety_service: SafetyGateService,
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

        try:
            generated = await self.generator_service.generate(
                GeneratorGenerateRequest(
                    session_id=request.session_id,
                    user_message=request.current_message,
                    history=history,
                    scenario=scenario.scenario,
                    rag_examples=[],
                )
            )
        except Exception as exc:
            return await self._module_failed(
                request=request,
                failed_module="generator",
                exc=exc,
                risk_level=safety.risk_level,
                scenario=scenario.scenario,
                activated_casel=scenario.activated_casel,
                history_window=max_messages,
            )

        try:
            critic = await self.critic_service.evaluate(
                CriticEvaluateRequest(
                    session_id=request.session_id,
                    user_message=request.current_message,
                    history=history,
                    activated_casel=scenario.activated_casel,
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
            if critic.best_candidate_id is None:
                reply_text = critic.fallback_message or self.settings.CHAT_FALLBACK_MESSAGE
                return await self._finalize(
                    request=request,
                    status="all_candidates_blocked",
                    reply_text=reply_text,
                    risk_level=safety.risk_level,
                    scenario=scenario.scenario,
                    activated_casel=scenario.activated_casel,
                    candidates=generated.candidates,
                    scores=critic.scores,
                    best_candidate_id=None,
                    preference_pair=critic.preference_pair,
                    failed_module=None,
                    failure_reason="",
                    fallback_message=reply_text,
                    history_window=max_messages,
                )

            selected = self._candidate_by_id(
                generated.candidates, critic.best_candidate_id
            )
            if selected is None:
                raise RuntimeError(
                    f"critic selected unknown candidate: {critic.best_candidate_id}"
                )
        except Exception as exc:
            return await self._module_failed(
                request=request,
                failed_module="critic",
                exc=exc,
                risk_level=safety.risk_level,
                scenario=scenario.scenario,
                activated_casel=scenario.activated_casel,
                candidates=generated.candidates,
                history_window=max_messages,
            )

        return await self._finalize(
            request=request,
            status="answered",
            reply_text=selected.text,
            risk_level=safety.risk_level,
            scenario=scenario.scenario,
            activated_casel=scenario.activated_casel,
            candidates=generated.candidates,
            scores=critic.scores,
            best_candidate_id=critic.best_candidate_id,
            preference_pair=critic.preference_pair,
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
            status=status,
            reply_text=reply_text,
            risk_level=risk_level,
            scenario=scenario,
            activated_casel=activated_casel,
            best_candidate_id=best_candidate_id,
            candidates=candidates,
            scores=scores,
            preference_pair=preference_pair,
            failed_module=failed_module,
            failure_reason=failure_reason,
        )

    @staticmethod
    def _candidate_by_id(
        candidates: list[GeneratorCandidate], candidate_id: str
    ) -> GeneratorCandidate | None:
        for candidate in candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        return None
