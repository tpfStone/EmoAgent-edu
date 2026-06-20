import json

import pytest

from app.config import Settings
from app.schemas.safety import ConversationMessage, SafetyGateRequest
from app.services.safety_gate_service import SafetyGateService


def _request(message: str, history=None):
    return SafetyGateRequest(
        session_id="session-1",
        current_message=message,
        history=history or [],
    )


@pytest.mark.asyncio
async def test_green_result_allows_generation(fake_llm_client, safety_log_dao):
    llm = fake_llm_client(
        [
            json.dumps(
                {
                    "risk_level": "green",
                    "matched_signals": [],
                    "rationale": "没有自伤或自杀表达。",
                },
                ensure_ascii=False,
            )
        ]
    )
    service = SafetyGateService(llm, safety_log_dao, Settings())

    response = await service.evaluate(_request("这次月考没考好，心情好差，不想上学了"))

    assert response.risk_level == "green"
    assert response.action.block_generation is False
    assert response.action.referral_message == ""
    assert safety_log_dao.records[0]["risk_level"] == "green"


@pytest.mark.asyncio
async def test_yellow_result_keeps_label_and_support_without_blocking(
    fake_llm_client, safety_log_dao
):
    llm = fake_llm_client(
        [
            json.dumps(
                {
                    "risk_level": "yellow",
                    "matched_signals": ["活着没什么意思"],
                    "rationale": "出现被动自杀意念但无计划。",
                },
                ensure_ascii=False,
            )
        ]
    )
    service = SafetyGateService(llm, safety_log_dao, Settings())

    response = await service.evaluate(_request("最近总觉得活着没什么意思，挺没劲的"))

    assert response.risk_level == "yellow"
    assert response.action.block_generation is False
    assert "12356" not in response.action.referral_message
    assert "12355" not in response.action.referral_message
    assert "爸爸妈妈、老师" in response.action.referral_message
    assert "下面的支持资源" in response.action.referral_message
    assert "你愿意和我说说，是很勇敢的一步。" in response.action.referral_message


@pytest.mark.asyncio
async def test_red_result_uses_emergency_referral(fake_llm_client, safety_log_dao):
    llm = fake_llm_client(
        [
            json.dumps(
                {
                    "risk_level": "red",
                    "matched_signals": ["今晚", "具体方法"],
                    "rationale": "出现具体时间和方法。",
                },
                ensure_ascii=False,
            )
        ]
    )
    service = SafetyGateService(llm, safety_log_dao, Settings())

    response = await service.evaluate(_request("我想好了今晚就用具体方法伤害自己"))

    assert response.risk_level == "red"
    assert response.action.block_generation is True
    assert "12356" not in response.action.referral_message
    assert "120 / 110" not in response.action.referral_message
    assert "立刻联系你信任的大人" in response.action.referral_message
    assert "下面的紧急资源" in response.action.referral_message
    assert "你不是一个人，有人愿意帮你。" in response.action.referral_message


@pytest.mark.asyncio
async def test_history_window_uses_recent_twelve_messages(fake_llm_client):
    llm = fake_llm_client(
        [
            json.dumps(
                {
                    "risk_level": "green",
                    "matched_signals": [],
                    "rationale": "无风险。",
                },
                ensure_ascii=False,
            )
        ]
    )
    history = [
        ConversationMessage(role="student", text="old-signal"),
        ConversationMessage(role="assistant", text="old-reply"),
    ] + [
        ConversationMessage(role="student", text=f"recent-signal-{index}")
        for index in range(12)
    ]
    service = SafetyGateService(
        llm,
        safety_log_dao=None,
        settings=Settings(HISTORY_WINDOW_N=6),
    )

    await service.evaluate(_request("你好", history=history))

    prompt = llm.prompts[0]["prompt"]
    assert "old-signal" not in prompt
    assert "recent-signal-0" in prompt
    assert "recent-signal-11" in prompt


@pytest.mark.asyncio
async def test_invalid_llm_json_defaults_to_yellow(fake_llm_client):
    llm = fake_llm_client(["不是JSON"])
    service = SafetyGateService(llm, safety_log_dao=None, settings=Settings())

    response = await service.evaluate(_request("你好"))

    assert response.risk_level == "yellow"
    assert response.matched_signals == ["llm_parse_failure"]
    assert response.action.block_generation is False
    assert "下面的支持资源" in response.action.referral_message


@pytest.mark.asyncio
async def test_llm_exception_defaults_to_yellow(fake_llm_client):
    llm = fake_llm_client([TimeoutError("timeout")])
    service = SafetyGateService(llm, safety_log_dao=None, settings=Settings())

    response = await service.evaluate(_request("你好"))

    assert response.risk_level == "yellow"
    assert response.matched_signals == ["llm_failure"]
    assert response.action.block_generation is False
