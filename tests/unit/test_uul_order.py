import pytest
from unittest.mock import ANY, MagicMock

from python.modules.nca.agent import NCAAgent


class TestUULIntegration:
    def test_uul_order(self) -> None:
        """Verifies that NCAAgent.step follows context-native UUL v1.0 ordering."""
        agent = NCAAgent(
            world=MagicMock(),
            orientation=MagicMock(),
        )

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

        agent.build_state = MagicMock(return_value=MagicMock(t=1, world_state={}))
        agent.orientation.to_snapshot.return_value = {}
        agent.values.to_context_snapshot.return_value = {}
        agent.autonomy.to_context_snapshot.return_value = {}
        agent.intentengine.to_context_snapshot.return_value = {}
        agent.social.to_context_snapshot.return_value = {}
        agent.culture.to_context_snapshot.return_value = {}
        agent.militocracy.to_context_snapshot.return_value = {}
        agent.synergy.to_context_snapshot.return_value = {}
        agent.identitycore.to_context_snapshot.return_value = {}

        agent.self_model.update.return_value = {
            "snapshot": {},
            "analysis": {},
            "metafeedback": {},
        }
        agent.orientation.update.return_value = {"snapshot": {}}
        agent.identitycore.update.return_value = {"snapshot": {}, "initiative": {}}
        agent.social.update.return_value = {"snapshot": {}, "alignment": 0.0, "adjustments": {}}
        agent.culture.update.return_value = {"snapshot": {}, "alignment": 0.0, "adjustments": {}}
        agent.militocracy.update.return_value = {"snapshot": {}, "trace_snapshot": {}}
        agent.synergy.update.return_value = {"snapshot": {}, "trace_snapshot": {}}
        agent.values.update.return_value = {"snapshot": {}, "value_alignment": 0.0}
        agent.autonomy.update.return_value = {
            "snapshot": {},
            "primary_strategy": {},
            "strategies": [],
        }
        agent.intentengine.update.return_value = {
            "snapshot": {},
            "primary_intent": {},
            "intents": [],
        }
        choice = MagicMock(action="idle", score=1.0, confidence=1.0, details={})
        choice.uncertainty = 0.0
        choice.causal_score = 0.0
        agent.planner.generate.return_value = [choice]
        agent.planner.evaluate.return_value = [choice]
        agent.planner.choose.return_value = choice
        agent.world.step.return_value = {"t": 1}
        agent._finalize_step = MagicMock(return_value={"t": 1})

        manager = MagicMock()
        manager.attach_mock(agent.self_model, "self_model")
        manager.attach_mock(agent.orientation, "orientation")
        manager.attach_mock(agent.identitycore, "identitycore")
        manager.attach_mock(agent.social, "social")
        manager.attach_mock(agent.culture, "culture")
        manager.attach_mock(agent.militocracy, "militocracy")
        manager.attach_mock(agent.synergy, "synergy")
        manager.attach_mock(agent.values, "values")
        manager.attach_mock(agent.autonomy, "autonomy")
        manager.attach_mock(agent.intentengine, "intentengine")
        manager.attach_mock(agent.planner, "planner")
        manager.attach_mock(agent.world, "world")
        manager.attach_mock(agent.causal_graph, "causal_graph")

        agent.step()

        expected_order = [
            "self_model.update",
            "orientation.update",
            "identitycore.update",
            "social.update",
            "culture.update",
            "militocracy.update",
            "synergy.update",
            "values.update",
            "autonomy.update",
            "intentengine.update",
            "planner.generate",
            "planner.evaluate",
            "planner.choose",
            "world.step",
            "causal_graph.record_transition",
        ]

        call_names = [entry[0] for entry in manager.mock_calls]
        last_index = -1
        for expected_name in expected_order:
            try:
                current_index = call_names.index(expected_name, last_index + 1)
            except ValueError:
                pytest.fail(f"Call sequence mismatch. Missing or out-of-order: {expected_name}")
            last_index = current_index

        agent.self_model.update.assert_called_with(ANY)
        agent.orientation.update.assert_called_with(ANY)
        agent._finalize_step.assert_called_once()
