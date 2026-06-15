import json

import pytest

from app.config import Settings
from app.schemas.critic import CandidateInput, CriticEvaluateRequest
from app.services.critic_service import CRITIC_FALLBACK_MESSAGE, CriticService


def _candidate(candidate_id: str, text: str, orientation: str = "共情型"):
    return CandidateInput(candidate_id=candidate_id, orientation=orientation, text=text)


def _request(candidates, activated_casel=None):
    return CriticEvaluateRequest(
        session_id="session-1",
        user_message="我和朋友闹别扭了，心里很难受。",
        history=[],
        activated_casel=activated_casel or [],
        candidates=candidates,
    )


def _score(er, ip, ex, boundary=False, reason="", casel=None):
    return json.dumps(
        {
            "ER": er,
            "IP": ip,
            "EX": ex,
            "casel": casel or {},
            "boundary_flag": boundary,
            "boundary_reason": reason,
            "rationale": "测试理由",
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_high_quality_candidate_wins_and_preference_pair_created(
    fake_llm_client, critic_run_dao
):
    llm = fake_llm_client([_score(2, 2, 1), _score(1, 0, 0)])
    service = CriticService(
        llm,
        critic_run_dao,
        Settings(CRITIC_SAMPLE_COUNT=1),
    )

    response = await service.evaluate(
        _request(
            [
                _candidate("c1", "听起来你很在意这段关系，也有点受伤。"),
                _candidate("c2", "别想太多。"),
            ]
        )
    )

    assert response.best_candidate_id == "c1"
    assert response.scores[0].weighted_total == 5
    assert response.scores[1].weighted_total == 1
    assert response.preference_pair is not None
    assert response.preference_pair.winner_id == "c1"
    assert response.preference_pair.loser_id == "c2"
    assert response.scores[0].casel == {}
    assert critic_run_dao.records[0]["best_candidate_id"] == "c1"


@pytest.mark.asyncio
async def test_boundary_candidate_is_excluded(fake_llm_client):
    llm = fake_llm_client(
        [
            _score(2, 2, 2, boundary=True, reason="建议隐瞒家长老师"),
            _score(1, 1, 1),
        ]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [
                _candidate("c1", "这事别跟你爸妈说。"),
                _candidate("c2", "可以先找一个你信任的大人聊聊。"),
            ]
        )
    )

    assert response.best_candidate_id == "c2"
    assert response.scores[0].boundary_flag is True
    assert response.scores[0].boundary_reason == "建议隐瞒家长老师"


@pytest.mark.asyncio
async def test_internal_prompt_leak_candidate_is_excluded(fake_llm_client):
    llm = fake_llm_client([_score(1, 1, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [
                _candidate("c1", "如果孩子想继续，可以追问：你更讨厌哪一点？"),
                _candidate("c2", "被比较的时候，心里那股委屈会很重。"),
            ]
        )
    )

    assert response.best_candidate_id == "c2"
    assert response.scores[0].boundary_flag is True
    assert response.scores[0].boundary_reason == "internal_prompt_leak"


@pytest.mark.asyncio
async def test_prompt_stage_labels_force_boundary_without_llm(fake_llm_client):
    llm = fake_llm_client([_score(2, 2, 2)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [
                _candidate(
                    "c1",
                    "（先接住你的场景）背了半天书被一句话浇灭，确实憋屈。（再递新视角）你有没有注意到你烦的是努力没被看见？",
                )
            ]
        )
    )

    assert response.scores[0].boundary_flag is True
    assert response.scores[0].boundary_reason == "internal_prompt_leak"
    assert response.best_candidate_id is None
    assert response.fallback_message == CRITIC_FALLBACK_MESSAGE


@pytest.mark.asyncio
async def test_whole_response_quote_wrapping_is_format_boundary(fake_llm_client):
    llm = fake_llm_client([_score(1, 1, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [
                _candidate("c1", "“你刚才说的那件事，确实让人很难受。”"),
                _candidate("c2", "你刚才说的那件事，确实让人很难受。"),
            ]
        )
    )

    assert response.best_candidate_id == "c2"
    assert response.scores[0].boundary_flag is True
    assert response.scores[0].boundary_reason == "format_artifact"
    assert len(llm.prompts) == 1


@pytest.mark.asyncio
async def test_in_sentence_quote_is_not_format_boundary(fake_llm_client):
    llm = fake_llm_client([_score(2, 2, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request([_candidate("c1", "你说“我真的很难受”的时候，那股委屈我听见了。")])
    )

    assert response.scores[0].boundary_flag is False
    assert response.scores[0].weighted_total == 5


@pytest.mark.asyncio
async def test_fabricated_fact_candidate_is_excluded(fake_llm_client):
    llm = fake_llm_client(
        [
            _score(2, 2, 2, boundary=True, reason="事实编造"),
            _score(1, 1, 1),
        ]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [
                _candidate("c1", "你一口气把三科的作业都列出来排了顺序。"),
                _candidate("c2", "这么多作业压过来，会觉得喘不过气。"),
            ]
        )
    )

    assert response.best_candidate_id == "c2"
    assert response.scores[0].boundary_flag is True
    assert response.scores[0].boundary_reason == "事实编造"


@pytest.mark.asyncio
async def test_all_boundary_candidates_return_fallback(fake_llm_client):
    llm = fake_llm_client(
        [
            _score(2, 2, 2, boundary=True, reason="越界"),
            _score(1, 1, 1, boundary=True, reason="不适龄"),
        ]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request([_candidate("c1", "bad"), _candidate("c2", "bad")])
    )

    assert response.best_candidate_id is None
    assert response.preference_pair is None
    assert response.fallback_message == "所有候选回应均未通过边界检查，请转人工复核。"


@pytest.mark.asyncio
async def test_single_candidate_has_no_preference_pair(fake_llm_client):
    llm = fake_llm_client([_score(2, 2, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(_request([_candidate("c1", "我听见你很难受。")]))

    assert response.best_candidate_id == "c1"
    assert response.preference_pair is None


@pytest.mark.asyncio
async def test_three_samples_use_median_scores(fake_llm_client):
    llm = fake_llm_client([_score(0, 0, 0), _score(2, 2, 2), _score(1, 1, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=3))

    response = await service.evaluate(_request([_candidate("c1", "我在听你说。")]))

    assert response.scores[0].epitome.ER == 1
    assert response.scores[0].epitome.IP == 1
    assert response.scores[0].epitome.EX == 1
    assert response.scores[0].weighted_total == 3


@pytest.mark.asyncio
async def test_critic_uses_critic_specific_token_budget_and_json_response_format(
    fake_llm_client,
):
    llm = fake_llm_client([_score(1, 1, 1)])
    service = CriticService(
        llm,
        None,
        Settings(
            CRITIC_SAMPLE_COUNT=1,
            LLM_MAX_TOKENS=1000,
            CRITIC_LLM_MAX_TOKENS=4096,
            CRITIC_LLM_RESPONSE_FORMAT_JSON=True,
        ),
    )

    await service.evaluate(_request([_candidate("c1", "我听见你很难受。")]))

    assert llm.prompts[0]["max_tokens"] == 4096
    assert llm.prompts[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_long_empty_answer_receives_only_judge_scores(fake_llm_client):
    llm = fake_llm_client([_score(1, 0, 0)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request([_candidate("c1", "我理解你。" * 100)])
    )

    assert response.scores[0].weighted_total == 1


@pytest.mark.asyncio
async def test_wrong_question_can_keep_ip_zero(fake_llm_client):
    llm = fake_llm_client([_score(1, 0, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(_request([_candidate("c1", "我们聊聊作业吧。")]))

    assert response.scores[0].epitome.IP == 0


@pytest.mark.asyncio
async def test_empty_activated_casel_returns_empty_casel(fake_llm_client):
    llm = fake_llm_client([_score(2, 2, 2)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request([_candidate("c1", "你愿意说说发生了什么吗？")], activated_casel=[])
    )

    assert response.scores[0].casel == {}


@pytest.mark.asyncio
async def test_non_empty_activated_casel_scores_enter_weighted_total(fake_llm_client):
    llm = fake_llm_client(
        [
            _score(
                1,
                1,
                1,
                casel={
                    "自我觉察引导": 2,
                    "关系技能培养": 1,
                    "未激活维度": 2,
                },
            )
        ]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [_candidate("c1", "听起来你有点受伤，我们可以聊聊怎么和朋友说。")],
            activated_casel=["自我觉察引导", "关系技能培养"],
        )
    )

    assert response.scores[0].casel == {
        "自我觉察引导": 2,
        "关系技能培养": 1,
    }
    assert response.scores[0].weighted_total == 3.75


@pytest.mark.asyncio
async def test_missing_and_invalid_casel_values_are_zero(fake_llm_client):
    llm = fake_llm_client(
        [
            _score(
                2,
                1,
                1,
                casel={
                    "自我觉察引导": "bad",
                    "社会觉察培养": 3,
                },
            )
        ]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [_candidate("c1", "也许可以想想对方当时可能怎么理解这件事。")],
            activated_casel=["自我觉察引导", "社会觉察培养", "关系技能培养"],
        )
    )

    assert response.scores[0].casel == {
        "自我觉察引导": 0,
        "社会觉察培养": 0,
        "关系技能培养": 0,
    }
    assert response.scores[0].weighted_total == 4.0


@pytest.mark.asyncio
async def test_casel_scores_can_change_winner_and_preference_pair(fake_llm_client):
    llm = fake_llm_client(
        [
            _score(1, 1, 1, casel={"自我觉察引导": 0, "关系技能培养": 0}),
            _score(1, 1, 1, casel={"自我觉察引导": 2, "关系技能培养": 2}),
        ]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [
                _candidate("c1", "我能理解你。"),
                _candidate("c2", "听起来你很受伤，也可以想想怎么表达你的在意。"),
            ],
            activated_casel=["自我觉察引导", "关系技能培养"],
        )
    )

    assert response.scores[0].weighted_total == 3.0
    assert response.scores[1].weighted_total == 4.0
    assert response.best_candidate_id == "c2"
    assert response.preference_pair is not None
    assert response.preference_pair.winner_id == "c2"
    assert response.preference_pair.loser_id == "c1"


@pytest.mark.asyncio
async def test_single_activated_casel_dimension_uses_mean_without_edge_case(
    fake_llm_client,
):
    llm = fake_llm_client([_score(1, 1, 1, casel={"自我觉察引导": 2})])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [_candidate("c1", "听起来你很难受，也能感觉到你在努力撑着。")],
            activated_casel=["自我觉察引导"],
        )
    )

    assert response.scores[0].casel == {"自我觉察引导": 2}
    assert response.scores[0].weighted_total == 4.0


@pytest.mark.asyncio
async def test_casel_rubric_is_added_to_prompt_when_activated(fake_llm_client):
    llm = fake_llm_client([_score(1, 1, 1, casel={"自我觉察引导": 2})])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    await service.evaluate(
        _request(
            [_candidate("c1", "听起来你很难受。")],
            activated_casel=["自我觉察引导"],
        )
    )

    prompt = llm.prompts[0]["prompt"]
    assert "【CASEL 辅助维度" in prompt
    assert "自我觉察引导" in prompt
    assert '"casel"' in prompt


@pytest.mark.asyncio
async def test_critic_prompt_marks_prompt_leaks_and_fabrication_as_boundaries(
    fake_llm_client,
):
    llm = fake_llm_client([_score(1, 1, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    await service.evaluate(_request([_candidate("c1", "你心里那股委屈会很重。")]))

    prompt = llm.prompts[0]["prompt"]
    assert "内部提示外泄" in prompt
    assert "prompt 痕迹" in prompt
    assert "面向开发者或教师的元话术" in prompt
    assert "事实编造" in prompt
    assert "把用户未提及的第三方动机写成事实" in prompt
    assert "即使 ER/IP/EX 分数较高" in prompt


@pytest.mark.asyncio
async def test_critic_prompt_contains_f9_reliability_guardrails(fake_llm_client):
    llm = fake_llm_client([_score(1, 1, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    await service.evaluate(
        _request([_candidate("c1", "说明你很在乎这段关系，先缓一缓也没关系。")])
    )

    prompt = llm.prompts[0]["prompt"]
    assert "IP=2 只给有文本依据的隐含情绪或担忧命名" in prompt
    assert "无依据动机推断、人格结论或因果解释不能算 IP=2" in prompt
    assert "如果主要信息来自换词复述、泛化安抚或品质化夸奖" in prompt
    assert "关系决策风险单独处理" in prompt
    assert "具体、低压、学生能直接回答的二选一问题本身不应被惩罚" in prompt
    assert '"audit_tags"' in prompt
    assert "template_low_information" in prompt
    assert "unsupported_fact_completion" in prompt
    assert "hard_boundary_fabrication" in prompt
    assert "low_pressure_binary_question" in prompt
    assert "只有学生可以不加推理直接回答的具体二选一" in prompt
    assert "说明你真的很在乎" in prompt
    assert "先停在这儿也没关系" in prompt
    assert '例如："唯一的空档"' in prompt
    assert '例如："三科作业"' in prompt
    assert "先判定 audit_tags，再给 ER/IP/EX" in prompt
    assert "旁观者在描述他的状态" in prompt
    assert "有人在陪我、在乎我" in prompt
    assert "气死了" in prompt
    assert "是不是我哪里不好" in prompt
    assert "孩子没有明说、但藏在话里的情绪或担忧" in prompt


def test_f9_unsupported_fact_completion_caps_without_boundary():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": 2,
            "IP": 2,
            "EX": 1,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "补出了用户没有说过的时间段或社交位置。",
            "audit_tags": ["unsupported_fact_completion"],
        }
    )

    assert capped["ER"] == 1
    assert capped["IP"] == 1
    assert capped["EX"] == 1
    assert capped["boundary_flag"] is False
    assert capped["boundary_reason"] == ""


def test_f9_hard_boundary_fabrication_forces_boundary():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": 2,
            "IP": 2,
            "EX": 1,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "编造了用户未提及的科目数量和排序。",
            "audit_tags": ["hard_boundary_fabrication"],
        }
    )

    assert capped["boundary_flag"] is True
    assert capped["boundary_reason"] == "hard_boundary_fabrication"
    assert capped["ER"] == 1
    assert capped["IP"] == 1


def test_f9_multiple_tags_compound_effect():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": 2,
            "IP": 2,
            "EX": 2,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "把愤怒重构成主见，同时替同学解释动机。",
            "audit_tags": ["forced_positive_reframe", "third_party_excuse"],
        }
    )

    assert capped["ER"] == 1
    assert capped["IP"] == 0
    assert capped["EX"] == 2
    assert capped["boundary_flag"] is False


def test_f9_adult_coaching_question_caps_ex():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": 2,
            "IP": 2,
            "EX": 2,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "成人 coaching 式追问。",
            "audit_tags": ["adult_coaching_question"],
        }
    )

    assert capped["ER"] == 2
    assert capped["IP"] == 2
    assert capped["EX"] == 1


def test_f9_score_caps_defensively_normalize_invalid_scores():
    capped = CriticService._apply_f9_score_caps(
        {
            "ER": "2",
            "IP": None,
            "EX": 5,
            "casel": {},
            "boundary_flag": False,
            "boundary_reason": "",
            "rationale": "非法分数输入。",
            "audit_tags": ["template_low_information"],
        }
    )

    assert capped["ER"] == 1
    assert capped["IP"] == 0
    assert capped["EX"] == 0
