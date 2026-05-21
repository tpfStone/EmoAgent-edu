import pytest

from app.config import Settings
from app.schemas.generator import GeneratorGenerateRequest
from app.services.generator_service import GENERATOR_FALLBACK_TEXT, GeneratorService


def _request(rag_examples=None):
    return GeneratorGenerateRequest(
        session_id="session-1",
        user_message="他们周末出去玩没叫我，我有点难受。",
        history=[],
        scenario="同伴关系",
        rag_examples=rag_examples or [],
    )


@pytest.mark.asyncio
async def test_generator_returns_two_fixed_orientation_candidates(fake_llm_client):
    llm = fake_llm_client(["我听见你有点受伤。", "你愿意说说最难受的是哪一刻吗？"])
    service = GeneratorService(llm, Settings())

    response = await service.generate(_request())

    assert [candidate.candidate_id for candidate in response.candidates] == ["c1", "c2"]
    assert [candidate.orientation for candidate in response.candidates] == [
        "共情型",
        "引导反思型",
    ]
    assert response.candidates[0].text == "我听见你有点受伤。"
    assert response.candidates[1].text == "你愿意说说最难受的是哪一刻吗？"


@pytest.mark.asyncio
async def test_generator_uses_orientation_prompts_rag_and_temperature(fake_llm_client):
    llm = fake_llm_client(["共情回应", "反思回应"])
    service = GeneratorService(llm, Settings(GENERATOR_LLM_TEMPERATURE=0.8))

    await service.generate(_request(rag_examples=["参考回应：先接住情绪。"]))

    assert len(llm.prompts) == 2
    assert "【你的取向：共情陪伴】" in llm.prompts[0]["prompt"]
    assert "【你的取向：引导反思】" in llm.prompts[1]["prompt"]
    assert "参考回应：先接住情绪。" in llm.prompts[0]["prompt"]
    assert "参考回应：先接住情绪。" in llm.prompts[1]["prompt"]
    assert llm.prompts[0]["temperature"] == 0.8
    assert llm.prompts[1]["temperature"] == 0.8


@pytest.mark.asyncio
async def test_generator_handles_empty_rag_examples(fake_llm_client):
    llm = fake_llm_client(["共情回应", "反思回应"])
    service = GeneratorService(llm, Settings())

    response = await service.generate(_request(rag_examples=[]))

    assert len(response.candidates) == 2
    assert "【参考（可选，仅供风格参考，不要照抄）】无" in llm.prompts[0]["prompt"]


@pytest.mark.asyncio
async def test_failed_candidate_generation_returns_fallback(fake_llm_client):
    llm = fake_llm_client([TimeoutError("timeout"), "你愿意多说一点吗？"])
    service = GeneratorService(llm, Settings())

    response = await service.generate(_request())

    assert response.candidates[0].candidate_id == "c1"
    assert response.candidates[0].orientation == "共情型"
    assert response.candidates[0].text == GENERATOR_FALLBACK_TEXT
    assert response.candidates[1].text == "你愿意多说一点吗？"
