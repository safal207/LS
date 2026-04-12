from __future__ import annotations

from modules.council.council_engine import RelationalCouncilEngine
from modules.council.self_constitution import RelationalSelfConstitution
from modules.graph.models import RelationalSelf


def test_constitution_evaluate_passes_for_healthy_self():
    rs = RelationalSelf(
        self_coherence_score=0.75,
        core_nodes=[{"alignment_score": 0.7}, {"alignment_score": 0.8}],
        core_edges=[
            {"relation_type": "reinforces", "strength": 0.8},
            {"relation_type": "reinforces", "strength": 0.6},
        ],
    )
    evaluation = RelationalSelfConstitution().evaluate(rs)
    assert evaluation.passed is True
    assert len(evaluation.findings) == 3
    payload = evaluation.to_dict()
    assert payload["schema_version"] == "1.0"
    assert payload["findings"][0]["rule_id"].startswith("rs.constitution.")
    assert payload["findings"][0]["reason_code"].endswith("_ok")


def test_self_preservation_blocks_on_constitution_violation():
    rs = RelationalSelf(
        self_coherence_score=0.5,
        core_nodes=[{"alignment_score": 0.1}],
        core_edges=[
            {"relation_type": "contradicts", "strength": 0.9},
            {"relation_type": "contradicts", "strength": 0.85},
        ],
    )
    outcome = RelationalCouncilEngine(coherence_guard_threshold=0.2).run_mode(
        mode="self-preservation",
        relational_self=rs,
    )
    assert outcome["blocked"] is True
    assert outcome["reason"] == "constitution_violation"
    assert outcome["constitution"]["passed"] is False
