from httpx import ASGITransport, AsyncClient
import pytest

from app.dependencies import get_critic_service
from app.main import app
from app.schemas.critic import (
    CandidateScore,
    CriticEvaluateResponse,
    EpitomeScore,
)


class FakeCriticService:
    async def evaluate(self, request):
        return CriticEvaluateResponse(
            best_candidate_id="c1",
            scores=[
                CandidateScore(
                    candidate_id="c1",
                    epitome=EpitomeScore(ER=2, IP=2, EX=1),
                    casel={},
                    boundary_flag=False,
                    boundary_reason="",
                    weighted_total=5,
                    rationale="质量较好。",
                )
            ],
            preference_pair=None,
            fallback_message="",
        )


@pytest.mark.asyncio
async def test_critic_evaluate_endpoint_returns_service_response():
    app.dependency_overrides[get_critic_service] = lambda: FakeCriticService()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/critic/evaluate",
                json={
                    "session_id": "session-1",
                    "user_message": "我和朋友闹别扭了。",
                    "history": [],
                    "activated_casel": [],
                    "candidates": [
                        {
                            "candidate_id": "c1",
                            "orientation": "情感共情型",
                            "text": "听起来你有些受伤。",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        assert response.json()["best_candidate_id"] == "c1"
        assert response.json()["scores"][0]["epitome"]["ER"] == 2
    finally:
        app.dependency_overrides.clear()
