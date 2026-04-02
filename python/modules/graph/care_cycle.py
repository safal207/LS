from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from .derived_module_registry import DerivedModuleRegistry
from .models import DerivedModule


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CareCycleResult:
    module_id: str
    action: str
    state: str
    trust_score: float
    quality_score: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class CareCycleRunner:
    def __init__(
        self,
        registry: DerivedModuleRegistry,
        *,
        min_quality: float = 0.68,
        min_trust: float = 0.58,
        retire_trust: float = 0.35,
        promote_bonus: float = 0.03,
        demote_penalty: float = 0.08,
    ) -> None:
        self.registry = registry
        self.min_quality = min_quality
        self.min_trust = min_trust
        self.retire_trust = retire_trust
        self.promote_bonus = promote_bonus
        self.demote_penalty = demote_penalty

    def review(self, module: DerivedModule | str) -> Optional[CareCycleResult]:
        current = self.registry.get_module(module) if isinstance(module, str) else module
        if current is None:
            return None

        action = "keep"
        reason = "stable"

        if current.trust_score <= self.retire_trust or (current.runs >= 3 and current.successes == 0):
            current.state = "retired"
            current.trust_score = round(max(0.0, current.trust_score - self.demote_penalty), 4)
            action = "retire"
            reason = "low-trust-or-zero-success"
        elif current.quality_score < self.min_quality or current.trust_score < self.min_trust:
            current.state = "review"
            current.trust_score = round(max(0.0, current.trust_score - self.demote_penalty), 4)
            action = "demote"
            reason = "quality-or-trust-below-threshold"
        else:
            current.state = "active"
            current.trust_score = round(min(1.0, current.trust_score + self.promote_bonus), 4)
            action = "promote" if current.runs > 0 else "keep"
            reason = "healthy-module"

        current.care_cycles += 1
        current.last_reviewed_at = _utc_now()
        saved = self.registry.save_module(current)
        return CareCycleResult(
            module_id=saved.module_id,
            action=action,
            state=saved.state,
            trust_score=saved.trust_score,
            quality_score=saved.quality_score,
            reason=reason,
        )
