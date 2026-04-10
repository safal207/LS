from __future__ import annotations

from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
)
from ls.cognition.validation_governance import (
    InMemoryValidationHistoryStore,
    ValidationGovernanceEngine,
)


def _make_validator(store: InMemoryValidationHistoryStore | None = None) -> CollectiveAnswerValidator:
    history_store = store or InMemoryValidationHistoryStore()
    governance = ValidationGovernanceEngine(history_store=history_store)
    return CollectiveAnswerValidator(governance_engine=governance)


def test_governance_detects_semantic_paraphrase_cluster() -> None:
    store = InMemoryValidationHistoryStore()
    validator = _make_validator(store)
    payload = ValidationInput(
        task_prompt="How should we roll out the release?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-a",
                answer_text="Use a staged rollout with feature flags and active monitoring.",
                relevance=0.86,
                thread_relevance=0.82,
                hallucination_risk=0.08,
            ),
            CandidateAnswer(
                agent_id="agent-b",
                answer_text="Use feature flags, monitoring, and a staged rollout for the release.",
                relevance=0.85,
                thread_relevance=0.81,
                hallucination_risk=0.09,
            ),
        ],
    )

    result = validator.validate(payload)

    assert result.winner_agent_id == "agent-a"
    assert result.governance_report is not None
    assert "semantic_paraphrase_cluster" in result.governance_report.governance_flags
    assert result.governance_report.review_required is True
    clusters = result.governance_report.paraphrase_clusters
    assert len(clusters) == 1
    assert clusters[0].agent_ids == ["agent-a", "agent-b"]


def test_governance_applies_history_aware_score_correction_without_changing_base_winner() -> None:
    store = InMemoryValidationHistoryStore()
    validator = _make_validator(store)

    validator.validate(
        ValidationInput(
            task_prompt="Seed trustworthy history.",
            candidates=[
                CandidateAnswer(
                    agent_id="trusted-agent",
                    answer_text="Use gradual rollout with rollback checkpoints.",
                    relevance=0.93,
                    thread_relevance=0.88,
                    hallucination_risk=0.05,
                ),
                CandidateAnswer(
                    agent_id="risky-agent",
                    answer_text="Ship instantly to all users.",
                    relevance=0.22,
                    thread_relevance=0.20,
                    hallucination_risk=0.72,
                ),
            ],
        )
    )
    validator.validate(
        ValidationInput(
            task_prompt="Seed risky paraphrase behavior.",
            candidates=[
                CandidateAnswer(
                    agent_id="risky-agent",
                    answer_text="Push the release now to everyone without staging.",
                    relevance=0.72,
                    thread_relevance=0.72,
                    hallucination_risk=0.12,
                ),
                CandidateAnswer(
                    agent_id="echo-agent",
                    answer_text="Push the release now to everyone and skip staging.",
                    relevance=0.72,
                    thread_relevance=0.72,
                    hallucination_risk=0.12,
                ),
            ],
        )
    )

    payload = ValidationInput(
        task_prompt="Choose a rollout plan.",
        candidates=[
            CandidateAnswer(
                agent_id="risky-agent",
                answer_text="Roll out with feature flags and monitoring.",
                relevance=0.84,
                thread_relevance=0.80,
                hallucination_risk=0.08,
            ),
            CandidateAnswer(
                agent_id="trusted-agent",
                answer_text="Use gradual rollout with feature flags and rollback checkpoints.",
                relevance=0.82,
                thread_relevance=0.80,
                hallucination_risk=0.08,
            ),
        ],
    )

    result = validator.validate(payload)

    assert result.winner_agent_id == "risky-agent"
    assert result.governance_report is not None
    adjusted = {
        item.agent_id: item
        for item in result.governance_report.adjusted_candidates
    }
    assert adjusted["trusted-agent"].adjusted_score > adjusted["risky-agent"].adjusted_score
    assert result.governance_report.governed_winner_agent_id == "trusted-agent"
    assert "governed_winner_differs_from_base" in result.governance_report.governance_flags
    assert result.governance_report.review_required is True
    assert result.governance_report.escalation_recommendations


def test_governance_persists_reputation_memory_across_rounds() -> None:
    store = InMemoryValidationHistoryStore()
    validator = _make_validator(store)

    validator.validate(
        ValidationInput(
            task_prompt="Round one.",
            candidates=[
                CandidateAnswer(
                    agent_id="agent-a",
                    answer_text="Use a gradual rollout.",
                    relevance=0.90,
                    thread_relevance=0.84,
                    hallucination_risk=0.05,
                ),
                CandidateAnswer(
                    agent_id="agent-b",
                    answer_text="Ship now.",
                    relevance=0.20,
                    thread_relevance=0.20,
                    hallucination_risk=0.70,
                ),
            ],
        )
    )
    result = validator.validate(
        ValidationInput(
            task_prompt="Round two.",
            candidates=[
                CandidateAnswer(
                    agent_id="agent-a",
                    answer_text="Use staged rollout with monitoring.",
                    relevance=0.88,
                    thread_relevance=0.83,
                    hallucination_risk=0.06,
                ),
                CandidateAnswer(
                    agent_id="agent-b",
                    answer_text="Use staged rollout with monitoring too.",
                    relevance=0.80,
                    thread_relevance=0.76,
                    hallucination_risk=0.08,
                ),
            ],
        )
    )

    assert result.governance_report is not None
    profiles = {profile.agent_id: profile for profile in result.governance_report.agent_profiles}
    assert profiles["agent-a"].rounds_seen >= 1
    assert profiles["agent-a"].reputation_score > profiles["agent-b"].reputation_score
    assert profiles["agent-a"].trust_tier in {"watch", "trusted"}


def test_governance_emits_quorum_snapshot_for_trusted_supporters() -> None:
    store = InMemoryValidationHistoryStore()
    validator = _make_validator(store)

    validator.validate(
        ValidationInput(
            task_prompt="Prime trust for agent-a.",
            candidates=[
                CandidateAnswer(
                    agent_id="agent-a",
                    answer_text="Use staged rollout.",
                    relevance=0.92,
                    thread_relevance=0.86,
                    hallucination_risk=0.05,
                ),
            ],
        )
    )
    validator.validate(
        ValidationInput(
            task_prompt="Prime trust for agent-b.",
            candidates=[
                CandidateAnswer(
                    agent_id="agent-b",
                    answer_text="Use monitoring and rollback.",
                    relevance=0.90,
                    thread_relevance=0.84,
                    hallucination_risk=0.05,
                ),
            ],
        )
    )

    result = validator.validate(
        ValidationInput(
            task_prompt="Choose final rollout.",
            candidates=[
                CandidateAnswer(
                    agent_id="agent-a",
                    answer_text="Use staged rollout with feature flags.",
                    relevance=0.88,
                    thread_relevance=0.84,
                    hallucination_risk=0.06,
                ),
                CandidateAnswer(
                    agent_id="agent-b",
                    answer_text="Support agent-a: use staged rollout with feature flags.",
                    relevance=0.82,
                    thread_relevance=0.80,
                    hallucination_risk=0.06,
                    supports=["agent-a"],
                ),
            ],
        )
    )

    assert result.governance_report is not None
    snapshot = result.governance_report.distributed_consensus
    assert snapshot.quorum_reached is True
    assert snapshot.status == "quorum"
    assert snapshot.trusted_support_agent_ids == ["agent-a", "agent-b"]
    assert snapshot.veto_present is False


def test_governance_emits_trusted_veto_when_strong_agent_contradicts_winner() -> None:
    store = InMemoryValidationHistoryStore()
    validator = _make_validator(store)

    validator.validate(
        ValidationInput(
            task_prompt="Prime trust for reviewer.",
            candidates=[
                CandidateAnswer(
                    agent_id="reviewer-agent",
                    answer_text="Use a staged rollout with rollback checkpoints.",
                    relevance=0.93,
                    thread_relevance=0.88,
                    hallucination_risk=0.05,
                ),
            ],
        )
    )

    result = validator.validate(
        ValidationInput(
            task_prompt="Check whether instant rollout is safe.",
            candidates=[
                CandidateAnswer(
                    agent_id="winner-agent",
                    answer_text="Deploy immediately to all users.",
                    relevance=0.85,
                    thread_relevance=0.82,
                    hallucination_risk=0.08,
                ),
                CandidateAnswer(
                    agent_id="reviewer-agent",
                    answer_text="Do not deploy immediately; require staged rollout and rollback checkpoints.",
                    relevance=0.82,
                    thread_relevance=0.80,
                    hallucination_risk=0.06,
                    contradicts=["winner-agent"],
                ),
            ],
        )
    )

    assert result.governance_report is not None
    snapshot = result.governance_report.distributed_consensus
    assert snapshot.veto_present is True
    assert snapshot.status == "vetoed"
    assert snapshot.trusted_contradiction_agent_ids == ["reviewer-agent"]
    assert "trusted_veto_present" in result.governance_report.governance_flags
    assert result.governance_report.review_required is True


def test_governance_detects_repeated_coalition_behavior_across_rounds() -> None:
    store = InMemoryValidationHistoryStore()
    validator = _make_validator(store)

    rounds = [
        (
            "Round one coalition pattern.",
            "Use feature flags and staged rollout for safety.",
            "Use feature flags and staged rollout for release safety.",
        ),
        (
            "Round two coalition pattern.",
            "Use feature flags and staged rollout with safety checks.",
            "Use feature flags and staged rollout for safety checks.",
        ),
        (
            "Round three coalition pattern.",
            "Use feature flags and staged rollout with monitoring for safety.",
            "Use feature flags and staged rollout for safety with monitoring.",
        ),
    ]
    result = None
    for prompt, left_text, right_text in rounds:
        result = validator.validate(
            ValidationInput(
                task_prompt=prompt,
                candidates=[
                    CandidateAnswer(
                        agent_id="agent-a",
                        answer_text=left_text,
                        relevance=0.83,
                        thread_relevance=0.80,
                        hallucination_risk=0.08,
                        supports=["agent-b"],
                        contradicts=["agent-c"],
                    ),
                    CandidateAnswer(
                        agent_id="agent-b",
                        answer_text=right_text,
                        relevance=0.82,
                        thread_relevance=0.79,
                        hallucination_risk=0.08,
                        supports=["agent-a"],
                    ),
                    CandidateAnswer(
                        agent_id="agent-c",
                        answer_text="Do an all-at-once release.",
                        relevance=0.30,
                        thread_relevance=0.30,
                        hallucination_risk=0.40,
                    ),
                ],
            )
        )

    assert result is not None
    assert result.governance_report is not None
    alerts = result.governance_report.coalition_alerts
    assert alerts
    assert alerts[0].agent_ids == ["agent-a", "agent-b"]
    assert alerts[0].severity == "high"
    assert "coalition_risk_detected" in result.governance_report.governance_flags


def test_governance_handles_empty_candidates() -> None:
    # build_governance_report must not crash when no candidates exist.
    validator = _make_validator()
    payload = ValidationInput(task_prompt="Pick the best option.", candidates=[])

    result = validator.validate(payload)

    assert result.consensus_status == "rejected"
    assert result.winner_agent_id is None
    assert result.governance_report is not None
    report = result.governance_report
    assert report.paraphrase_clusters == []
    assert report.coalition_alerts == []
    assert report.adjusted_candidates == []
    assert report.governed_winner_agent_id is None
    assert not report.distributed_consensus.quorum_reached
