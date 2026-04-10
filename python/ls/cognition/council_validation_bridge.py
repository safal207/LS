"""Bridge between ResonanceAgent council artifacts and the validation pipeline.

Converts council contribution ledger participants into CandidateAnswer objects
so that the CollectiveAnswerValidator can score, trace, and govern council
decisions post-hoc.

Usage:

    from ls.cognition.council_validation_bridge import validate_council_artifact

    result = validate_council_artifact(quality_artifact_path, governance=True)
    print(result.winner_agent_id, result.consensus_status)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
    ValidationResult,
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _participant_to_candidate(
    participant: dict[str, Any],
    *,
    outcome: dict[str, Any],
) -> CandidateAnswer:
    """Convert a council participant dict into a CandidateAnswer.

    Mapping:
      - agent_id ← model_id
      - answer_text ← proposal_summary
      - relevance ← confidence (participant's self-reported confidence)
      - thread_relevance ← weight_in_final_decision (how much the council used it)
      - hallucination_risk ← inverted from outcome success + confidence
      - supports/contradicts ← inferred from selected status
    """
    model_id = str(participant.get("model_id") or "unknown")
    proposal = str(participant.get("proposal_summary") or "")
    confidence = _clamp(float(participant.get("confidence") or 0.5))
    weight = _clamp(float(participant.get("weight_in_final_decision") or 0.0))
    selected = bool(participant.get("selected"))

    # Hallucination risk: low if selected with high confidence, higher otherwise
    success = bool(outcome.get("success"))
    if selected and success:
        hallucination_risk = _clamp(0.15 - 0.1 * confidence)
    elif selected:
        hallucination_risk = _clamp(0.30 - 0.1 * confidence)
    else:
        hallucination_risk = _clamp(0.50 - 0.2 * confidence)

    return CandidateAnswer(
        agent_id=model_id,
        answer_text=proposal,
        relevance=confidence,
        thread_relevance=max(weight, 0.30) if selected else weight,
        hallucination_risk=hallucination_risk,
    )


def candidates_from_ledger(ledger: dict[str, Any]) -> list[CandidateAnswer]:
    """Extract CandidateAnswer list from a council contribution ledger dict."""
    participants = ledger.get("participants") or []
    outcome = ledger.get("outcome") or {}

    candidates = []
    seen_ids: set[str] = set()
    for p in participants:
        if not isinstance(p, dict):
            continue
        model_id = str(p.get("model_id") or "")
        if not model_id or model_id in seen_ids:
            continue
        seen_ids.add(model_id)
        candidates.append(_participant_to_candidate(p, outcome=outcome))

    return candidates


def task_prompt_from_ledger(ledger: dict[str, Any]) -> str:
    """Extract a task prompt from the ledger's goal summary."""
    goal = ledger.get("goal") or {}
    return str(goal.get("summary") or "Council coordination cycle")


def validate_council_ledger(
    ledger: dict[str, Any],
    *,
    governance: bool = False,
    trace: bool = False,
    sign: bool = False,
) -> ValidationResult:
    """Validate a council contribution ledger through the full pipeline.

    Parameters
    ----------
    ledger:
        Parsed council contribution ledger dict (from the JSON artifact).
    governance:
        Enable governance engine for reputation tracking.
    trace:
        Attach a Lifetra trajectory trace.
    sign:
        Sign the trace artifact with a generated Ed25519 key pair.

    Returns
    -------
    ValidationResult with ranked candidates, consensus status, and optional
    trace/governance attachments.
    """
    candidates = candidates_from_ledger(ledger)
    if not candidates:
        return ValidationResult(
            ranked_candidates=[],
            winner_agent_id=None,
            consensus_status="rejected",
            consensus_summary="No participants found in council ledger.",
            global_risk_flags=["empty_council"],
        )

    task_prompt = task_prompt_from_ledger(ledger)

    trace_backend = None
    governance_engine = None

    if trace:
        from ls.cognition.lifetra_validation_adapter import LifetraValidationAdapter  # noqa: PLC0415

        trace_backend = LifetraValidationAdapter()

    if governance:
        from ls.cognition.validation_governance import (  # noqa: PLC0415
            InMemoryValidationHistoryStore,
            ValidationGovernanceEngine,
        )

        store = InMemoryValidationHistoryStore()
        governance_engine = ValidationGovernanceEngine(history_store=store)

    validator = CollectiveAnswerValidator(
        trace_backend=trace_backend,
        governance_engine=governance_engine,
    )
    payload = ValidationInput(task_prompt=task_prompt, candidates=candidates)
    result = validator.validate(payload)

    if sign and result.trace_artifact is not None:
        try:
            from ls.cognition.ltp_trace_signer import (  # noqa: PLC0415
                generate_key_pair,
                sign_trace_artifact,
            )
            from dataclasses import replace  # noqa: PLC0415

            priv, _pub = generate_key_pair()
            signed = sign_trace_artifact(result.trace_artifact, priv)
            result = replace(result, trace_artifact=signed)
        except Exception:  # noqa: BLE001
            pass

    return result


def validate_council_artifact(
    artifact_path: str | Path,
    *,
    governance: bool = False,
    trace: bool = False,
    sign: bool = False,
) -> ValidationResult:
    """Load a council quality artifact from disk and validate its ledger.

    The artifact is expected to contain a council_ledger_path field pointing
    to the full ledger JSON.  Falls back to using the artifact's own data
    if the ledger path is missing.
    """
    path = Path(artifact_path)
    quality_data = json.loads(path.read_text(encoding="utf-8"))

    # Try loading the full ledger from the referenced path
    ledger_path = quality_data.get("council_ledger_path")
    if ledger_path and Path(ledger_path).exists():
        ledger = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    else:
        # Use the quality artifact data directly (has outcome, attribution)
        ledger = quality_data

    return validate_council_ledger(
        ledger,
        governance=governance,
        trace=trace,
        sign=sign,
    )
