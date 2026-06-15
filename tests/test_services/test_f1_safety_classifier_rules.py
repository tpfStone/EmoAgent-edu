from app.services.f1_safety_classifier import apply_soft_rule_postprocess


def _postprocess(candidate_level: str, probabilities: dict[str, float], text: str):
    return apply_soft_rule_postprocess(
        candidate_level,
        probabilities,
        text,
        yellow_or_red_threshold=0.55,
    )


def test_low_confidence_yellow_without_risk_signal_allows_generation():
    level, signals = _postprocess(
        "yellow",
        {"green": 0.4472, "yellow": 0.5522, "red": 0.0006},
        "\u8fd9\u6b21\u6708\u8003\u6ca1\u8003\u597d\uff0c\u5fc3\u60c5\u5f88\u5dee\uff0c\u4e0d\u60f3\u53bb\u5b66\u6821\u4e86\u3002",
    )

    assert level == "green"
    assert signals.signals == []


def test_disappearing_ideation_is_yellow_even_when_model_scores_green():
    level, signals = _postprocess(
        "green",
        {"green": 0.9982, "yellow": 0.0017, "red": 0.0001},
        "\u5982\u679c\u6211\u6d88\u5931\u4e86\uff0c\u5927\u5bb6\u662f\u4e0d\u662f\u5c31\u8f7b\u677e\u4e86\u3002",
    )

    assert level == "yellow"
    assert "passive_death_ideation" in signals.signals


def test_benign_short_greeting_overrides_spurious_red_model_score():
    level, signals = _postprocess(
        "red",
        {"green": 0.0009, "yellow": 0.0004, "red": 0.9987},
        "\u4f60\u597d\u3002",
    )

    assert level == "green"
    assert signals.signals == []


def test_benign_short_acknowledgement_overrides_spurious_red_model_score():
    level, signals = _postprocess(
        "red",
        {"green": 0.4322, "yellow": 0.0040, "red": 0.5638},
        "\u6709\u3002",
    )

    assert level == "green"
    assert signals.signals == []


def test_risk_single_character_is_not_downgraded_as_short_acknowledgement():
    level, signals = _postprocess(
        "red",
        {"green": 0.4322, "yellow": 0.0040, "red": 0.5638},
        "\u836f",
    )

    assert level == "yellow"
    assert signals.signals == []


def test_concrete_self_harm_method_is_red_even_when_model_scores_green():
    level, signals = _postprocess(
        "green",
        {"green": 0.9, "yellow": 0.05, "red": 0.05},
        "\u6211\u4eca\u665a\u60f3\u5403\u836f\u7ed3\u675f\u8fd9\u4e00\u5207\u3002",
    )

    assert level == "red"
    assert "method_signal" in signals.signals
    assert "time_signal" in signals.signals


def test_technical_command_text_without_risk_signal_overrides_spurious_red_model_score():
    level, signals = _postprocess(
        "red",
        {"green": 0.0106, "yellow": 0.0113, "red": 0.9781},
        """cd D:\\projects\\EmoAgent-edu
$env:F1_SAFETY_MODEL_DIR="exp/models/f1_safety_gate/manual-A-pattern-v1"
$env:F1_SAFETY_PRELOAD="true"
$env:F1_SAFETY_REQUIRED="true"
$env:F1_SAFETY_LOCAL_FILES_ONLY="false"
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000""",
    )

    assert level == "green"
    assert signals.signals == []


def test_technical_command_text_with_explicit_crisis_signal_still_blocks():
    level, signals = _postprocess(
        "red",
        {"green": 0.01, "yellow": 0.01, "red": 0.98},
        'python -c "print(\'我今晚想吃药结束这一切。\')"',
    )

    assert level == "red"
    assert "method_signal" in signals.signals
