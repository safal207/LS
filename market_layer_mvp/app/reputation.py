from __future__ import annotations

from .models import Agent


def update_reputation(agent: Agent, artifact_quality: float) -> float:
    agent.reputation = 0.7 * agent.reputation + 0.3 * artifact_quality
    return agent.reputation
