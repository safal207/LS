from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.nca.agent import NCAAgent  # noqa: E402
from modules.nca.multiagent import MultiAgentSystem  # noqa: E402
from modules.nca.orientation import OrientationCenter  # noqa: E402
from modules.nca.signals import InternalSignal  # noqa: E402
from modules.nca.trajectories import TrajectoryOption  # noqa: E402
from modules.nca.world import GridWorld  # noqa: E402


def _make_agent(identity: str = "t-agent") -> NCAAgent:
    return NCAAgent(
        world=GridWorld(size=8, start_position=0, goal_position=7),
        orientation=OrientationCenter(identity=identity, preferences={"progress": 0.8, "stability": 0.2}),
    )


def test_orientation_signal_handler_restores_collective_and_causal_behavior() -> None:
    agent = _make_agent()
    before_stability = agent.orientation.stability_preference
    before_impulse = agent.orientation.impulsiveness

    agent._orientation_signal_handler(InternalSignal(signal_type="causal_drift", payload={}, t=0))
    assert agent.orientation.stability_preference > before_stability
    assert agent.orientation.impulsiveness < before_impulse

    agent._orientation_signal_handler(
        InternalSignal(signal_type="coordination_required", payload={"collective_score": 1.0}, t=1)
    )
    emitted = agent.signal_bus.get_recent(clear=True)
    assert any(s.signal_type == "collectivegoalconflict" for s in emitted)


def test_step_uses_dynamic_value_action_and_emits_low_confidence() -> None:
    agent = _make_agent()
    agent.identitycore.generate_initiative = lambda: {  # type: ignore[assignment]
        "mode": "stabilize",
        "preferred_actions": ["idle"],
        "identity_integrity": 0.9,
        "agency_level": 0.5,
    }

    captured: dict[str, str] = {}
    original_eval = agent.values.evaluate_value_alignment

    def _capture(action, intent, strategy):
        captured["action"] = str(action.get("action"))
        return original_eval(action, intent, strategy)

    agent.values.evaluate_value_alignment = _capture  # type: ignore[assignment]

    agent.planner.choose = lambda _: TrajectoryOption(  # type: ignore[assignment]
        action="idle",
        score=0.1,
        details={"forced": True},
        uncertainty=0.9,
        confidence=0.01,
        causal_score=0.0,
    )

    event = agent.step()
    assert captured["action"] == "idle"
    assert any(sig.get("type") == "low_confidence" for sig in event["signals"])


def test_collective_traditions_are_aggregated_not_last_write_wins() -> None:
    a1 = _make_agent("a1")
    a2 = _make_agent("a2")
    a1.culture.traditions = {"ritual": 0.2}
    a2.culture.traditions = {"ritual": 0.8}

    mas = MultiAgentSystem()
    mas.add_agent(a1)
    mas.add_agent(a2)

    collective = mas.collective_state()
    assert collective["collectivetraditionpatterns"]["ritual"] == 0.5


def test_culture_alignment_uses_explicit_scores() -> None:
    agent = _make_agent()
    score = agent.culture.evaluate_cultural_alignment(0.9, 0.8, 0.7)
    assert 0.0 <= score <= 1.0


def test_social_and_identity_compatibility_fallback_inputs() -> None:
    agent = _make_agent("compat")

    events = [
        {
            "agent": "peer-1",
            "primaryintent": {"desired_mode": "balanced", "alignment": 0.7, "strength": 0.6},
            "values": {"corevalues": {"collective_good": 0.8}, "value_alignment": 0.75},
        }
    ]
    agent.social.infer_other_agents_intents(events)
    agent.social.infer_other_agents_values(events)
    social_snapshot = agent.social.update_from_collective_state({"collectivecollaboration": 0.9})

    assert "peer-1" in agent.social.social_models
    assert social_snapshot["cooperation_score"] > 0.0

    agent.culture.traditions = [{"pattern": "repeat_idle", "strength": 0.9}]
    score = agent.identitycore.evaluate_cultural_compatibility(agent.culture)
    assert 0.0 <= score <= 1.0


def test_multiagent_and_self_model_support_list_traditions() -> None:
    a1 = _make_agent("m1")
    a2 = _make_agent("m2")

    a1.culture.traditions = [{"pattern": "ritual", "strength": 0.2}]
    a2.culture.traditions = [{"pattern": "ritual", "strength": 0.8}]

    mas = MultiAgentSystem()
    mas.add_agent(a1)
    mas.add_agent(a2)
    collective = mas.collective_state()

    assert collective["collectivetraditionpatterns"]["ritual"] == 0.5

    metrics = a1.self_model.update_culture_metrics(a1.culture)
    assert metrics["tradition_count"] == 1


def test_trajectory_culture_alignment_uses_conflicts_property() -> None:
    agent = _make_agent("traj")
    agent.culture.norm_conflicts = [{"norm": "stability", "severity": 0.9}] * 3
    # Verify property access
    assert len(agent.culture.conflicts) == 3

    planner = agent.planner
    opt = TrajectoryOption(
        action="left",
        score=0.0,
        details={},
        uncertainty=0.0,
        confidence=0.0,
        causal_score=0.0,
    )
    score = planner.evaluate_culture_alignment(opt, agent.culture)
    assert 0.0 <= score <= 1.0


def test_phase_11_1_engines_are_emitted_in_agent_event() -> None:
    agent = _make_agent("phase11_1")
    event = agent.step()

    assert "militocracy" in event
    assert "synergy" in event
    assert "coordinated_command" in {s.get("name") for s in event.get("strategies", [])}


def test_multiagent_collective_phase_11_1_metrics() -> None:
    a1 = _make_agent("mc1")
    a2 = _make_agent("mc2")

    a1.step()
    a2.step()

    mas = MultiAgentSystem()
    mas.add_agent(a1)
    mas.add_agent(a2)
    collective = mas.collective_state()

    assert 0.0 <= float(collective.get("collectivemilitarydiscipline", 0.0)) <= 1.0
    assert 0.0 <= float(collective.get("collectivecommandcoherence", 0.0)) <= 1.0
    assert 0.0 <= float(collective.get("collectivesynergyindex", 0.0)) <= 1.0
    assert 0.0 <= float(collective.get("collectivesynergy", 0.0)) <= 1.0
    assert 0.0 <= float(collective.get("collectivemilitocracy", 0.0)) <= 1.0


def test_event_serialization_handles_list_traditions_shapes() -> None:
    agent = _make_agent("serial")
    agent.social.tradition_patterns = [{"pattern": "repeat_idle", "strength": 0.7}]
    agent.culture.traditions = [{"pattern": "ritual", "strength": 0.9}]

    event = agent.step()

    assert isinstance(event["social"]["tradition_patterns"], (list, dict))
    assert isinstance(event["culture"]["traditions"], (list, dict))
    assert isinstance(event["militocracy"]["snapshot"], dict)
    assert isinstance(event["synergy"]["snapshot"], dict)


def test_civilization_demo_exposes_phase_11_1_collective_metrics() -> None:
    from modules.nca.experiments.ncacivilizationdemo import NCACivilizationDemo

    result = NCACivilizationDemo(steps=1, agent_count=2).run()
    collective = result.get("collective", {})

    assert "collectivesynergy" in collective
    assert "collectivemilitocracy" in collective
    assert 0.0 <= float(collective.get("civilizationmaturityscore", 0.0)) <= 1.0


def test_collective_alias_metrics_match_canonical_values() -> None:
    a1 = _make_agent("alias1")
    a2 = _make_agent("alias2")

    a1.step()
    a2.step()

    mas = MultiAgentSystem()
    mas.add_agent(a1)
    mas.add_agent(a2)
    collective = mas.collective_state()

    assert float(collective.get("collectivesynergy", -1.0)) == float(
        collective.get("collectivesynergyindex", -2.0)
    )
    assert float(collective.get("collectivemilitocracy", -1.0)) == float(
        collective.get("collectivemilitarydiscipline", -2.0)
    )


def test_phase_11_identity_stability() -> None:
    agent = _make_agent("stability")
    agent.identitycore.identity_integrity = 0.4
    agent.identitycore.drift_resistance = 0.4
    agent.identitycore.stabilize_identity()
    # Expect boosts due to low integrity
    assert agent.identitycore.core_traits.get("consistency", 0.0) > 0.7
    assert agent.identitycore.drift_resistance > 0.4


def test_phase_11_culture_alignment() -> None:
    agent = _make_agent("culture_align")
    agent.culture.norms = {"cooperation": 0.8, "stability": 0.6}
    agent.identitycore.culturalpreferenceprofile = {"cooperation": 0.8, "stability": 0.6, "tradition": 0.5}
    score = agent.identitycore.evaluate_cultural_compatibility(agent.culture)
    assert score > 0.6


def test_phase_11_synergy_index() -> None:
    agent = _make_agent("synergy")
    agent.social.cooperation_score = 0.9
    agent.culture.culturalalignmentscore = 0.8
    # Ensure culture has valid civilization state for maturity check inside synergy
    agent.culture.civilization_state["civilizationmaturityscore"] = 0.7

    agent.synergy.update_from_social(agent.social)
    agent.synergy.update_from_culture(agent.culture)

    assert agent.synergy.synergy_index > 0.5
    assert agent.synergy.cooperative_efficiency > 0.8


def test_phase_11_collective_norms() -> None:
    a1 = _make_agent("n1")
    a2 = _make_agent("n2")
    a1.culture.norms = {"honesty": 0.8}
    a2.culture.norms = {"honesty": 0.4}

    mas = MultiAgentSystem()
    mas.add_agent(a1)
    mas.add_agent(a2)
    collective = mas.collective_state()

    # 0.6 is the average of 0.8 and 0.4
    assert 0.55 < collective["collectivenorms"]["honesty"] < 0.65
