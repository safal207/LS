from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
)


def _validator() -> CollectiveAnswerValidator:
    return CollectiveAnswerValidator()


# ──────────────────────────────────────────────
# 1. Clear strong winner
# ──────────────────────────────────────────────
def test_clear_strong_winner():
    payload = ValidationInput(
        task_prompt="What is the capital of France?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-a",
                answer_text="Paris is the capital of France.",
                relevance=0.9,
                thread_relevance=0.85,
                hallucination_risk=0.05,
                supports=["agent-b"],
            ),
            CandidateAnswer(
                agent_id="agent-b",
                answer_text="The capital is Paris.",
                relevance=0.8,
                thread_relevance=0.75,
                hallucination_risk=0.10,
            ),
        ],
    )
    result = _validator().validate(payload)

    assert result.winner_agent_id == "agent-a"
    assert result.consensus_status == "convergent"
    assert len(result.ranked_candidates) == 2
    assert result.ranked_candidates[0].accepted is True
    assert result.ranked_candidates[1].accepted is True
    assert "no_valid_candidates" not in result.global_risk_flags


# ──────────────────────────────────────────────
# 2. All candidates rejected
# ──────────────────────────────────────────────
def test_all_candidates_rejected():
    payload = ValidationInput(
        task_prompt="Explain quantum entanglement.",
        candidates=[
            CandidateAnswer(
                agent_id="agent-x",
                answer_text="I don't know.",
                relevance=0.1,
                thread_relevance=0.1,
                hallucination_risk=0.8,
            ),
            CandidateAnswer(
                agent_id="agent-y",
                answer_text="",
                relevance=0.0,
                thread_relevance=0.0,
                hallucination_risk=0.9,
            ),
        ],
    )
    result = _validator().validate(payload)

    assert result.winner_agent_id is None
    assert result.consensus_status == "rejected"
    assert "no_valid_candidates" in result.global_risk_flags
    assert all(not v.accepted for v in result.ranked_candidates)


# ──────────────────────────────────────────────
# 3. Conflict between top candidates
# ──────────────────────────────────────────────
def test_conflict_between_top_candidates():
    payload = ValidationInput(
        task_prompt="Should we use strategy A or B?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-1",
                answer_text="Use strategy A for better throughput.",
                relevance=0.85,
                thread_relevance=0.80,
                hallucination_risk=0.10,
                contradicts=["agent-2"],
            ),
            CandidateAnswer(
                agent_id="agent-2",
                answer_text="Use strategy B for lower latency.",
                relevance=0.82,
                thread_relevance=0.78,
                hallucination_risk=0.12,
                contradicts=["agent-1"],
            ),
        ],
    )
    result = _validator().validate(payload)

    assert result.consensus_status == "conflicted"
    assert "conflict_between_top_candidates" in result.global_risk_flags
    assert result.winner_agent_id == "agent-1"


# ──────────────────────────────────────────────
# 4. Weak consensus — only one accepted
# ──────────────────────────────────────────────
def test_weak_consensus_single_accepted():
    payload = ValidationInput(
        task_prompt="Recommend a caching strategy.",
        candidates=[
            CandidateAnswer(
                agent_id="agent-ok",
                answer_text="Use LRU caching with a TTL of 300s.",
                relevance=0.75,
                thread_relevance=0.70,
                hallucination_risk=0.15,
            ),
            CandidateAnswer(
                agent_id="agent-weak",
                answer_text="Cache everything forever.",
                relevance=0.20,
                thread_relevance=0.15,
                hallucination_risk=0.70,
            ),
        ],
    )
    result = _validator().validate(payload)

    assert result.consensus_status == "weak"
    assert result.winner_agent_id == "agent-ok"
    assert "single_point_consensus" in result.global_risk_flags
    accepted = [v for v in result.ranked_candidates if v.accepted]
    assert len(accepted) == 1


# ──────────────────────────────────────────────
# 5. Hallucination risk causes rejection
# ──────────────────────────────────────────────
def test_hallucination_risk_rejection():
    payload = ValidationInput(
        task_prompt="List all prime numbers below 10.",
        candidates=[
            CandidateAnswer(
                agent_id="risky-agent",
                answer_text="2, 3, 5, 7 and also 9.",
                relevance=0.55,
                thread_relevance=0.50,
                hallucination_risk=0.80,
            ),
        ],
    )
    result = _validator().validate(payload)

    assert result.consensus_status == "rejected"
    assert result.winner_agent_id is None
    vc = result.ranked_candidates[0]
    assert vc.accepted is False
    assert "high_hallucination_risk" in vc.risk_flags


# ──────────────────────────────────────────────
# 6. Contradiction penalty lowers score
# ──────────────────────────────────────────────
def test_contradiction_penalty_lowers_score():
    # Same base metrics but one candidate has contradictions
    no_contradiction = CandidateAnswer(
        agent_id="clean",
        answer_text="Answer A.",
        relevance=0.70,
        thread_relevance=0.65,
        hallucination_risk=0.10,
        contradicts=(),
    )
    with_contradiction = CandidateAnswer(
        agent_id="contested",
        answer_text="Answer A.",
        relevance=0.70,
        thread_relevance=0.65,
        hallucination_risk=0.10,
        contradicts=["other-1", "other-2", "other-3"],
    )

    from ls.cognition.collective_answer_validator import _score

    score_clean = _score(no_contradiction)
    score_contested = _score(with_contradiction)

    assert score_contested < score_clean
    assert score_clean - score_contested > 0.0


# ──────────────────────────────────────────────
# 7. Echo chamber flag on near-duplicate low-quality answers
# ──────────────────────────────────────────────
def test_possible_echo_chamber_flag():
    duplicate_answer = "i think it works somehow"
    payload = ValidationInput(
        task_prompt="How does the system work?",
        candidates=[
            CandidateAnswer(
                agent_id=f"agent-{i}",
                answer_text=duplicate_answer,
                relevance=0.35,
                thread_relevance=0.35,
                hallucination_risk=0.30,
            )
            for i in range(3)
        ],
    )
    result = _validator().validate(payload)

    assert "possible_echo_chamber" in result.global_risk_flags


def test_possible_echo_chamber_when_first_candidate_is_unique():
    # Regression: echo-chamber detection must find ANY duplicate group,
    # not only groups that match the first candidate's text.
    payload = ValidationInput(
        task_prompt="How does the system work?",
        candidates=[
            CandidateAnswer(
                agent_id="unique-agent",
                answer_text="An entirely different answer with details.",
                relevance=0.40,
                thread_relevance=0.40,
                hallucination_risk=0.30,
            ),
            CandidateAnswer(
                agent_id="dup-1",
                answer_text="i think it works somehow",
                relevance=0.35,
                thread_relevance=0.35,
                hallucination_risk=0.30,
            ),
            CandidateAnswer(
                agent_id="dup-2",
                answer_text="i think it works somehow",
                relevance=0.35,
                thread_relevance=0.35,
                hallucination_risk=0.30,
            ),
            CandidateAnswer(
                agent_id="dup-3",
                answer_text="i think it works somehow",
                relevance=0.35,
                thread_relevance=0.35,
                hallucination_risk=0.30,
            ),
        ],
    )
    result = _validator().validate(payload)

    assert "possible_echo_chamber" in result.global_risk_flags


def test_distant_second_candidate_does_not_trigger_single_point_consensus():
    # Regression: single_point_consensus must only fire when exactly one
    # candidate is accepted.  A dominant winner with a distant runner-up
    # is still a multi-accepted case and should not carry that flag.
    payload = ValidationInput(
        task_prompt="Recommend a data store.",
        candidates=[
            CandidateAnswer(
                agent_id="strong",
                answer_text="Use PostgreSQL with partitioning.",
                relevance=0.98,
                thread_relevance=0.95,
                hallucination_risk=0.05,
            ),
            CandidateAnswer(
                agent_id="ok",
                answer_text="Try SQLite for now.",
                relevance=0.70,
                thread_relevance=0.65,
                hallucination_risk=0.10,
            ),
        ],
    )
    result = _validator().validate(payload)

    accepted = [v for v in result.ranked_candidates if v.accepted]
    assert len(accepted) == 2
    assert result.consensus_status == "weak"
    assert "single_point_consensus" not in result.global_risk_flags


def test_no_echo_chamber_on_diverse_answers():
    payload = ValidationInput(
        task_prompt="How does the system work?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-0",
                answer_text="It uses event sourcing.",
                relevance=0.70,
                thread_relevance=0.65,
                hallucination_risk=0.10,
            ),
            CandidateAnswer(
                agent_id="agent-1",
                answer_text="It relies on CQRS patterns.",
                relevance=0.68,
                thread_relevance=0.62,
                hallucination_risk=0.12,
            ),
            CandidateAnswer(
                agent_id="agent-2",
                answer_text="A shared memory bus coordinates agents.",
                relevance=0.65,
                thread_relevance=0.60,
                hallucination_risk=0.08,
            ),
        ],
    )
    result = _validator().validate(payload)

    assert "possible_echo_chamber" not in result.global_risk_flags


def test_empty_answer_flag():
    payload = ValidationInput(
        task_prompt="Describe the architecture.",
        candidates=[
            CandidateAnswer(
                agent_id="silent-agent",
                answer_text="   ",
                relevance=0.50,
                thread_relevance=0.50,
                hallucination_risk=0.10,
            ),
        ],
    )
    result = _validator().validate(payload)

    vc = result.ranked_candidates[0]
    assert "empty_answer" in vc.risk_flags
    assert vc.accepted is False
