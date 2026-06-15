from httpx import ASGITransport, AsyncClient
import pytest

from app.dependencies import get_scenario_service
from app.main import app
from app.schemas.safety import SafetyAction, SafetyGateResponse
from app.schemas.scenario import ScenarioAnalyzeResponse


class FakeScenarioService:
    async def analyze(self, request):
        return ScenarioAnalyzeResponse(
            scenario="同伴关系",
            scenario_confidence=0.91,
            activated_casel=["自我觉察引导", "社会觉察培养", "关系技能培养"],
            secondary_safety=SafetyGateResponse(
                risk_level="green",
                matched_signals=[],
                rationale="F2 二次安全复核通过。",
                action=SafetyAction(block_generation=False, referral_message=""),
            ),
            rationale="与同伴互动受挫有关。",
        )


@pytest.mark.asyncio
async def test_scenario_evaluate_endpoint_returns_service_response():
    app.dependency_overrides[get_scenario_service] = lambda: FakeScenarioService()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/scenario/evaluate",
                json={
                    "session_id": "session-1",
                    "current_message": "他们出去玩没叫我",
                    "history": [],
                },
            )

        assert response.status_code == 200
        assert response.json()["scenario"] == "同伴关系"
        assert response.json()["activated_casel"] == [
            "自我觉察引导",
            "社会觉察培养",
            "关系技能培养",
        ]
    finally:
        app.dependency_overrides.clear()
