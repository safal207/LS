import unittest
from unittest.mock import MagicMock, ANY
from dataclasses import FrozenInstanceError
import sys
import os

# Add repo root to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from python.modules.nca.agent import NCAAgent
from python.modules.nca.update_context import UpdateContext

class TestContextPropagation(unittest.TestCase):
    def setUp(self):
        self.world = MagicMock()
        self.world.t = 0
        self.world.state.return_value = {}
        self.orientation = MagicMock()
        # Mock signal bus to avoid issues
        self.signal_bus = MagicMock()

        # We need to mock engines during initialization or after?
        # NCAAgent instantiates engines in __init__ defaults.
        # We can overwrite them after init.
        self.agent = NCAAgent(world=self.world, orientation=self.orientation, signal_bus=self.signal_bus)

    def test_context_immutability(self):
        context = UpdateContext(t=0, state=None, collective_state={})
        with self.assertRaises(FrozenInstanceError):
            context.t = 1

    def test_step_propagates_context(self):
        # Mock engines to verify calls
        self.agent.social = MagicMock()
        self.agent.culture = MagicMock()
        self.agent.identitycore = MagicMock()
        self.agent.values = MagicMock()
        self.agent.autonomy = MagicMock()
        self.agent.intentengine = MagicMock()
        self.agent.militocracy = MagicMock()
        self.agent.synergy = MagicMock()
        self.agent.planner = MagicMock()
        # self.agent.metacognition = MagicMock() # Property, cannot set
        self.agent.self_model = MagicMock()
        self.agent.assembly = MagicMock()
        # self.agent.meta_observer = MagicMock() # Property, cannot set
        self.agent.causal_graph = MagicMock()

        # Setup return values for mocks to satisfy flow
        self.agent.assembly.build.return_value = MagicMock(t=0, world_state={})
        # Phase 13: Mock update(context) instead of legacy methods
        self.agent.self_model.update.return_value = {
            "snapshot": {"self_data": "test"},
            "analysis": {"report": {}},
            "metafeedback": {}
        }
        self.agent.orientation.update.return_value = {"snapshot": {"orientation_data": "test"}}
        self.agent.orientation.to_snapshot.return_value = {}

        self.agent.identitycore.update.return_value = {"snapshot": {"id_data": "test"}, "initiative": {}}
        self.agent.social.update.return_value = {"snapshot": {"social_data": "test"}, "alignment": 0.5, "adjustments": {}}
        self.agent.culture.update.return_value = {"snapshot": {}, "alignment": 0.5, "adjustments": {}}
        self.agent.militocracy.update.return_value = {"snapshot": {}, "trace_snapshot": {}}
        self.agent.synergy.update.return_value = {"snapshot": {}, "trace_snapshot": {}}
        self.agent.values.update.return_value = {"snapshot": {}, "value_alignment": 0.5}
        self.agent.autonomy.update.return_value = {"snapshot": {}, "primary_strategy": {}, "strategies": []}
        self.agent.intentengine.update.return_value = {"snapshot": {}, "primary_intent": {}, "intents": []}

        # Mock to_context_snapshot for initialization
        self.agent.values.to_context_snapshot.return_value = {}
        self.agent.autonomy.to_context_snapshot.return_value = {}
        self.agent.intentengine.to_context_snapshot.return_value = {}
        self.agent.intentengine.select_primary_intent.return_value = {}
        self.agent.social.to_context_snapshot.return_value = {}
        self.agent.culture.to_context_snapshot.return_value = {}
        self.agent.militocracy.to_context_snapshot.return_value = {}
        self.agent.synergy.to_context_snapshot.return_value = {}
        self.agent.identitycore.to_context_snapshot.return_value = {}

        self.agent.planner.choose.return_value = MagicMock(action="idle", score=0.0, confidence=1.0, details={}, uncertainty=0.0, causal_score=0.0)
        self.agent.planner.generate.return_value = []
        self.agent.planner.evaluate.return_value = []

        self.agent.world.step.return_value = {"t": 1}

        self.agent.step()

        # Verify calls

        # Verify SelfModel update
        self.agent.self_model.update.assert_called_with(ANY)
        arg_self = self.agent.self_model.update.call_args[0][0]
        self.assertIsInstance(arg_self, UpdateContext)
        self.assertEqual(arg_self.orientation_snapshot, {}) # Mocked to_snapshot

        # Verify Orientation update
        self.agent.orientation.update.assert_called_with(ANY)
        arg_orient = self.agent.orientation.update.call_args[0][0]
        self.assertEqual(arg_orient.self_snapshot, {"self_data": "test"})

        self.agent.social.update.assert_called_with(ANY)
        arg_social = self.agent.social.update.call_args[0][0]
        self.assertIsInstance(arg_social, UpdateContext)
        # Verify social context has identity snapshot (since identity runs before social)
        self.assertEqual(arg_social.identity_snapshot, {"id_data": "test"})

        self.agent.culture.update.assert_called_with(ANY)
        arg_culture = self.agent.culture.update.call_args[0][0]
        self.assertIsInstance(arg_culture, UpdateContext)
        # Verify culture context has social snapshot
        self.assertEqual(arg_culture.social_snapshot, {"social_data": "test"})

if __name__ == "__main__":
    unittest.main()
