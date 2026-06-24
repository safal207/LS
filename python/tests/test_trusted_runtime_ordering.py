from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.trusted_runtime.contracts import WorkflowPlan


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "python"
    / "tests"
    / "fixtures"
    / "trusted-runtime"
    / "valid_workflow_plan.json"
)


def test_workflow_rejects_parent_and_dependency_from_future_step() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["steps"] = [payload["steps"][1], payload["steps"][0]]

    with pytest.raises(ValueError, match="unavailable parent cause"):
        WorkflowPlan.from_mapping(payload)
