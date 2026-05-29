from httpx import ASGITransport, AsyncClient
import pytest

from app.dependencies import get_generator_service
from app.main import app
from app.schemas.generator import (
    GeneratorCandidate,
    GeneratorGenerateResponse,
)


class FakeGeneratorService:
    async def generate(self, request):
        return GeneratorGenerateResponse(
            candidates=[
                GeneratorCandidate(
                    candidate_id="c1",
                    orientation="情感共情型",
                    text="听起来你有点受伤。",
                ),
                GeneratorCandidate(
                    candidate_id="c2",
                    orientation="认知共情型",
                    text="你愿意说说最在意的是什么吗？",
                ),
            ]
        )


@pytest.mark.asyncio
async def test_generator_endpoint_returns_f4_ready_candidates():
    app.dependency_overrides[get_generator_service] = lambda: FakeGeneratorService()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/generator/generate",
                json={
                    "session_id": "session-1",
                    "user_message": "他们出去玩没叫我",
                    "history": [],
                    "scenario": "同伴关系",
                    "rag_examples": [],
                },
            )

        assert response.status_code == 200
        assert response.json()["candidates"] == [
            {
                "candidate_id": "c1",
                "orientation": "情感共情型",
                "text": "听起来你有点受伤。",
            },
            {
                "candidate_id": "c2",
                "orientation": "认知共情型",
                "text": "你愿意说说最在意的是什么吗？",
            },
        ]
    finally:
        app.dependency_overrides.clear()
