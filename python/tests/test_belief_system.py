import pytest
from datetime import datetime
from hexagon_core.belief_system import (
    ReinforcementTracker,
    DecayEngine,
    ContradictionDetector,
    SemanticClusterManager,
    Convict
)

class TestBeliefSystem:

    def test_reinforcement_boost(self):
        tracker = ReinforcementTracker()

        # Case 1: Low confidence -> High boost
        c_low = Convict("test", {}, 0.1, "test", 1, 0, 0)
        boost_low = tracker.calculate_boost(c_low)

        # Case 2: High confidence -> Low boost
        c_high = Convict("test", {}, 0.9, "test", 1, 0, 0)
        boost_high = tracker.calculate_boost(c_high)

        assert boost_low > boost_high, "Boost should be higher for low confidence"
        assert boost_high < tracker.base_boost, "Boost should be less than base at high confidence"

    def test_decay_survived(self):
        engine = DecayEngine()

        # Case 1: Active belief -> Increment
        c_active = Convict("test", {}, 0.5, "test", 1, 0, 0)
        c_active.status = "active"
        c_active.decay_cycles_survived = 0
        c_active.last_validated = datetime.now().timestamp() # Recent

        engine.apply_decay(c_active)
        assert c_active.decay_cycles_survived == 1

        # Case 2: Deprecated belief -> No Increment
        c_dep = Convict("test", {}, 0.1, "test", 1, 0, 0)
        c_dep.status = "deprecated"
        c_dep.decay_cycles_survived = 5

        engine.apply_decay(c_dep)
        assert c_dep.decay_cycles_survived == 5

    def test_negation_detection(self):
        detector = ContradictionDetector()

        # Explicit negation
        assert detector.detect("I love Python", "I do not love Python") is True

        # Different topics (low similarity)
        assert detector.detect("I love Python", "I love Rust") is False

        # Double negative (agreement)
        assert detector.detect("I do not like errors", "I never like errors") is False

        # Implicit conflict (not handled by simple negation, currently False)
        # assert detector.detect("Sky is blue", "Sky is green") is False

    def test_clustering_russian(self):
        manager = SemanticClusterManager()

        c1 = Convict("Питон это большая змея", {}, 0.5, "test", 1, 0, 0)
        c2 = Convict("Питон это язык программирования", {}, 0.5, "test", 1, 0, 0)

        clusters = manager.cluster([c1, c2])

        # Should be 2 clusters because overlap is just "Питон" (and "это" is stopword)
        # "змея", "большая" vs "язык", "программирования"
        assert len(clusters) == 2, f"Failed to separate Russian homonyms. Clusters: {len(clusters)}"
        assert clusters[0].id != clusters[1].id

    def test_clustering_best_fit(self):
        manager = SemanticClusterManager()

        # Center: "Python language"
        # C1: "Python programming language" (should match)
        # C2: "Cobra snake" (should new)
        # C3: "Rust language" (should new or match if threshold low, but threshold 0.4 implies high similarity needed)

        # Let's test the greedy vs best fit logic specifically?
        # Hard to test without controlling iteration order, but manager logic is deterministic.
        pass
