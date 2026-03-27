import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.coalition_registry import CoalitionRecord, CoalitionRegistry


def test_coalition_registry_selects_best_matching_coalition(tmp_path):
    registry = CoalitionRegistry(tmp_path / "coalitions.json")
    registry.save_coalition(
        CoalitionRecord(
            coalition_id="coalition-a",
            route_key="full_run>local>gonka>mimo",
            members=["local", "gonka", "mimo"],
            intents=["technical_reasoning"],
            why_tags=["evaluate_reasoning"],
            trust_score=0.9,
        )
    )
    registry.save_coalition(
        CoalitionRecord(
            coalition_id="coalition-b",
            route_key="full_run>local",
            members=["local"],
            intents=["technical_reasoning"],
            why_tags=["evaluate_reasoning"],
            trust_score=0.4,
        )
    )

    selected = registry.select_best(
        available_backends=["local", "gonka", "mimo"],
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
    )

    assert selected is not None
    assert selected.route_key == "full_run>local>gonka>mimo"


def test_coalition_registry_updates_trust_after_run(tmp_path):
    registry = CoalitionRegistry(tmp_path / "coalitions.json")
    registry.save_coalition(
        CoalitionRecord(
            coalition_id="coalition-a",
            route_key="full_run>local>gonka>mimo",
            members=["local", "gonka", "mimo"],
            trust_score=0.5,
        )
    )

    updated = registry.update_after_run(
        route_key="full_run>local>gonka>mimo",
        quality_score=0.8,
        success=True,
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
    )

    assert updated.runs == 1
    assert updated.successes == 1
    assert updated.trust_score > 0.5
    assert "technical_reasoning" in updated.intents
