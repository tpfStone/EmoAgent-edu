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
    assert "【你的取向：共情陪伴 —— 全程向内】" in llm.prompts[0]["prompt"]
    assert "不要问任何问题" in llm.prompts[0]["prompt"]
    assert '不要把"哇"、"其实你"或品质化夸奖作为默认开头' in llm.prompts[0]["prompt"]
    assert "最终回复只包含直接对学生说的话" in llm.prompts[0]["prompt"]
    assert "禁止内部提示外泄" in llm.prompts[0]["prompt"]
    assert "不得编造用户未说的事实" in llm.prompts[0]["prompt"]
    assert "少评价、少说教、少替第三方解释，多承接孩子感受" in llm.prompts[0]["prompt"]
    assert "【你的取向：引导反思 —— 重心向外】" in llm.prompts[1]["prompt"]
    assert "不要固定使用任何引导套话" in llm.prompts[1]["prompt"]
    assert "不替朋友、同学、家长或老师解释动机" in llm.prompts[1]["prompt"]
    assert "如果新角度需要猜他人的心里想法，就换成孩子自己的感受、需要或可控边界" in llm.prompts[1]["prompt"]
    assert "如果新角度需要补充孩子没说过的事实" in llm.prompts[1]["prompt"]
    assert "退回为关于孩子感受的轻问题" in llm.prompts[1]["prompt"]
    assert "反趋同" in llm.prompts[1]["prompt"]
    assert "避免模板化" in llm.prompts[1]["prompt"]
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
async def test_generator_prompt_contains_f9_reliability_guardrails(fake_llm_client):
    llm = fake_llm_client(["共情回应", "反思回应"])
    service = GeneratorService(llm, Settings())

    await service.generate(_request())

    empathic_prompt = llm.prompts[0]["prompt"]
    reflective_prompt = llm.prompts[1]["prompt"]
    assert "未充分承接情绪前，不要把痛苦、自责、愤怒或不信任直接重构成优点、主见、判断力或在乎别人" in empathic_prompt
    assert "轻量稳定感可以使用，但前面必须已经具体回应当前倾诉" in empathic_prompt
    assert "可以使用具体、低压、学生能直接回答的二选一问题" in reflective_prompt
    assert "二选一问题的前提不能替第三方解释动机，也不能替学生下人格或关系结论" in reflective_prompt
    assert "不要用“说明你”“可见你”“这本身”把孩子的痛苦总结成品质、能力或优点" in empathic_prompt
    assert "肯定只能落在孩子明确说出的动作、感受或表达本身" in empathic_prompt
    assert "不要把抱怨、愤怒、自责、沉默、反复确认改写成判断力、懂事、很有数或有主见" in reflective_prompt
    assert "换个角度看" not in reflective_prompt
    assert "承接必须包含对孩子说出的那一件具体的事的复述" in empathic_prompt
    assert "最多只能跟在具体复述后面作补充，绝不能单独充当承接" in empathic_prompt
    assert "开头先用一句具体复述接住情绪" in reflective_prompt
    assert "引导反思型的承接可以短，但不能空" in reflective_prompt
    assert "一句具体复述即可" in reflective_prompt
    assert "不要写括号式阶段标签" in reflective_prompt
    assert "（先接住你的场景）" in reflective_prompt
    assert "（再递新视角）" in reflective_prompt


@pytest.mark.asyncio
async def test_failed_candidate_generation_returns_fallback(fake_llm_client):
    llm = fake_llm_client([TimeoutError("timeout"), "你愿意多说一点吗？"])
    service = GeneratorService(llm, Settings())

    response = await service.generate(_request())

    assert response.candidates[0].candidate_id == "c1"
    assert response.candidates[0].orientation == "共情型"
    assert response.candidates[0].text == GENERATOR_FALLBACK_TEXT
    assert response.candidates[1].text == "你愿意多说一点吗？"
