from ls.cognition import TriSignalCore, TriSignalInput


core = TriSignalCore()


def test_explicit_yes_want_meaningful() -> None:
    result = core.detect(TriSignalInput(utterance="Yes, I want this. It is meaningful and worth it."))

    assert result.agreement_signal == "yes"
    assert result.desire_signal == "want"
    assert result.meaning_signal == "meaningful"
    assert result.agreement_confidence == 0.8
    assert result.desire_confidence == 0.8
    assert result.meaning_confidence == 0.8


def test_explicit_yes_dont_want_meaningful() -> None:
    result = core.detect(TriSignalInput(utterance="Да, это важно, но не хочу."))

    assert result.agreement_signal == "yes"
    assert result.desire_signal == "dont_want"
    assert result.meaning_signal == "meaningful"
    assert "agreement_desire_mismatch" in result.tension_flags


def test_explicit_no_want_meaningful() -> None:
    result = core.detect(TriSignalInput(utterance="No, but I want this because it is meaningful."))

    assert result.agreement_signal == "no"
    assert result.desire_signal == "want"
    assert result.meaning_signal == "meaningful"


def test_triple_neutral() -> None:
    result = core.detect(TriSignalInput(utterance="Let's revisit this later when we have data."))

    assert result.agreement_signal == "neutral"
    assert result.desire_signal == "neutral"
    assert result.meaning_signal == "neutral"
    assert result.agreement_confidence == 0.3
    assert result.desire_confidence == 0.3
    assert result.meaning_confidence == 0.3
    assert result.tension_flags == ["triple_neutral"]


def test_negative_markers_override_naive_positive_substrings() -> None:
    result = core.detect(TriSignalInput(utterance="Я не хочу, хотя хочу результата."))

    assert result.desire_signal == "dont_want"
    assert "не хочу" in result.supporting_markers["desire"]


def test_tension_flags_for_mismatch_cases() -> None:
    result = core.detect(TriSignalInput(utterance="Yes, I want this, but it is pointless."))

    assert result.agreement_signal == "yes"
    assert result.desire_signal == "want"
    assert result.meaning_signal == "meaningless"
    assert "desire_meaning_mismatch" in result.tension_flags
    assert "agreement_meaning_mismatch" in result.tension_flags


def test_detect_searches_all_payload_fields_and_as_dict() -> None:
    result = core.detect(
        TriSignalInput(
            utterance="Signals may be elsewhere.",
            task_intent="Need to align soon.",
            scene_context="It is worth it in the long run.",
            recent_memory=("yes",),
        )
    )

    assert result.agreement_signal == "yes"
    assert result.meaning_signal == "meaningful"

    data = result.as_dict()
    assert data["agreement_signal"] == "yes"
    assert data["meaning_signal"] == "meaningful"
    assert isinstance(data["supporting_markers"], dict)
