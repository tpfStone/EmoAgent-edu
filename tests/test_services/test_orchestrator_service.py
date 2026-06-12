import json

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
            secondary_safety=SafetyGateResponse(
                risk_level="green",
                matched_signals=[],
                rationale="F2 二次安全复核通过。",
                action=SafetyAction(block_generation=False, referral_message=""),
            ),
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
                    orientation="情感共情型",
                    text="我听见你很难受。",
                ),
                GeneratorCandidate(
                    candidate_id="c2",
                    orientation="认知共情型",
                    text="你愿意说说发生了什么吗？",
                ),
            ]
        )
        self.exc = exc
        self.requests = []
        self.candidate_ids = []
        self.followup_requests = []

    async def generate(self, request):
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return self.response

    async def generate_one(self, request, candidate_id="c2"):
        self.requests.append(request)
        self.candidate_ids.append(candidate_id)
        if self.exc is not None:
            raise self.exc
        return self._candidate_by_id(candidate_id)

    async def generate_followup(
        self,
        *,
        session_id,
        user_message,
        history,
        f4_guidance="",
    ):
        self.followup_requests.append(
            {
                "session_id": session_id,
                "user_message": user_message,
                "history": history,
                "f4_guidance": f4_guidance,
            }
        )
        if self.exc is not None:
            raise self.exc
        return GeneratorCandidate(
            candidate_id="cbt",
            orientation="认知共情型",
            text="我们先把这件事里最卡住的一点说清楚。",
        )

    async def stream_one_text(self, request, candidate_id="c2"):
        candidate = await self.generate_one(request, candidate_id=candidate_id)
        yield candidate.text

    async def stream_followup_text(
        self,
        *,
        user_message,
        history,
        f4_guidance="",
    ):
        candidate = await self.generate_followup(
            session_id="stream-session",
            user_message=user_message,
            history=history,
            f4_guidance=f4_guidance,
        )
        yield candidate.text

    def _candidate_by_id(self, candidate_id):
        for candidate in self.response.candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        return self.response.candidates[-1]


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


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value


class InMemoryHistoryStoreWithRedis(InMemoryHistoryStore):
    def __init__(self):
        super().__init__()
        self.redis = FakeRedis()


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


def _scenario_with_route(
    support_mode: str,
    emotion_intensity: str = "medium",
    help_seeking: bool = False,
):
    return RecordingScenarioService().response.model_copy(
        update={
            "support_mode": support_mode,
            "emotion_intensity": emotion_intensity,
            "help_seeking": help_seeking,
        }
    )


def _record_background_schedule(service):
    scheduled = []

    def record(**kwargs):
        scheduled.append(kwargs)

    service._schedule_background_critic = record
    return scheduled


@pytest.mark.asyncio
async def test_first_turn_fast_path_records_single_candidate_and_appends_history():
    history_store = InMemoryHistoryStore()
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
    scheduled = _record_background_schedule(service)

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="我和朋友闹别扭了。")
    )

    history = await history_store.get_history("s1", max_messages=12)

    assert response.status == "answered"
    assert response.reply_text == "你愿意说说发生了什么吗？"
    assert response.risk_level == "green"
    assert response.scenario == "同伴关系"
    assert response.best_candidate_id == "c2"
    assert response.selected_by == "fast_first_turn"
    assert len(response.candidates) == 1
    assert response.candidates[0].candidate_id == "c2"
    assert response.scores == []
    assert response.preference_pair is None
    assert safety.requests[0].history == []
    assert scenario.requests[0].history == []
    assert generator.requests[0].rag_examples == []
    assert generator.candidate_ids == ["c2"]
    assert critic.requests == []
    assert scheduled[0]["activated_casel"] == ["自我觉察引导"]
    assert scheduled[0]["candidates"][0].candidate_id == "c2"
    assert history[-2].text == "我和朋友闹别扭了。"
    assert history[-1].text == "你愿意说说发生了什么吗？"
    assert dao.calls[0]["status"] == "answered"
    assert dao.calls[0]["best_candidate_id"] == "c2"
    assert dao.calls[0]["scores"] == []
    assert dao.calls[0]["preference_pair"] is None


@pytest.mark.asyncio
async def test_first_turn_routes_to_c1_for_emotion_first_or_high_intensity():
    scenario = RecordingScenarioService(
        _scenario_with_route(
            support_mode="emotion_first",
            emotion_intensity="high",
            help_seeking=False,
        )
    )
    generator = RecordingGeneratorService()
    service = _service(scenario=scenario, generator=generator)
    _record_background_schedule(service)

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="I feel awful today.")
    )

    assert response.status == "answered"
    assert response.best_candidate_id == "c1"
    assert response.support_mode == "emotion_first"
    assert response.emotion_intensity == "high"
    assert response.help_seeking is False
    assert response.selected_by == "fast_first_turn"
    assert generator.candidate_ids == ["c1"]


@pytest.mark.asyncio
async def test_first_turn_routes_to_c2_for_solution_seeking():
    scenario = RecordingScenarioService(
        _scenario_with_route(support_mode="solution_seeking", help_seeking=True)
    )
    generator = RecordingGeneratorService()
    service = _service(scenario=scenario, generator=generator)
    _record_background_schedule(service)

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="What should I do next?")
    )

    assert response.status == "answered"
    assert response.best_candidate_id == "c2"
    assert response.support_mode == "solution_seeking"
    assert response.help_seeking is True
    assert response.selected_by == "fast_first_turn"
    assert generator.candidate_ids == ["c2"]


@pytest.mark.asyncio
async def test_follow_up_uses_ready_f4_guidance_without_rerunning_first_turn_chain():
    history_store = InMemoryHistoryStoreWithRedis()
    await history_store.append_messages(
        "s1",
        [
            ConversationMessage(role="student", text="之前我说作业很多。"),
            ConversationMessage(role="assistant", text="那种被作业压住的感觉很闷。"),
        ],
        max_messages=12,
    )
    await history_store.redis.set(
        "emoedu:f4_guidance:s1",
        json.dumps(
            {
                "status": "ready",
                "guidance": "Use a more concrete emotional acknowledgment.",
            }
        )
    )
    safety = RecordingSafetyService()
    scenario = RecordingScenarioService()
    generator = RecordingGeneratorService()
    service = _service(
        safety=safety,
        scenario=scenario,
        generator=generator,
        history_store=history_store,
    )

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="那我现在怎么办？")
    )

    assert response.status == "answered"
    assert response.best_candidate_id == "cbt"
    assert response.selected_by == "fast_cbt_followup_with_f4_guidance"
    assert response.scenario is None
    assert len(safety.requests) == 1
    assert safety.requests[0].current_message == "那我现在怎么办？"
    assert safety.requests[0].history[0].text == "之前我说作业很多。"
    assert scenario.requests == []
    assert generator.requests == []
    assert generator.followup_requests[0]["f4_guidance"] == (
        "Use a more concrete emotional acknowledgment."
    )
    assert generator.followup_requests[0]["history"][0].text == "之前我说作业很多。"


@pytest.mark.asyncio
async def test_follow_up_safety_short_circuits_before_generator():
    referral = "follow-up referral"
    history_store = InMemoryHistoryStore()
    await history_store.append_messages(
        "s1",
        [
            ConversationMessage(role="student", text="first message"),
            ConversationMessage(role="assistant", text="first reply"),
        ],
        max_messages=12,
    )
    safety = RecordingSafetyService(
        SafetyGateResponse(
            risk_level="red",
            matched_signals=["method_signal"],
            rationale="follow-up risk",
            action=SafetyAction(block_generation=True, referral_message=referral),
        )
    )
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
        ChatRequest(session_id="s1", current_message="follow-up crisis")
    )

    history = await history_store.get_history("s1", max_messages=12)

    assert response.status == "blocked_by_safety"
    assert response.reply_text == referral
    assert response.risk_level == "red"
    assert len(safety.requests) == 1
    assert safety.requests[0].current_message == "follow-up crisis"
    assert safety.requests[0].history[0].text == "first message"
    assert scenario.requests == []
    assert generator.followup_requests == []
    assert critic.requests == []
    assert history[-1].text == referral
    assert dao.calls[0]["status"] == "blocked_by_safety"
    assert dao.calls[0]["risk_level"] == "red"


@pytest.mark.asyncio
async def test_stream_follow_up_safety_short_circuits_before_generator():
    referral = "stream referral"
    history_store = InMemoryHistoryStore()
    await history_store.append_messages(
        "s1",
        [
            ConversationMessage(role="student", text="first message"),
            ConversationMessage(role="assistant", text="first reply"),
        ],
        max_messages=12,
    )
    safety = RecordingSafetyService(
        SafetyGateResponse(
            risk_level="red",
            matched_signals=["method_signal"],
            rationale="stream follow-up risk",
            action=SafetyAction(block_generation=True, referral_message=referral),
        )
    )
    generator = RecordingGeneratorService()
    dao = RecordingChatTurnDAO()
    service = _service(
        safety=safety,
        generator=generator,
        history_store=history_store,
        dao=dao,
        settings=Settings(CHAT_STREAM_CHUNK_SIZE=12, CHAT_FALLBACK_MESSAGE="fallback"),
    )

    events = [
        event
        async for event in service.stream_chat(
            ChatRequest(session_id="s1", current_message="stream crisis")
        )
    ]

    event_names = [name for name, _payload in events]
    done_payload = events[-1][1]
    delta_text = "".join(
        payload["text"] for name, payload in events if name == "delta"
    )

    assert event_names[0] == "metadata"
    assert "delta" in event_names
    assert event_names[-1] == "done"
    assert done_payload["status"] == "blocked_by_safety"
    assert done_payload["risk_level"] == "red"
    assert done_payload["reply_text"] == referral
    assert delta_text == referral
    assert len(safety.requests) == 1
    assert safety.requests[0].current_message == "stream crisis"
    assert generator.followup_requests == []
    assert dao.calls[0]["status"] == "blocked_by_safety"


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
async def test_f2_secondary_safety_short_circuits_generator_and_critic():
    referral = "f2 referral"
    scenario = RecordingScenarioService(
        ScenarioAnalyzeResponse(
            scenario="学业压力",
            scenario_confidence=0.86,
            activated_casel=["自我觉察引导", "自我管理引导", "负责任决策引导"],
            secondary_safety=SafetyGateResponse(
                risk_level="red",
                matched_signals=["今晚吃药"],
                rationale="F2 发现具体时间和方法。",
                action=SafetyAction(block_generation=True, referral_message=referral),
            ),
            rationale="涉及考试压力。",
        )
    )
    generator = RecordingGeneratorService()
    critic = RecordingCriticService()
    history_store = InMemoryHistoryStore()
    dao = RecordingChatTurnDAO()
    service = _service(
        scenario=scenario,
        generator=generator,
        critic=critic,
        history_store=history_store,
        dao=dao,
    )

    response = await service.chat(
        ChatRequest(session_id="s1", current_message="考试太差了，我今晚吃药算了")
    )

    history = await history_store.get_history("s1", max_messages=12)

    assert response.status == "blocked_by_safety"
    assert response.reply_text == referral
    assert response.risk_level == "red"
    assert response.scenario == "学业压力"
    assert response.activated_casel == ["自我觉察引导", "自我管理引导", "负责任决策引导"]
    assert generator.requests == []
    assert critic.requests == []
    assert history[-1].text == referral
    assert dao.calls[0]["status"] == "blocked_by_safety"
    assert dao.calls[0]["risk_level"] == "red"


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
