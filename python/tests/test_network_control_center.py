from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from network import NetworkControlCenter, NetworkExecutionPlan  # noqa: E402


class FakeOrientationCenter:
    def __init__(self):
        self.last_observer_report = None

    def decide(self, item, *, thread_context=None, intent=None, why_tag=None, observer_report=None):
        self.last_observer_report = observer_report
        return NetworkExecutionPlan(
            mode="full_run",
            route_key="full_run>local>gonka>mimo",
            coalition_id="full_run-local-gonka-mimo",
            derived_module_id=None,
            memory_case_id=None,
            reason="control-center",
            confidence=0.8,
            observer_report=observer_report,
        )


class FakeObserver:
    def evaluate(self):
        return type(
            "Observer",
            (),
            {
                "to_dict": lambda self_: {
                    "status": "watch",
                    "summary": {"trend": "stable"},
                    "adequacy": {"status": "watch"},
                    "retrospective": {"weak_routes": []},
                    "trajectory": {"record": {"trend": "stable"}},
                }
            },
        )()


def test_network_control_center_passes_observer_into_orientation() -> None:
    orientation = FakeOrientationCenter()
    center = NetworkControlCenter(orientation_center=orientation, observer_core=FakeObserver())

    plan = center.create_plan({"text": "Почему вы выбрали этот стек?"}, intent="technical_reasoning", why_tag="evaluate_reasoning")

    assert plan.reason == "control-center"
    assert orientation.last_observer_report is not None
    assert orientation.last_observer_report["status"] == "watch"
    assert plan.observer_report["summary"]["trend"] == "stable"
