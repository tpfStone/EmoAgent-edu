import pytest

from app.config import Settings
from app.schemas.chat import ChatRequest
from app.schemas.critic import (
    CandidateScore,
    CriticEvaluateResponse,
    EpitomeScore,
    PreferencePair,
)
from app.schemas.generator import GeneratorCandidate, GeneratorGenerateResponse
from app.schemas.safety import ConversationMessage, SafetyAction, SafetyGateResponse
from app.schemas.scenario import ScenarioAnalyzeResponse
from app.services.history_store import InMemoryHistoryStore
from app.services.orchestrator_service import OrchestratorService


class RecordingSafetyService:
    def __init__(self, response=None, exc: Exception | None = None):
        self.response = response or SafetyGateResponse(
            risk_level="green",
            matched_signals=[],
            rationale="无风险。",
            action=SafetyAction(block_generation=False, referral_message=""),
        )
        self.exc = exc
        self.requests = []

    async def evaluate(self, request):
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return self.response


class RecordingScenarioService:
    def __init__(self, response=None, exc: Exception | None = None):
        self.response = response or ScenarioAnalyzeResponse(
            scenario="同伴关系",
            scenario_confidence=0.9,
            activated_casel=["自我觉察引导"],
            rationale="同伴冲突。",
        )
        self.exc = exc
        self.requests = []

    async def analyze(self, request):
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return self.response


class RecordingGeneratorService:
    def __init__(self, response=None, exc: Exception | None = None):
        self.response = response or GeneratorGenerateResponse(
            candidates=[
                GeneratorCandidate(
                    candidate_id="c1",
                    orientation="共情型",
                    text="我听见你很难受。",
                ),
                GeneratorCandidate(
                    candidate_id="c2",
                    orientation="引导反思型",
                    text="你愿意说说发生了什么吗？",
                ),
            ]
        )
        self.exc = exc
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return self.response


class RecordingCriticService:
    def __init__(self, response=None, exc: Exception | None = None):
        self.response = response or CriticEvaluateResponse(
            best_candidate_id="c2",
            scores=[
                CandidateScore(
                    candidate_id="c1",
                    epitome=EpitomeScore(ER=2, IP=1, EX=1),
                    casel={"自我觉察引导": 1},
                    boundary_flag=False,
                    boundary_reason="",
                    weighted_total=4.5,
                    rationale="可以。",
                ),
                CandidateScore(
                    candidate_id="c2",
                    epitome=EpitomeScore(ER=2, IP=2, EX=1),
                    casel={"自我觉察引导": 2},
                    boundary_flag=False,
                    boundary_reason="",
                    weighted_total=6.0,
                    rationale="更好。",
                ),
            ],
            preference_pair=PreferencePair(winner_id="c2", loser_id="c1"),
            fallback_message="",
        )
        self.exc = exc
        self.requests = []

    async def evaluate(self, request):
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return self.response


class RecordingChatTurnDAO:
    def __init__(self):
        self.calls = []

    async def create_turn(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


def _service(
    safety=None,
    scenario=None,
    generator=None,
    critic=None,
    history_store=None,
    dao=None,
    settings=None,
):
    return OrchestratorService(
        safety_service=safety or RecordingSafetyService(),
        scenario_service=scenario or RecordingScenarioService(),
        generator_service=generator or RecordingGeneratorService(),
        critic_service=critic or RecordingCriticService(),
        history_store=history_store or InMemoryHistoryStore(),
        chat_turn_dao=dao or RecordingChatTurnDAO(),
        settings=settings or Settings(CHAT_FALLBACK_MESSAGE="fallback"),
    )


@pytest.mark.asyncio
async def test_green_happy_path_records_and_appends_history():
    history_store = InMemoryHistoryStore()
    await history_store.append_messages(
        "s1",
        [ConversationMessage(role="student", text="之前的话")],
        max_messages=12,
    )
    safety = RecordingSafetyService()
    scenario = RecordingScenarioService()
    generator = RecordingGeneratorService()
    critic = RecordingCriticService()
    dao = RecordingChatTurnDAO()
    service = _service(
        safety=safety,
        scenario=scenario,
        generator=generator,
        critic=critic,
        history_store=history_store,
        dao=dao,
    )

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="我和朋友闹别扭了。")
    )

    history = await history_store.get_history("s1", max_messages=12)

    assert response.status == "answered"
    assert response.reply_text == "你愿意说说发生了什么吗？"
    assert response.risk_level == "green"
    assert response.scenario == "同伴关系"
    assert response.best_candidate_id == "c2"
    assert safety.requests[0].history[0].text == "之前的话"
    assert scenario.requests[0].history[0].text == "之前的话"
    assert generator.requests[0].rag_examples == []
    assert critic.requests[0].activated_casel == ["自我觉察引导"]
    assert history[-2].text == "我和朋友闹别扭了。"
    assert history[-1].text == "你愿意说说发生了什么吗？"
    assert dao.calls[0]["status"] == "answered"
    assert dao.calls[0]["preference_pair"].winner_id == "c2"


@pytest.mark.asyncio
async def test_non_green_safety_short_circuits_downstream_services():
    referral = "fixed referral"
    safety = RecordingSafetyService(
        SafetyGateResponse(
            risk_level="yellow",
            matched_signals=["不想存在"],
            rationale="有风险。",
            action=SafetyAction(block_generation=True, referral_message=referral),
        )
    )
    scenario = RecordingScenarioService()
    generator = RecordingGeneratorService()
    critic = RecordingCriticService()
    history_store = InMemoryHistoryStore()
    dao = RecordingChatTurnDAO()
    service = _service(
        safety=safety,
        scenario=scenario,
        generator=generator,
        critic=critic,
        history_store=history_store,
        dao=dao,
    )

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="我不想存在了")
    )

    history = await history_store.get_history("s1", max_messages=12)

    assert response.status == "blocked_by_safety"
    assert response.reply_text == referral
    assert response.risk_level == "yellow"
    assert scenario.requests == []
    assert generator.requests == []
    assert critic.requests == []
    assert history[-1].text == referral
    assert dao.calls[0]["status"] == "blocked_by_safety"
    assert dao.calls[0]["risk_level"] == "yellow"


@pytest.mark.asyncio
async def test_all_candidates_blocked_returns_critic_fallback():
    critic = RecordingCriticService(
        CriticEvaluateResponse(
            best_candidate_id=None,
            scores=[
                CandidateScore(
                    candidate_id="c1",
                    epitome=EpitomeScore(ER=2, IP=2, EX=2),
                    casel={},
                    boundary_flag=True,
                    boundary_reason="越界",
                    weighted_total=6.0,
                    rationale="越界。",
                )
            ],
            preference_pair=None,
            fallback_message="critic fallback",
        )
    )
    dao = RecordingChatTurnDAO()
    service = _service(critic=critic, dao=dao)

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="我和朋友闹别扭了。")
    )

    assert response.status == "all_candidates_blocked"
    assert response.reply_text == "critic fallback"
    assert response.best_candidate_id is None
    assert dao.calls[0]["status"] == "all_candidates_blocked"
    assert dao.calls[0]["fallback_message"] == "critic fallback"


@pytest.mark.asyncio
async def test_module_exception_returns_fallback_and_records_failure():
    generator = RecordingGeneratorService(exc=RuntimeError("boom"))
    history_store = InMemoryHistoryStore()
    dao = RecordingChatTurnDAO()
    service = _service(generator=generator, history_store=history_store, dao=dao)

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="这次月考没考好。")
    )

    history = await history_store.get_history("s1", max_messages=12)

    assert response.status == "module_failed"
    assert response.reply_text == "fallback"
    assert response.failed_module == "generator"
    assert response.failure_reason == "boom"
    assert history[-1].text == "fallback"
    assert dao.calls[0]["status"] == "module_failed"
    assert dao.calls[0]["failed_module"] == "generator"
    assert dao.calls[0]["failure_reason"] == "boom"
