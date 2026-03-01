import unittest
from unittest.mock import MagicMock, patch
from codex.causal_memory.bloodstream import Bloodstream
from codex.causal_memory.amygdala import Amygdala
from python.modules.agent.loop import AgentLoop

class TestBloodstreamSmoke(unittest.TestCase):
    def setUp(self):
        self.mock_amygdala = MagicMock(spec=Amygdala)
        self.mock_amygdala.to_snapshot.return_value = {"state": 0.5, "phantom_pain": 0.1}
        self.mock_temporal = MagicMock()
        self.bloodstream = Bloodstream(self.mock_amygdala, self.mock_temporal)
        self.bloodstream.peers = ["peer1"]

    @patch("python.modules.lthread.create_audited_package")
    @patch("python.modules.lthread.send_package")
    @patch("python.modules.lthread.receive_from_peer")
    def test_blood_pump_transfers_snapshot(self, mock_receive, mock_send, mock_create):
        mock_create.return_value = {"pkg": "data"}
        mock_receive.return_value = {"state": 0.7, "phantom_pain": 0.2}

        self.bloodstream.pump()

        mock_create.assert_called_once()
        mock_send.assert_called_once_with({"pkg": "data"}, "peer1")
        mock_receive.assert_called_once_with("peer1")
        self.mock_amygdala.merge_from_peer.assert_called_once_with({"state": 0.7, "phantom_pain": 0.2})

    @patch("python.modules.lthread.send_toxins")
    def test_toxin_filter_prunes_and_sends(self, mock_send_toxins):
        self.mock_temporal.prune_weak_nodes.return_value = 5

        self.bloodstream.filter_toxins()

        self.mock_temporal.prune_weak_nodes.assert_called_once_with(threshold=0.25)
        mock_send_toxins.assert_called_once_with(5, ["peer1"])

    def test_peer_merge_logic(self):
        # Real Amygdala to test merge logic
        real_amygdala = Amygdala(persist_state=False)
        real_amygdala.state = 0.5
        real_amygdala.visceral.phantom_pain = 0.1

        peer_data = {
            "state": 0.8,
            "phantom_pain": 0.4,
            "personality_p": 0.6,
            "endocrine": real_amygdala.endocrine.to_dict()
        }

        real_amygdala.merge_from_peer(peer_data)

        # alpha=0.3. 0.5 * 0.7 + 0.8 * 0.3 = 0.35 + 0.24 = 0.59
        self.assertAlmostEqual(real_amygdala.state, 0.59)
        # 0.1 + (0.4 - 0.1) = 0.4
        self.assertAlmostEqual(real_amygdala.phantom_pain, 0.4)

    def test_agent_loop_integration(self):
        mock_llm = MagicMock()
        with patch("threading.Thread"):
            loop = AgentLoop(llm=mock_llm, temporal_enabled=True)
            self.assertIsInstance(loop.bloodstream, Bloodstream)
            self.assertEqual(loop.bloodstream.amygdala, loop.causal_transitions.amygdala)

if __name__ == "__main__":
    unittest.main()
