from __future__ import annotations

from agent.cognition import CognitiveTransaction, CreationFeedbackLayer, FLOW_CHANNELS


def _tx(action: str, payload: dict | None = None) -> CognitiveTransaction:
    return CognitiveTransaction.create(actor="agent", action=action, payload=payload or {})


def test_creation_feedback_layer_tracks_score_and_trajectory() -> None:
    layer = CreationFeedbackLayer()

    idea_tx = _tx("idea_created")
    commit_tx = _tx("code_commit", {"parent_idea_tx_id": idea_tx.tx_id})
    resolve_tx = _tx("decision_resolved", {"parent_idea_tx_id": idea_tx.tx_id})

    assert layer.ingest_transaction(idea_tx) is True
    assert layer.ingest_transaction(commit_tx) is True
    assert layer.ingest_transaction(resolve_tx) is True

    snapshot = layer.snapshot()

    assert snapshot["creation_score"] == 5.5
    assert snapshot["events_total"] == 3
    assert snapshot["counts"] == {
        "idea_created": 1,
        "code_commit": 1,
        "decision_resolved": 1,
    }
    assert [point["score"] for point in snapshot["trajectory"]] == [1.0, 3.5, 5.5]
    assert snapshot["idea_lineage"] == {idea_tx.tx_id: [commit_tx.tx_id, resolve_tx.tx_id]}


def test_creation_feedback_layer_ignores_non_creation_actions() -> None:
    layer = CreationFeedbackLayer()

    approved = _tx("approve_proposal", {"proposal_id": "p1", "data": {"ok": True}})

    assert layer.ingest_transaction(approved) is False
    assert layer.process_micro_step(approved) is None

    snapshot = layer.snapshot()
    assert snapshot["creation_score"] == 0.0
    assert snapshot["events_total"] == 0
    assert snapshot["trajectory"] == []


def test_creation_feedback_layer_builds_full_ls_flow_visualization() -> None:
    layer = CreationFeedbackLayer()
    layer.ingest_transaction(_tx("idea_created"))
    snapshot = layer.snapshot()

    flow = snapshot["flow_visualization"]
    assert flow["channels"] == list(FLOW_CHANNELS)
    assert flow["summary"]["creation_score"] == 1.0
    assert flow["summary"]["events_total"] == 1
    assert any(node["id"] == "mel" for node in flow["nodes"])
    assert any(node["id"] == "cel" for node in flow["nodes"])
    assert any(node["id"] == "cem" for node in flow["nodes"])
    assert any(node["id"] == "ctl" for node in flow["nodes"])
    assert any(node["id"] == "ltp" for node in flow["nodes"])
    assert any(edge["source"] == "artifact" and edge["target"] == "mel" for edge in flow["edges"])


def test_creation_feedback_layer_renders_mermaid_diagram() -> None:
    layer = CreationFeedbackLayer()

    graph = layer.mermaid_diagram()

    assert graph.startswith("flowchart TD")
    assert "artifact -->|economy| mel" in graph
    assert "cel -->|knowledge| cem" in graph
    assert "ltp -->|dopamine| next_cue" in graph


def test_process_micro_step_emits_reflection_cel_and_ltp_updates() -> None:
    layer = CreationFeedbackLayer()
    tx = _tx("code_commit", {"trace_id": "trace_commit_1"})

    feedback = layer.process_micro_step(tx, quality_score=0.8)

    assert feedback is not None
    assert feedback.action == "code_commit"
    assert feedback.micro_reward > 0
    assert feedback.prediction_error > 0
    assert feedback.reflection_event["type"] == "reflection_micro_reward"
    assert feedback.cel_decision_payload["type"] == "cel_decision_micro"
    assert feedback.cel_decision_payload["trace_id"] == "trace_commit_1"
    assert feedback.ltp_update["type"] == "ltp_growth_update"
    assert feedback.ltp_score > 0

    actor_profile = layer.snapshot()["actor_profiles"]["agent"]
    assert actor_profile["ltp_score"] == feedback.ltp_score


def test_process_micro_step_rejects_invalid_quality_score() -> None:
    layer = CreationFeedbackLayer()
    tx = _tx("code_commit")

    try:
        layer.process_micro_step(tx, quality_score=1.5)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "quality_score" in str(exc)
