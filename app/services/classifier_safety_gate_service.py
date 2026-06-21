import asyncio
from typing import Protocol

from app.config import Settings
from app.schemas.safety import SafetyAction, SafetyGateRequest, SafetyGateResponse
from app.services.f1_safety_classifier import F1SafetyPrediction
from app.services.safety_gate_service import (
    RED_REFERRAL_MESSAGE,
    SAFETY_UNAVAILABLE_MESSAGE,
    YELLOW_REFERRAL_MESSAGE,
)


class SafetyClassifierProtocol(Protocol):
    def predict(self, text: str) -> F1SafetyPrediction:
        ...


class ClassifierSafetyGateService:
    def __init__(
        self,
        safety_classifier: SafetyClassifierProtocol,
        safety_log_dao,
        settings: Settings,
    ):
        self.safety_classifier = safety_classifier
        self.safety_log_dao = safety_log_dao
        self.settings = settings

    async def evaluate(self, request: SafetyGateRequest) -> SafetyGateResponse:
        try:
            prediction = await asyncio.to_thread(
                self.safety_classifier.predict,
                self._classifier_text(request),
            )
            response = self._response_from_prediction(prediction)
        except Exception:
            response = self._response(
                risk_level="yellow",
                safety_status="unavailable",
                matched_signals=["classifier_failure"],
                rationale="本地 F1 安全分类器调用失败，安全评估暂不可用。",
            )

        if self.safety_log_dao is not None:
            await self.safety_log_dao.create_log(
                session_id=request.session_id,
                risk_level=response.risk_level,
                matched_signals=response.matched_signals,
                rationale=response.rationale,
                block_generation=response.action.block_generation,
                referral_message=response.action.referral_message,
            )
        return response

    @staticmethod
    def _classifier_text(request: SafetyGateRequest) -> str:
        # 当前 F1 分类器按 PsyQA 单条 input 训练，生产推理只使用本轮学生原始输入。
        return request.current_message

    def _response_from_prediction(self, prediction: F1SafetyPrediction) -> SafetyGateResponse:
        signals = []
        if prediction.risk_level != "green":
            signals = (
                prediction.matched_keywords[:12]
                or prediction.rule_signals[:12]
                or ["probability_threshold"]
            )
        probabilities = prediction.probabilities
        rationale = (
            f"本地 F1 安全分类器判定为 {prediction.risk_level}；"
            f"p_green={probabilities.get('green', 0.0):.3f}, "
            f"p_yellow={probabilities.get('yellow', 0.0):.3f}, "
            f"p_red={probabilities.get('red', 0.0):.3f}；"
            f"argmax={prediction.argmax_level}，latency={prediction.latency_ms:.1f}ms。"
        )
        return self._response(
            risk_level=prediction.risk_level,
            matched_signals=signals,
            rationale=rationale,
        )

    @staticmethod
    def _response(
        risk_level: str,
        matched_signals: list[str],
        rationale: str,
        safety_status: str = "ok",
    ) -> SafetyGateResponse:
        if safety_status == "unavailable":
            action = SafetyAction(
                block_generation=True,
                referral_message=SAFETY_UNAVAILABLE_MESSAGE,
            )
        elif risk_level == "green":
            action = SafetyAction(block_generation=False, referral_message="")
        elif risk_level == "yellow":
            action = SafetyAction(
                block_generation=False,
                referral_message=YELLOW_REFERRAL_MESSAGE,
            )
        else:
            action = SafetyAction(
                block_generation=True,
                referral_message=RED_REFERRAL_MESSAGE,
            )
        return SafetyGateResponse(
            risk_level=risk_level,
            safety_status=safety_status,  # type: ignore[arg-type]
            matched_signals=matched_signals,
            rationale=rationale,
            action=action,
        )
