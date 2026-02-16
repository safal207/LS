import pytest
from unittest.mock import MagicMock, call, ANY
from python.modules.nca.agent import NCAAgent

class TestUULIntegration:
    def test_uul_order(self):
        """
        Verifies that NCAAgent.step follows the strict UUL v1.0 order.
        """
        # Create a mock agent with mocked components
        agent = NCAAgent(
            world=MagicMock(),
            orientation=MagicMock(),
        )

        # Mock all sub-components
        agent.self_model = MagicMock()
        agent.meta_observer = MagicMock()
        agent.metacognition = MagicMock()
        agent.identitycore = MagicMock()
        agent.social = MagicMock()
        agent.culture = MagicMock()
        agent.militocracy = MagicMock()
        agent.synergy = MagicMock()
        agent.values = MagicMock()
        agent.autonomy = MagicMock()
        agent.intentengine = MagicMock()
        agent.planner = MagicMock()
        agent.causal_graph = MagicMock()
        agent.signal_bus = MagicMock()

        # Mock methods to return expected structures to prevent crashes
        agent.build_state = MagicMock(return_value=MagicMock(t=1))
        agent.meta_observer.observe_and_correct.return_value = {"report": {}}
        agent.metacognition.analyze_cognition.return_value = {}
        agent.identitycore.generate_initiative.return_value = {"preferred_actions": ["idle"]}
        agent.autonomy.generate_strategies.return_value = []
        agent.autonomy.select_strategy.return_value = {}
        agent.intentengine.generate_intents.return_value = []
        agent.intentengine.select_primary_intent.return_value = {}
        agent.planner.choose.return_value = MagicMock(action="idle", score=1.0, confidence=1.0, details={})
        agent.world.step.return_value = {"t": 1}

        # Helper to track calls globally
        manager = MagicMock()
        manager.attach_mock(agent.self_model, 'self_model')
        manager.attach_mock(agent.meta_observer, 'meta_observer')
        manager.attach_mock(agent.metacognition, 'metacognition')
        manager.attach_mock(agent.identitycore, 'identitycore')
        manager.attach_mock(agent.social, 'social')
        manager.attach_mock(agent.culture, 'culture')
        manager.attach_mock(agent.militocracy, 'militocracy')
        manager.attach_mock(agent.synergy, 'synergy')
        manager.attach_mock(agent.values, 'values')
        manager.attach_mock(agent.autonomy, 'autonomy')
        manager.attach_mock(agent.intentengine, 'intentengine')
        manager.attach_mock(agent.planner, 'planner')
        manager.attach_mock(agent.world, 'world')
        manager.attach_mock(agent.causal_graph, 'causal_graph')

        # Run step
        agent.step()

        # Define expected call order sequence (partial, key steps)
        expected_calls = [
            # 2. Self-Model Layer
            call.self_model.update_from_state(ANY),
            call.meta_observer.observe_and_correct(ANY, ANY, ANY, self_model=ANY),
            call.metacognition.analyze_cognition(ANY, ANY, ANY),

            # 3. Identity Layer
            call.identitycore.update_from_self_model(ANY),
            call.identitycore.update_from_meta(ANY),
            call.identitycore.stabilize_identity(),

            # 4. Social Layer
            call.social.update_from_collective_state(ANY),
            call.social.infer_other_agents_intents(ANY),
            call.social.infer_other_agents_values(ANY),
            call.social.evaluate_social_alignment(ANY, ANY),

            # 5. Culture Layer
            call.culture.update_from_social(ANY),
            call.culture.update_from_values(ANY),
            call.culture.update_from_collective(ANY),
            call.culture.infer_norms(ANY),
            call.culture.evolve_norms(),
            call.culture.evaluate_cultural_alignment(ANY, ANY, ANY),

            # 6. Derived Engines Layer
            # Militocracy
            call.militocracy.update_from_identity(ANY),
            call.militocracy.update_from_autonomy(ANY),
            call.militocracy.update_from_culture(ANY),
            # Synergy
            call.synergy.update_from_social(ANY),
            call.synergy.update_from_culture(ANY),
            call.synergy.update_from_collective(ANY),

            # 7. Values Layer
            call.values.update_from_identity(ANY),
            call.values.update_from_collective(ANY),

            # 8. Autonomy Layer
            call.autonomy.generate_strategies(ANY, ANY, ANY, values=ANY, culture=ANY, militocracy=ANY, synergy=ANY),
            call.autonomy.apply_cooperative_regulation(ANY, ANY),
            call.autonomy.select_strategy(),

            # 9. Intent Layer
            call.intentengine.generate_intents(ANY, ANY, ANY, strategy=ANY, values=ANY, social=None, collective_state=None),
            call.intentengine.apply_social_influence(ANY, ANY),
            call.intentengine.select_primary_intent(),

            # 10. Planning Layer
            call.planner.generate(ANY, ANY, initiative=ANY, intent=ANY, strategy=ANY, values=ANY, social=ANY, culture=ANY),
            call.planner.evaluate(ANY, ANY, collective_state=ANY, self_model=ANY, metafeedback=ANY, initiative=ANY, intent=ANY, strategy=ANY, values=ANY, social=ANY, culture=ANY),
            call.planner.choose(ANY),

            # 11. World Step
            call.world.step(ANY),
            call.causal_graph.record_transition(ANY, ANY, ANY),
        ]

        # Verify call order
        # We check if these calls appear in manager.mock_calls in this relative order
        # Since strict `assert_has_calls` with `any_order=False` checks exact match including intermediate calls we might miss,
        # we will iterate and find them.

        mock_calls = manager.mock_calls
        last_index = -1
        for expected in expected_calls:
            try:
                # Find the next occurrence of expected call
                index = mock_calls.index(expected, last_index + 1)
                last_index = index
            except ValueError:
                # If not found, print useful info
                print(f"Expected call not found or out of order: {expected}")
                print("Actual calls around last known position:")
                start = max(0, last_index - 5)
                end = min(len(mock_calls), last_index + 10)
                for i in range(start, end):
                    print(f"{i}: {mock_calls[i]}")
                pytest.fail(f"Call sequence mismatch. Missing or out-of-order: {expected}")

if __name__ == "__main__":
    pytest.main([__file__])
