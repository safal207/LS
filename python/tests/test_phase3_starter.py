import pytest
import datetime
from datetime import timezone
from unittest.mock import MagicMock

from hexagon_core.capu_v3 import CaPUv3
from hexagon_core.belief.lifecycle import BeliefLifecycleManager
from hexagon_core.belief.models import Convict, ConvictStatus, ReinforcementEvent
from hexagon_core.belief.events import BeliefDeprecatedEvent
from hexagon_core.causal.graph import CausalGraph
from hexagon_core.cot.alignment import AlignmentSystem
from hexagon_core.mission.state import MissionState
from hexagon_core.mission.cleanup import MissionCleanupObserver

class TestPhase3Starter:

    @pytest.fixture
    def lifecycle(self):
        return BeliefLifecycleManager()

    @pytest.fixture
    def causal_graph(self):
        return CausalGraph()

    @pytest.fixture
    def mission(self):
        return MissionState()

    # --- Tier 1: Must Have ---

    def test_promotion_rules_basic(self, lifecycle):
        now = datetime.datetime.now(timezone.utc)
        past = now - datetime.timedelta(hours=7)

        c = lifecycle.register_belief("Sky is blue")
        c.created_at = past
        c.decay_cycles_survived = 3
        c.reinforcement_count = 2
        c.confidence = 0.8

        c.reinforcement_history.append(ReinforcementEvent(timestamp=past, source="A", context={}, strength=1.0))
        c.reinforcement_history.append(ReinforcementEvent(timestamp=past, source="B", context={}, strength=1.0))

        can_promote, reason = lifecycle.promotion_system.can_be_promoted(c, now)
        assert can_promote, f"Should be promotable but failed: {reason}"

        c.confidence = 0.5
        can_promote, reason = lifecycle.promotion_system.can_be_promoted(c, now)
        assert not can_promote
        assert "Confidence" in reason

    def test_promotion_with_temporal_aspects(self, lifecycle):
        now = datetime.datetime.now(timezone.utc)
        past = now - datetime.timedelta(hours=1)

        c = lifecycle.register_belief("Time flies")
        c.created_at = past
        c.decay_cycles_survived = 10
        c.reinforcement_count = 10
        c.confidence = 0.99
        c.reinforcement_history.append(ReinforcementEvent(timestamp=past, source="A", context={}, strength=1.0))
        c.reinforcement_history.append(ReinforcementEvent(timestamp=past, source="B", context={}, strength=1.0))

        can_promote, reason = lifecycle.promotion_system.can_be_promoted(c, now)
        assert not can_promote
        assert "Age" in reason

    def test_add_causal_link(self, causal_graph):
        added = causal_graph.add_causal_link("A", "B", 1.0)
        assert added

        down = causal_graph.get_downstream("A")
        assert len(down) == 1
        assert down[0].effect_id == "B"

        up = causal_graph.get_upstream("B")
        assert len(up) == 1
        assert up[0].cause_id == "A"

    def test_alignment_scores_range(self, mission):
        align_sys = AlignmentSystem(mission)
        score = align_sys.calculate_alignment("We must avoid oscillation at all costs")
        assert 0.0 <= score <= 1.0
        assert score > 0.0

    # --- New Tests from Fix List ---

    def test_observer_pattern(self, lifecycle):
        mock_observer = MagicMock()
        mock_observer.handle_event = MagicMock()

        lifecycle.add_observer(mock_observer)

        # Trigger deprecated event
        c = lifecycle.register_belief("Weak belief")
        c.strength = 0.01
        c.status = ConvictStatus.ACTIVE

        # Decay it
        lifecycle.decay_all()

        assert mock_observer.handle_event.called
        event = mock_observer.handle_event.call_args[0][0]
        assert isinstance(event, BeliefDeprecatedEvent)
        assert event.convict_id == c.id

    def test_promote_mature_beliefs(self, lifecycle):
        # Setup valid candidate
        now = datetime.datetime.now(timezone.utc)
        past = now - datetime.timedelta(hours=7)
        c = lifecycle.register_belief("Mature Idea")
        c.created_at = past
        c.decay_cycles_survived = 3
        c.reinforcement_count = 2
        c.confidence = 0.8
        c.reinforcement_history.append(ReinforcementEvent(timestamp=past, source="A", context={}, strength=1.0))
        c.reinforcement_history.append(ReinforcementEvent(timestamp=past, source="B", context={}, strength=1.0))

        promoted = lifecycle.promote_mature_beliefs()
        assert len(promoted) == 1
        assert promoted[0].id == c.id
        assert c.status == ConvictStatus.MATURE

    def test_mission_cleanup_by_id(self, mission):
        # Setup
        observer = MissionCleanupObserver(mission)
        c_id = "convict_123"
        mission.add_convict({"belief": "Bad Idea", "id": c_id})

        assert len(mission.adaptive_beliefs) == 1

        # Trigger event
        event = BeliefDeprecatedEvent(
            timestamp=datetime.datetime.now(timezone.utc),
            convict_id=c_id,
            belief_text="Bad Idea",
            reason="decay"
        )

        observer.handle_event(event)

        assert len(mission.adaptive_beliefs) == 0

    def test_causal_chain_ordering(self, causal_graph):
        causal_graph.add_causal_link("A", "B", 1.0)
        causal_graph.add_causal_link("B", "C", 1.0)
        added = causal_graph.add_causal_link("C", "A", 1.0)
        assert not added

    def test_graph_cleanup_mechanism(self, causal_graph):
        causal_graph.add_causal_link("A", "B", 1.0)
        causal_graph.add_causal_link("B", "C", 1.0)
        causal_graph.remove_belief("B")
        assert len(causal_graph.get_downstream("A")) == 0
        assert len(causal_graph.get_upstream("C")) == 0

    def test_alignment_scores_consistency(self, mission):
        align_sys = AlignmentSystem(mission)
        t1 = align_sys.calculate_alignment("Test")
        t2 = align_sys.calculate_alignment("Test")
        assert t1 == t2

    def test_no_mission_duplication(self):
        """Test that MissionState is not duplicated in CaPUv3."""
        capu = CaPUv3()
        # cleanup_observer.mission should point to the same object as capu.mission
        assert capu.cleanup_observer.mission is capu.mission
