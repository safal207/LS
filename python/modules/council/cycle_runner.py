from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.cognition.relational_self import RelationalSelfBuilder
from modules.council.council_engine import RelationalCouncilEngine
from modules.graph.models import RelationalSelf


@dataclass
class CouncilCycleRunner:
    self_builder: RelationalSelfBuilder
    engine: RelationalCouncilEngine

    def run(
        self,
        *,
        cycle_id: str | None = None,
        mode: str = "self-consistency-check",
        omni_insight: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        relational_self: RelationalSelf = self.self_builder.update(
            cycle_id=cycle_id,
            source="council_cycle",
            omni_insight=omni_insight,
        )
        outcome = self.engine.run_mode(mode=mode, relational_self=relational_self)
        return {
            "cycle_id": cycle_id,
            "mode": mode,
            "relational_self": relational_self.to_dict(),
            "council_outcome": outcome,
            "relational_breach": self.engine.detect_breach(relational_self).__dict__,
        }
