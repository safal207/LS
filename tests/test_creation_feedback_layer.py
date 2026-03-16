from __future__ import annotations

from agent.cognition import CognitiveTransaction, CreationFeedbackLayer


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

    snapshot = layer.snapshot()
    assert snapshot["creation_score"] == 0.0
    assert snapshot["events_total"] == 0
    assert snapshot["trajectory"] == []
