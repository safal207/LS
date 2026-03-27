import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.derived_module_registry import DerivedModuleRegistry


def test_derived_module_registry_creates_and_selects_module(tmp_path):
    registry = DerivedModuleRegistry(tmp_path / "derived.json")
    created = registry.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="technical_reasoning",
        task_type="evaluate_reasoning",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Use concise technical interview answers.",
        quality_score=0.84,
    )

    selected = registry.find_best(
        available_backends=["local", "gonka"],
        domain="technical_reasoning",
        task_type="evaluate_reasoning",
        min_quality=0.7,
        min_trust=0.6,
    )

    assert created.module_id.startswith("derived-technical-reasoning")
    assert selected is not None
    assert selected.module_id == created.module_id


def test_derived_module_registry_marks_usage_and_updates_scores(tmp_path):
    registry = DerivedModuleRegistry(tmp_path / "derived.json")
    created = registry.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="technical_reasoning",
        task_type="evaluate_reasoning",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Use concise technical interview answers.",
        quality_score=0.8,
    )

    updated = registry.mark_used(created.module_id, quality_score=0.9, success=True)

    assert updated is not None
    assert updated.usage_count == 1
    assert updated.runs == 1
    assert updated.successes == 1
    assert updated.trust_score >= created.trust_score
