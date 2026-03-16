from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


class ReputationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AgentReputation:
    agent_id: str
    reputation_score: float
    quality_ema: float
    contribution_ema: float
    updates_count: int


class ReputationEngine:
    """Sprint 5 baseline reputation memory.

    reputation(t+1) = (1-decay) * reputation(t) + λ*quality + μ*contribution
    with clamp to [0, 1].
    """

    def __init__(self, quality_weight: float = 0.25, contribution_weight: float = 0.15, decay: float = 0.10) -> None:
        self._quality_weight = quality_weight
        self._contribution_weight = contribution_weight
        self._decay = decay
        self._lock = RLock()
        self._state: dict[str, AgentReputation] = {}

    def get(self, agent_id: str) -> AgentReputation:
        with self._lock:
            return self._state.get(
                agent_id,
                AgentReputation(
                    agent_id=agent_id,
                    reputation_score=0.5,
                    quality_ema=0.5,
                    contribution_ema=0.0,
                    updates_count=0,
                ),
            )

    def update(self, agent_id: str, quality_score: float, contribution_score: float) -> AgentReputation:
        if not 0 <= quality_score <= 1:
            raise ReputationError("INVALID_QUALITY", "quality_score must be in [0,1]")
        if contribution_score < 0:
            raise ReputationError("INVALID_CONTRIBUTION", "contribution_score must be >= 0")

        with self._lock:
            prev = self.get(agent_id)
            normalized_contribution = min(contribution_score, 1.0)
            q_ema = self._ema(prev.quality_ema, quality_score, alpha=0.3)
            c_ema = self._ema(prev.contribution_ema, normalized_contribution, alpha=0.3)

            next_score = (1 - self._decay) * prev.reputation_score
            next_score += self._quality_weight * q_ema
            next_score += self._contribution_weight * c_ema
            next_score = max(0.0, min(1.0, next_score))

            current = AgentReputation(
                agent_id=agent_id,
                reputation_score=round(next_score, 6),
                quality_ema=round(q_ema, 6),
                contribution_ema=round(c_ema, 6),
                updates_count=prev.updates_count + 1,
            )
            self._state[agent_id] = current
            return current

    @staticmethod
    def _ema(prev: float, value: float, alpha: float) -> float:
        return alpha * value + (1 - alpha) * prev
