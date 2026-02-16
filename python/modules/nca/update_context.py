from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .assembly import AgentState

@dataclass(frozen=True)
class UpdateContext:
    """
    Phase 12.1 Deterministic Context Propagation (DCP).
    Immutable context object passed between engines to eliminate hidden dependencies.
    """

    # Base Context
    t: int
    state: AgentState | None
    collective_state: dict[str, Any]

    # Layer 1-2: Self-Model & Meta-Cognition
    self_snapshot: dict[str, Any] | None = None
    orientation_snapshot: dict[str, Any] | None = None
    meta_report: dict[str, Any] | None = None
    metafeedback: dict[str, Any] | None = None

    # Layer 3: Identity
    identity_snapshot: dict[str, Any] | None = None
    initiative: dict[str, Any] | None = None

    # Layer 4: Social
    social_snapshot: dict[str, Any] | None = None
    social_alignment: float | None = None
    cooperative_adjustments: dict[str, Any] | None = None

    # Layer 5: Culture
    culture_snapshot: dict[str, Any] | None = None
    cultural_alignment: float | None = None
    civilization_adjustments: dict[str, Any] | None = None

    # Layer 6: Derived Engines
    militocracy_snapshot: dict[str, Any] | None = None
    synergy_snapshot: dict[str, Any] | None = None

    # Layer 7: Values
    values_snapshot: dict[str, Any] | None = None
    value_alignment: float | None = None

    # Layer 8: Autonomy
    autonomy_snapshot: dict[str, Any] | None = None
    primary_strategy: dict[str, Any] | None = None
    strategies: list[dict[str, Any]] | None = None

    # Layer 9: Intent
    intent_snapshot: dict[str, Any] | None = None
    primary_intent: dict[str, Any] | None = None
    intents: list[dict[str, Any]] | None = None

    def evolve(self, **kwargs: Any) -> UpdateContext:
        """Returns a new UpdateContext with updated fields."""
        return replace(self, **kwargs)
