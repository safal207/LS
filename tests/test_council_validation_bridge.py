from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ls.cognition.collective_answer_validator import ValidationResult
from ls.cognition.council_validation_bridge import (
    candidates_from_ledger,
    task_prompt_from_ledger,
    validate_council_artifact,
    validate_council_ledger,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _sample_ledger() -> dict:
    """Realistic council contribution ledger with 3 participants."""
    return {
        "cycle_id": "cycle-001",
        "task_id": "task-001",
        "goal": {
            "type": "coordination_cycle",
            "summary": "Which deployment strategy for the new release?",
        },
        "participants": [
            {
                "model_id": "strategy:gradual-rollout",
                "model_type": "advisory_strategy",
                "proposal_id": "gradual-rollout",
                "proposal_summary": "Gradual rollout with feature flags and 10% canary.",
                "route_hint": "primary",
                "confidence": 0.85,
                "latency_ms": 120,
                "token_cost": 0.0,
                "selected": True,
                "weight_in_final_decision": 0.6,
            },
            {
                "model_id": "strategy:blue-green",
                "model_type": "advisory_strategy",
                "proposal_id": "blue-green",
                "proposal_summary": "Blue-green deployment with instant cutover.",
                "route_hint": "primary",
                "confidence": 0.72,
                "latency_ms": 95,
                "token_cost": 0.0,
                "selected": False,
                "weight_in_final_decision": 0.1,
            },
            {
                "model_id": "openai:gpt-4o",
                "model_type": "primary_llm",
                "proposal_id": "route:primary",
                "proposal_summary": "I recommend gradual rollout with monitoring.",
                "route_hint": "primary",
                "confidence": 0.90,
                "latency_ms": 1800,
                "token_cost": 0.0,
                "selected": True,
                "weight_in_final_decision": 1.0,
            },
        ],
        "outcome": {
            "success": True,
            "path_quality": 0.78,
            "network_improvement": 0.15,
            "operator_intervention_required": False,
            "receiver_resonance_score": 0.82,
            "receiver_acceptance_label": "accepted",
        },
        "final_decision": {
            "selected_route": "primary",
            "decision_summary": "Gradual rollout selected.",
        },
    }


def _failed_ledger() -> dict:
    """Ledger where the outcome was unsuccessful."""
    ledger = _sample_ledger()
    ledger["outcome"] = {
        "success": False,
        "path_quality": 0.30,
        "receiver_resonance_score": 0.35,
        "receiver_acceptance_label": "rejected",
    }
    return ledger


def _write_artifact(ledger: dict) -> str:
    """Write a quality artifact JSON file pointing to a ledger."""
    # Write ledger
    ledger_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="ledger-", delete=False
    )
    json.dump(ledger, ledger_file)
    ledger_file.close()

    # Write quality artifact referencing the ledger
    quality = {
        "cycle_id": ledger.get("cycle_id", "unknown"),
        "council_ledger_path": ledger_file.name,
        "quality_score": 0.75,
    }
    quality_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="quality-", delete=False
    )
    json.dump(quality, quality_file)
    quality_file.close()

    return quality_file.name


# ── candidates_from_ledger ───────────────────────────────────────────────────


def test_candidates_from_ledger_extracts_all_participants():
    candidates = candidates_from_ledger(_sample_ledger())
    assert len(candidates) == 3
    ids = {c.agent_id for c in candidates}
    assert ids == {"strategy:gradual-rollout", "strategy:blue-green", "openai:gpt-4o"}


def test_candidates_from_ledger_deduplicates():
    ledger = _sample_ledger()
    # Duplicate participant
    ledger["participants"].append(ledger["participants"][0])
    candidates = candidates_from_ledger(ledger)
    assert len(candidates) == 3


def test_candidates_relevance_matches_confidence():
    candidates = candidates_from_ledger(_sample_ledger())
    by_id = {c.agent_id: c for c in candidates}
    assert by_id["openai:gpt-4o"].relevance == 0.90
    assert by_id["strategy:gradual-rollout"].relevance == 0.85


def test_candidates_selected_get_higher_thread_relevance():
    candidates = candidates_from_ledger(_sample_ledger())
    by_id = {c.agent_id: c for c in candidates}
    # Selected with weight 0.6 → thread_relevance = 0.6
    assert by_id["strategy:gradual-rollout"].thread_relevance == 0.6
    # Not selected with weight 0.1 → stays at 0.1
    assert by_id["strategy:blue-green"].thread_relevance == 0.1


def test_candidates_hallucination_risk_lower_for_selected_success():
    candidates = candidates_from_ledger(_sample_ledger())
    by_id = {c.agent_id: c for c in candidates}
    # Selected + success → low risk
    assert by_id["openai:gpt-4o"].hallucination_risk < 0.15
    # Not selected → higher risk
    assert by_id["strategy:blue-green"].hallucination_risk > by_id["openai:gpt-4o"].hallucination_risk


def test_candidates_from_empty_ledger():
    candidates = candidates_from_ledger({})
    assert candidates == []


def test_candidates_from_ledger_skips_invalid_participants():
    ledger = {"participants": ["not-a-dict", None, 42]}
    candidates = candidates_from_ledger(ledger)
    assert candidates == []


# ── task_prompt_from_ledger ──────────────────────────────────────────────────


def test_task_prompt_from_ledger():
    prompt = task_prompt_from_ledger(_sample_ledger())
    assert "deployment" in prompt.lower()


def test_task_prompt_fallback():
    prompt = task_prompt_from_ledger({})
    assert prompt == "Council coordination cycle"


# ── validate_council_ledger ──────────────────────────────────────────────────


def test_validate_council_ledger_basic():
    result = validate_council_ledger(_sample_ledger())
    assert isinstance(result, ValidationResult)
    assert result.winner_agent_id is not None
    assert result.consensus_status in {"convergent", "weak", "conflicted", "rejected"}


def test_validate_council_ledger_winner_is_a_participant():
    ledger = _sample_ledger()
    result = validate_council_ledger(ledger)
    participant_ids = {p["model_id"] for p in ledger["participants"]}
    assert result.winner_agent_id in participant_ids


def test_validate_council_ledger_with_governance():
    result = validate_council_ledger(_sample_ledger(), governance=True)
    assert result.governance_report is not None
    assert isinstance(result.governance_report.review_required, bool)


def test_validate_council_ledger_empty_participants():
    result = validate_council_ledger({"participants": []})
    assert result.consensus_status == "rejected"
    assert "empty_council" in result.global_risk_flags


def test_validate_council_ledger_failed_outcome():
    result = validate_council_ledger(_failed_ledger())
    assert result is not None
    # Failed outcome → higher hallucination risk → potentially different status
    assert result.consensus_status in {"convergent", "weak", "conflicted", "rejected"}


# ── validate_council_artifact (file-based) ───────────────────────────────────


def test_validate_council_artifact_from_file():
    path = _write_artifact(_sample_ledger())
    result = validate_council_artifact(path)
    assert result.winner_agent_id is not None
    Path(path).unlink(missing_ok=True)


def test_validate_council_artifact_with_governance():
    path = _write_artifact(_sample_ledger())
    result = validate_council_artifact(path, governance=True)
    assert result.governance_report is not None
    Path(path).unlink(missing_ok=True)


def test_validate_council_artifact_missing_ledger_path():
    """Quality artifact without council_ledger_path uses own data."""
    quality = {
        "cycle_id": "cycle-fallback",
        "participants": _sample_ledger()["participants"],
        "outcome": _sample_ledger()["outcome"],
        "goal": _sample_ledger()["goal"],
    }
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(quality, tmp)
    tmp.close()

    result = validate_council_artifact(tmp.name)
    assert result.winner_agent_id is not None
    Path(tmp.name).unlink()


def test_validate_council_artifact_file_not_found():
    with pytest.raises(FileNotFoundError):
        validate_council_artifact("/nonexistent/artifact.json")


# ── Integration: full pipeline ───────────────────────────────────────────────


def test_full_pipeline_with_signing():
    result = validate_council_ledger(_sample_ledger(), governance=True, sign=True)
    # sign=True only works when trace=True too (no trace → no artifact to sign)
    # This tests graceful handling: no trace backend → no crash
    assert result.winner_agent_id is not None


def test_full_pipeline_all_flags():
    """All flags enabled — graceful even without lifetra_py installed."""
    result = validate_council_ledger(
        _sample_ledger(),
        governance=True,
        trace=True,
        sign=True,
    )
    assert result.winner_agent_id is not None
    # Governance is always available
    assert result.governance_report is not None
    # Trace may be None if lifetra_py not installed (graceful)
