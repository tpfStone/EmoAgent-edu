import json

from app.config import Settings
from app.services.f3_support_service import F3SupportService, tokenize_for_support


def _write_rows(tmp_path, rows):
    path = tmp_path / "psyqa_labelled.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def test_f3_support_service_builds_strategy_prior_and_support_cards(tmp_path):
    path = _write_rows(
        tmp_path,
        [
            {
                "source_index": 1,
                "status": "ok",
                "use_tier": "direct_exemplar",
                "scenario": "同伴关系",
                "quality_label": "good",
                "safety_level": "green",
                "input": "同学周末出去玩没有叫我，我翻了好几遍群消息。",
                "psyqa_strategy_sequence": [
                    "Restatement",
                    "Approval and Reassurance",
                    "Interpretation",
                    "Direct Guidance",
                ],
                "psyqa_strategy_segments": [
                    {
                        "strategy": "Restatement",
                        "text": "你翻了好几遍群消息，发现他们出去玩没有叫你。",
                    },
                    {
                        "strategy": "Approval and Reassurance",
                        "text": "那种被落下的感觉会很堵。",
                    },
                    {
                        "strategy": "Direct Guidance",
                        "text": "你可以主动去问问他们。",
                    },
                ],
            },
            {
                "source_index": 2,
                "status": "ok",
                "use_tier": "strategy_reference",
                "scenario": "同伴关系",
                "quality_label": "rewrite",
                "safety_level": "green",
                "input": "朋友突然不回我消息，我担心自己被讨厌。",
                "psyqa_strategy_sequence": [
                    "Approval and Reassurance",
                    "Interpretation",
                    "Direct Guidance",
                ],
                "psyqa_strategy_segments": [
                    {
                        "strategy": "Interpretation",
                        "text": "你在意的可能不是一条消息，而是自己是不是被排除在外。",
                    }
                ],
            },
        ],
    )
    service = F3SupportService(
        Settings(F3_PSYQA_LABELLED_PATH=str(path), F3_SUPPORT_TOP_K=1)
    )

    context = service.build_context(
        scenario="同伴关系",
        user_message="他们出去玩没叫我，我翻群消息越看越难受。",
        external_examples=[],
    )

    assert "同伴关系 可参考样本 2 条" in context.strategy_prior
    assert "Direct Guidance 虽然在 PsyQA 高频，但第一轮默认延后" in context.strategy_prior
    assert len(context.support_cards) == 1
    assert "source=1" in context.support_cards[0]
    assert "具体复述[Restatement]" in context.support_cards[0]
    assert "不要照搬建议" in context.support_cards[0]


def test_f3_support_service_keeps_external_examples_when_disabled(tmp_path):
    path = _write_rows(tmp_path, [])
    service = F3SupportService(
        Settings(
            F3_SUPPORT_ENABLE=False,
            F3_PSYQA_LABELLED_PATH=str(path),
            F3_SUPPORT_TOP_K=2,
        )
    )

    context = service.build_context(
        scenario="学业压力",
        user_message="我这次考试没考好。",
        external_examples=["外部样例：先具体接住考试失利。"],
    )

    assert context.strategy_prior == ""
    assert "外部样例" in context.support_cards_text


def test_tokenize_for_support_uses_chinese_ngrams():
    tokens = tokenize_for_support("朋友出去玩没叫我")

    assert "朋友" in tokens
    assert "出去" in tokens
    assert "没叫我" in tokens
