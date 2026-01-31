import pytest
import datetime
from unittest.mock import MagicMock

from hexagon_core.belief.lifecycle import BeliefLifecycleManager
from hexagon_core.belief.models import Convict, ConvictStatus, ReinforcementEvent
from hexagon_core.belief.promotion import PromotionCriteria
from hexagon_core.causal.graph import CausalGraph
from hexagon_core.cot.alignment import AlignmentSystem
from hexagon_core.mission.state import MissionState

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
        # Setup: Create a convict that meets all criteria
        # Criteria defaults: age=6h, decay=3, reinf=2, conf=0.75, sources=2

        now = datetime.datetime.now()
        past = now - datetime.timedelta(hours=7)

        c = lifecycle.register_belief("Sky is blue")
        c.created_at = past
        c.decay_cycles_survived = 3
        c.reinforcement_count = 2
        c.confidence = 0.8

        # Add 2 unique sources
        c.reinforcement_history.append(ReinforcementEvent(timestamp=past, source="A", context={}, strength=1.0))
        c.reinforcement_history.append(ReinforcementEvent(timestamp=past, source="B", context={}, strength=1.0))

        # Test
        can_promote, reason = lifecycle.promotion_system.can_be_promoted(c, now)
        assert can_promote, f"Should be promotable but failed: {reason}"

        # Test failure case: Low confidence
        c.confidence = 0.5
        can_promote, reason = lifecycle.promotion_system.can_be_promoted(c, now)
        assert not can_promote
        assert "Confidence" in reason

    def test_promotion_with_temporal_aspects(self, lifecycle):
        # Test Age constraint
        now = datetime.datetime.now()
        past = now - datetime.timedelta(hours=1) # Too young (default 6h)

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
        # A -> B
        added = causal_graph.add_causal_link("A", "B", 1.0)
        assert added

        # Verify upstream/downstream
        down = causal_graph.get_downstream("A")
        assert len(down) == 1
        assert down[0].effect_id == "B"

        up = causal_graph.get_upstream("B")
        assert len(up) == 1
        assert up[0].cause_id == "A"

    def test_alignment_scores_range(self, mission):
        align_sys = AlignmentSystem(mission)

        # "Avoid oscillation" is a core principle.
        score = align_sys.calculate_alignment("We must avoid oscillation at all costs")
        assert 0.0 <= score <= 1.0
        # Should be relatively high due to overlap "avoid", "oscillation"
        assert score > 0.0

    # --- Tier 2: Should Have ---

    def test_causal_chain_ordering(self, causal_graph):
        # A -> B -> C
        causal_graph.add_causal_link("A", "B", 1.0)
        causal_graph.add_causal_link("B", "C", 1.0)

        # Cycle detection A -> B -> C -> A
        # Trying to add C -> A should fail
        added = causal_graph.add_causal_link("C", "A", 1.0)
        assert not added # Cycle detected

    def test_graph_cleanup_mechanism(self, causal_graph):
        causal_graph.add_causal_link("A", "B", 1.0)
        causal_graph.add_causal_link("B", "C", 1.0)

        # Remove B
        causal_graph.remove_belief("B")

        # Links involving B should be gone
        assert len(causal_graph.get_downstream("A")) == 0
        assert len(causal_graph.get_upstream("C")) == 0

    def test_alignment_scores_consistency(self, mission):
        align_sys = AlignmentSystem(mission)
        t1 = align_sys.calculate_alignment("Test")
        t2 = align_sys.calculate_alignment("Test")
        assert t1 == t2
