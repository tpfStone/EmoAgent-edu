import json

import pytest

from app.config import Settings
from app.schemas.scenario import ScenarioAnalyzeRequest
from app.services.scenario_service import ScenarioService


def _request(message: str, history=None):
    return ScenarioAnalyzeRequest(
        session_id="session-1",
        current_message=message,
        history=history or [],
    )


def _scenario_response(scenario: str, confidence: float = 0.9):
    return json.dumps(
        {
            "scenario": scenario,
            "scenario_confidence": confidence,
            "rationale": f"判断为{scenario}。",
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_casel"),
    [
        ("学业压力", ["自我觉察引导", "自我管理引导", "负责任决策引导"]),
        ("同伴关系", ["自我觉察引导", "社会觉察培养", "关系技能培养"]),
        (
            "亲子摩擦",
            ["自我觉察引导", "自我管理引导", "社会觉察培养", "关系技能培养"],
        ),
        ("其他", ["自我觉察引导"]),
    ],
)
async def test_scenario_maps_to_configured_casel(
    fake_llm_client, scenario, expected_casel
):
    llm = fake_llm_client([_scenario_response(scenario, confidence=0.82)])
    service = ScenarioService(llm, Settings())

    response = await service.analyze(_request("我最近有点烦"))

    assert response.scenario == scenario
    assert response.scenario_confidence == 0.82
    assert response.activated_casel == expected_casel
    assert response.rationale == f"判断为{scenario}。"
    assert llm.prompts[0]["temperature"] == 0.0


@pytest.mark.asyncio
async def test_scenario_parser_accepts_wrapped_json(fake_llm_client):
    llm = fake_llm_client([f"分类结果如下：\n{_scenario_response('同伴关系')}\n请查收"])
    service = ScenarioService(llm, Settings())

    response = await service.analyze(_request("他们出去玩没叫我"))

    assert response.scenario == "同伴关系"
    assert response.activated_casel == ["自我觉察引导", "社会觉察培养", "关系技能培养"]


@pytest.mark.asyncio
@pytest.mark.parametrize("llm_response", ["不是JSON", TimeoutError("timeout")])
async def test_invalid_or_failed_scenario_defaults_to_other(
    fake_llm_client, llm_response
):
    llm = fake_llm_client([llm_response])
    service = ScenarioService(llm, Settings())

    response = await service.analyze(_request("你好"))

    assert response.scenario == "其他"
    assert response.scenario_confidence == 0.0
    assert response.activated_casel == ["自我觉察引导"]
    assert response.rationale
