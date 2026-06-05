import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_orchestrator_service
from app.config import Settings
from app.main import app
from app.schemas.chat import ChatResponse


class FakeOrchestratorService:
    settings = Settings(CHAT_STREAM_CHUNK_SIZE=2)

    async def chat(self, request):
        return ChatResponse(
            session_id=request.session_id,
            anonymous_user_id=request.anonymous_user_id,
            status="answered",
            reply_text="我听见你现在有些不容易。",
            risk_level="green",
            scenario="其他",
            activated_casel=["自我觉察引导"],
            best_candidate_id="c1",
            candidates=[],
            scores=[],
            preference_pair=None,
        )


@pytest.mark.asyncio
async def test_chat_endpoint_returns_orchestrator_response():
    app.dependency_overrides[get_orchestrator_service] = lambda: FakeOrchestratorService()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat",
                json={
                    "session_id": "session-1",
                    "current_message": "这次月考没考好，心情很差。",
                },
            )

        assert response.status_code == 200
        assert response.json()["session_id"] == "session-1"
        assert response.json()["status"] == "answered"
        assert response.json()["risk_level"] == "green"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_stream_endpoint_returns_sse_events():
    app.dependency_overrides[get_orchestrator_service] = lambda: FakeOrchestratorService()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat/stream",
                json={
                    "session_id": "session-1",
                    "anonymous_user_id": "anon-1",
                    "current_message": "这次月考没考好，心情很差。",
                },
            )

        assert response.status_code == 200
        body = response.text
        assert "event: stage" in body
        assert "event: metadata" in body
        assert "event: delta" in body
        assert "event: done" in body
        assert '"anonymous_user_id": "anon-1"' in body
    finally:
        app.dependency_overrides.clear()
