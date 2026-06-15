import pytest

from app.config import Settings
from app.schemas.safety import SafetyGateRequest
from app.services.classifier_safety_gate_service import ClassifierSafetyGateService
from app.services.f1_safety_classifier import F1SafetyPrediction


def _request(message: str, history=None):
    return SafetyGateRequest(
        session_id="session-1",
        current_message=message,
        history=history or [],
    )


class FakeSafetyClassifier:
    def __init__(self, prediction=None, exc=None):
        self.prediction = prediction
        self.exc = exc
        self.texts = []

    def predict(self, text: str):
        self.texts.append(text)
        if self.exc is not None:
            raise self.exc
        return self.prediction


def _prediction(level: str, keywords=None, probabilities=None, rule_signals=None):
    probabilities = probabilities or {"green": 0.9, "yellow": 0.05, "red": 0.05}
    return F1SafetyPrediction(
        risk_level=level,
        argmax_level=level,
        probabilities=probabilities,
        matched_keywords=keywords or [],
        latency_ms=12.3,
        rule_signals=rule_signals or [],
    )


@pytest.mark.asyncio
async def test_classifier_green_result_allows_generation(safety_log_dao):
    classifier = FakeSafetyClassifier(_prediction("green"))
    service = ClassifierSafetyGateService(classifier, safety_log_dao, Settings())

    response = await service.evaluate(_request("这次月考没考好，心情好差，不想上学了"))

    assert response.risk_level == "green"
    assert response.action.block_generation is False
    assert response.action.referral_message == ""
    assert response.matched_signals == []
    assert safety_log_dao.records[0]["risk_level"] == "green"


@pytest.mark.asyncio
async def test_classifier_yellow_result_uses_fixed_referral():
    classifier = FakeSafetyClassifier(
        _prediction(
            "yellow",
            keywords=["活着"],
            probabilities={"green": 0.1, "yellow": 0.8, "red": 0.1},
        )
    )
    service = ClassifierSafetyGateService(classifier, None, Settings())

    response = await service.evaluate(_request("最近总觉得活着没什么意思，挺没劲的"))

    assert response.risk_level == "yellow"
    assert response.matched_signals == ["活着"]
    assert response.action.block_generation is True
    assert "12356" not in response.action.referral_message
    assert "下面的支持资源" in response.action.referral_message


@pytest.mark.asyncio
async def test_classifier_result_uses_rule_signals_when_keywords_are_empty():
    classifier = FakeSafetyClassifier(
        _prediction(
            "yellow",
            keywords=[],
            probabilities={"green": 0.99, "yellow": 0.001, "red": 0.001},
            rule_signals=["passive_death_ideation"],
        )
    )
    service = ClassifierSafetyGateService(classifier, None, Settings())

    response = await service.evaluate(_request("\u5982\u679c\u6211\u6d88\u5931\u4e86"))

    assert response.risk_level == "yellow"
    assert response.matched_signals == ["passive_death_ideation"]
    assert response.action.block_generation is True


@pytest.mark.asyncio
async def test_classifier_red_result_uses_emergency_referral():
    classifier = FakeSafetyClassifier(
        _prediction(
            "red",
            keywords=["自杀", "药"],
            probabilities={"green": 0.01, "yellow": 0.09, "red": 0.9},
        )
    )
    service = ClassifierSafetyGateService(classifier, None, Settings())

    response = await service.evaluate(_request("我想自杀，已经准备好了药"))

    assert response.risk_level == "red"
    assert response.matched_signals == ["自杀", "药"]
    assert response.action.block_generation is True
    assert "120 / 110" not in response.action.referral_message
    assert "下面的紧急资源" in response.action.referral_message


@pytest.mark.asyncio
async def test_classifier_uses_current_message_only():
    classifier = FakeSafetyClassifier(_prediction("green"))
    service = ClassifierSafetyGateService(
        classifier,
        safety_log_dao=None,
        settings=Settings(HISTORY_WINDOW_N=6),
    )

    await service.evaluate(_request("你好", history=[]))

    assert classifier.texts == ["你好"]


@pytest.mark.asyncio
async def test_classifier_exception_defaults_to_yellow():
    classifier = FakeSafetyClassifier(exc=TimeoutError("timeout"))
    service = ClassifierSafetyGateService(classifier, safety_log_dao=None, settings=Settings())

    response = await service.evaluate(_request("你好"))

    assert response.risk_level == "yellow"
    assert response.matched_signals == ["classifier_failure"]
    assert response.action.block_generation is True
