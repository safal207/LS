from __future__ import annotations

from ls.cognition.state_tracker import AgentState, StateTracker


def test_state_tracker_keeps_previous_and_current():
    tracker = StateTracker()

    s1 = AgentState(goal="ship", context={"step": 1}, goal_completion=0.1)
    s2 = AgentState(goal="ship", context={"step": 2}, goal_completion=0.4)

    tracker.update(s1)
    assert tracker.previous_state() is None
    assert tracker.current_state() == s1

    tracker.update(s2)
    assert tracker.previous_state() == s1
    assert tracker.current_state() == s2
    assert len(tracker.history) == 2
