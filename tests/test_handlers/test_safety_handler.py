from httpx import ASGITransport, AsyncClient
import pytest

from app.dependencies import get_safety_gate_service
from app.main import app
from app.schemas.safety import SafetyAction, SafetyGateResponse


class FakeSafetyService:
    async def evaluate(self, request):
        return SafetyGateResponse(
            risk_level="green",
            matched_signals=[],
            rationale="无风险。",
            action=SafetyAction(block_generation=False, referral_message=""),
        )


@pytest.mark.asyncio
async def test_safety_evaluate_endpoint_returns_service_response():
    app.dependency_overrides[get_safety_gate_service] = lambda: FakeSafetyService()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/safety/evaluate",
                json={
                    "session_id": "session-1",
                    "current_message": "你好",
                    "history": [],
                },
            )

        assert response.status_code == 200
        assert response.json()["risk_level"] == "green"
        assert response.json()["action"]["block_generation"] is False
    finally:
        app.dependency_overrides.clear()
