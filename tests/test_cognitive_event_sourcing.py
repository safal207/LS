from agent.cognition import (
    CognitiveEventMesh,
    CognitiveIdentity,
    CognitiveReducer,
    CognitiveStore,
    CognitiveTransaction,
    CognitiveTransactionLog,
    LTPEnvelope,
)
from agent.decision_pipeline import DecisionPipeline


def test_transaction_log_and_store_rebuild_state() -> None:
    events = []
    mesh = CognitiveEventMesh()
    mesh.subscribe(lambda tx: events.append(tx.action))
    log = CognitiveTransactionLog(event_mesh=mesh)
    store = CognitiveStore(log, CognitiveReducer(), initial_state={"canonical": {}, "rejected": []})

    log.append(CognitiveTransaction.create("human", "approve_proposal", {"proposal_id": "p1", "data": {"value": 1}}))
    log.append(CognitiveTransaction.create("human", "reject_proposal", {"proposal_id": "p2"}))
    store.rebuild()

    assert events == ["approve_proposal", "reject_proposal"]
    assert store.snapshot()["canonical"]["p1"] == {"value": 1}
    assert "p2" in store.snapshot()["rejected"]


def test_ltp_envelope_from_transaction() -> None:
    tx = CognitiveTransaction.create("agent", "belief_update", {"op": "set", "key": "x", "value": 1})
    env = LTPEnvelope.from_transaction(tx, sender="did:agent:a", receiver="did:agent:b", signing_key="k")

    assert env.event == "belief_update"
    assert env.payload["tx_id"] == tx.tx_id
    assert env.signature


def test_cognitive_identity_roundtrip() -> None:
    identity = CognitiveIdentity.create(creator="GasipasaLab", capabilities=["energy_forecasting"])
    clone = CognitiveIdentity.from_dict(identity.to_dict())

    assert clone.agent_id.startswith("did:agent:")
    assert clone.creator == "GasipasaLab"
    assert "energy_forecasting" in clone.capabilities


def test_decision_pipeline_writes_cognitive_timeline_and_outbox() -> None:
    state = {"causal_edges": []}
    pipeline = DecisionPipeline(state)

    pipeline.run([{"type": "decision", "value": "any"}])

    assert pipeline.cognitive_transaction_log.size() > 0
    assert pipeline.cognitive_state["cognitive_timeline"]
    assert pipeline.cognitive_state["cognitive_network_outbox"]
    snapshot = pipeline.get_visualization_snapshot()
    assert snapshot["cognitive_identity"]["agent_id"].startswith("did:agent:")
