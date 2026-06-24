"""Verified learning export for the Trusted PR Review product slice."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Optional

from .orientation import OrientationContext, OrientationStage
from .pr_review_mvp import run_trusted_pr_review as run_pr_review_mvp
from .verified_episode import CausalStatus, build_verified_episode


_DIMENSION_ORDER = (
    "intent",
    "authority",
    "evidence",
    "risk",
    "reversibility",
    "accountability",
)

_LESSONS = {
    "allow": {
        "statement": (
            "For this bounded PR-review transition, linked changed-test "
            "evidence and valid authorization supported exactly one protected "
            "review-result effect."
        ),
        "confidence": 0.80,
        "repeat_key": "trusted-pr-review:allow:one-authorized-effect",
    },
    "hold": {
        "statement": (
            "Missing changed-test evidence must keep this PR-review transition "
            "held without authorization, protected effect, or reusable artifact."
        ),
        "confidence": 0.72,
        "repeat_key": "trusted-pr-review:hold:missing-test-evidence",
    },
    "block": {
        "statement": (
            "A prohibited dynamic-execution risk must block this PR-review "
            "transition before authorization or protected effect."
        ),
        "confidence": 0.88,
        "repeat_key": "trusted-pr-review:block:dynamic-execution-risk",
    },
}


def run_trusted_pr_review_with_episode(
    diff_text: str,
    *,
    scenario: str,
    output_dir: Path,
    authorization_expires_at: Optional[str] = None,
) -> dict[str, Any]:
    """Run the product slice and emit one governed learning episode."""

    kwargs: dict[str, Any] = {
        "scenario": scenario,
        "output_dir": output_dir,
    }
    if authorization_expires_at is not None:
        kwargs["authorization_expires_at"] = authorization_expires_at

    result = run_pr_review_mvp(diff_text, **kwargs)
    normalized_scenario = str(result["scenario"])
    root = Path(output_dir)
    orientation = _load_orientation(root / "orientation-context.json")
    replay = _load_replay(root / "replay/replay-record.json", result["replay_ref"])
    expected_outcome, observed_outcome = _episode_outcomes(
        normalized_scenario,
        result,
        orientation,
    )
    lesson = _LESSONS[normalized_scenario]
    episode = build_verified_episode(
        orientation,
        replay=replay,
        expected_outcome=expected_outcome,
        observed_outcome=observed_outcome,
        lesson_statement=lesson["statement"],
        lesson_scope="trusted-pr-review-mvp",
        lesson_confidence=float(lesson["confidence"]),
        lesson_repeat_key=lesson["repeat_key"],
        created_at="2026-06-23T14:10:00Z",
        causal_status=(
            CausalStatus.VALID
            if result["causal_authorization_allowed"]
            else CausalStatus.INVALID
        ),
        minimum_verified_episodes=3,
        current_verified_episodes=1,
        metadata={
            "product_slice": "trusted-pr-review-mvp",
            "scenario": normalized_scenario,
            "replay_drift_accepted": (
                normalized_scenario == "hold"
                and result["replay_decision"] == "DRIFTED"
            ),
            "observed_from": "run_summary_and_durable_product_files",
            "non_claim": "lesson_candidate_is_not_a_global_truth",
        },
    )
    episode_path = root / "verified-episode.json"
    _write_json(episode_path, episode.to_dict())

    enriched = {
        **result,
        "verified_episode_status": episode.status.value,
        "verified_episode_ref": episode.episode_id,
        "verified_episode_path": str(episode_path),
        "lesson_repeat_key": episode.lesson.repeat_key,
        "lesson_confidence": episode.lesson.confidence,
        "identity_update_allowed": episode.identity_update.allowed,
        "identity_update_applied": episode.identity_update.applied,
    }
    _write_json(root / "run-summary.json", enriched)
    return enriched


def _load_orientation(path: Path) -> OrientationContext:
    payload = _read_json(path)
    dimensions = {
        name: str(payload["dimensions"][name]) for name in _DIMENSION_ORDER
    }
    return OrientationContext(
        orientation_id=str(payload["orientation_id"]),
        transition_id=str(payload["transition_id"]),
        task_id=str(payload["task_id"]),
        trail_id=str(payload["trail_id"]),
        actor=str(payload["actor"]),
        intent=str(payload["intent"]),
        created_at=str(payload["created_at"]),
        stage=OrientationStage(str(payload["stage"])),
        role_ids=tuple(str(item) for item in payload["role_ids"]),
        route_refs=tuple(str(item) for item in payload["route_refs"]),
        evidence_refs=tuple(str(item) for item in payload["evidence_refs"]),
        causal_parent_refs=tuple(
            str(item) for item in payload["causal_parent_refs"]
        ),
        dimensions=dimensions,
        actual_state=dict(payload["actual_state"]),
        expected_state=dict(payload["expected_state"]),
        forbidden_deltas=tuple(
            str(item) for item in payload["forbidden_deltas"]
        ),
        constraints=tuple(str(item) for item in payload["constraints"]),
        decision=payload["decision"],
        decision_reason=payload["decision_reason"],
        authorization_ref=payload["authorization_ref"],
        execution_ref=payload["execution_ref"],
        effect_ref=payload["effect_ref"],
        replay_ref=payload["replay_ref"],
        artifact_ref=payload["artifact_ref"],
        metadata=dict(payload["metadata"]),
        schema_version=str(payload["schema_version"]),
    )


def _load_replay(path: Path, report_ref: str) -> Any:
    payload = _read_json(path)
    return SimpleNamespace(
        record=SimpleNamespace(
            task_id=str(payload["task_id"]),
            trail_id=str(payload["trail_id"]),
            replay_id=str(payload["replay_id"]),
            decision=str(payload["decision"]),
        ),
        report_ref=str(report_ref),
    )


def _episode_outcomes(
    scenario: str,
    result: Mapping[str, Any],
    orientation: OrientationContext,
) -> tuple[dict[str, Any], dict[str, Any]]:
    effect_count = len(tuple(result["protected_effect_files"]))
    expected = {
        "decision": scenario.upper(),
        "terminal_stage": {
            "allow": "REPLAYABLE",
            "hold": "HELD",
            "block": "BLOCKED",
        }[scenario],
        "authorization_created": scenario == "allow",
        "protected_effect_count": 1 if scenario == "allow" else 0,
        "artifact_created": scenario == "allow",
    }
    observed = {
        "decision": str(result["decision"]),
        "terminal_stage": orientation.stage.value,
        "authorization_created": bool(result["authorization_created"]),
        "protected_effect_count": effect_count,
        "artifact_created": bool(result["artifact_written"]),
        "replay_status": str(result["replay_decision"]),
    }
    return expected, observed


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


__all__ = ["run_trusted_pr_review_with_episode"]
