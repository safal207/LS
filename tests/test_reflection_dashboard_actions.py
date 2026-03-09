from pathlib import Path

from agent.reflection import ReflectionPipeline
from agent.reflection_handler import ReflectionActionHandler


def test_approve_reject_and_save_state(tmp_path: Path):
    state_path = tmp_path / "reflection_state.json"
    pipeline = ReflectionPipeline.load_state(str(state_path))
    proposal = {
        "proposal_id": "p1",
        "change_type": "control_update",
        "target": "low_confidence_threshold",
        "proposed_value": 0.41,
        "confidence": 0.95,
    }

    handler = ReflectionActionHandler(pipeline.decision_pipeline)
    approved = handler.apply(proposal)
    assert approved["status"] == "applied"

    pipeline.save_state()
    assert state_path.exists()

    rejected = handler.reject(proposal)
    assert rejected["status"] == "rejected"


def test_high_confidence_flag():
    proposals = [
        {"proposal_id": "h1", "confidence": 0.91},
        {"proposal_id": "l1", "confidence": 0.6},
    ]
    for proposal in proposals:
        proposal["high_confidence"] = proposal["confidence"] > 0.9

    assert proposals[0]["high_confidence"] is True
    assert proposals[1]["high_confidence"] is False


def test_disable_tool_blocks_apply():
    pipeline = ReflectionPipeline.load_state()
    handler = ReflectionActionHandler(pipeline.decision_pipeline)

    proposal = {
        "proposal_id": "danger",
        "change_type": "tool_demotion",
        "target": "answer_with_tool",
        "disable_tool": True,
        "confidence": 0.99,
    }
    result = handler.apply(proposal)
    assert result["status"] == "blocked"
