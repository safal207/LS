from app.policy import assess_policy, stricter_decision


def test_read_only_action_can_be_allowed():
    result = assess_policy({"action": "Generate read-only report", "metadata": {"reversible": True}})
    assert result.floor_decision == "ALLOW"


def test_external_action_requires_human():
    result = assess_policy({"action": "Send email to customer", "metadata": {"reversible": True}})
    assert result.floor_decision == "HUMAN_APPROVAL"


def test_destructive_production_action_is_blocked():
    result = assess_policy({"action": "Delete production database", "metadata": {"reversible": False}})
    assert result.floor_decision == "BLOCK"


def test_model_cannot_weaken_policy_floor():
    assert stricter_decision("BLOCK", "ALLOW") == "BLOCK"
    assert stricter_decision("HUMAN_APPROVAL", "ALLOW") == "HUMAN_APPROVAL"
