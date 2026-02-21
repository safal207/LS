from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Protocol


@dataclass(frozen=True)
class FederationDecision:
    allowed: bool
    reason: str
    policy: str


class FederationPolicy(Protocol):
    def evaluate(self, envelope: Dict[str, Any]) -> FederationDecision: ...


@dataclass(frozen=True)
class AllowAllFederationPolicy:
    policy_name: str = "allow_all"

    def evaluate(self, envelope: Dict[str, Any]) -> FederationDecision:
        _ = envelope
        return FederationDecision(allowed=True, reason="allowed", policy=self.policy_name)


@dataclass(frozen=True)
class DenylistFederationPolicy:
    blocked_senders: frozenset[str] = field(default_factory=frozenset)
    blocked_receivers: frozenset[str] = field(default_factory=frozenset)
    blocked_message_types: frozenset[str] = field(default_factory=frozenset)
    policy_name: str = "denylist"

    def __post_init__(self) -> None:
        # Normalize incoming iterables so runtime lookup remains O(1).
        object.__setattr__(self, "blocked_senders", frozenset(self.blocked_senders))
        object.__setattr__(self, "blocked_receivers", frozenset(self.blocked_receivers))
        object.__setattr__(self, "blocked_message_types", frozenset(self.blocked_message_types))

    @classmethod
    def from_iterables(
        cls,
        *,
        blocked_senders: Iterable[str] = (),
        blocked_receivers: Iterable[str] = (),
        blocked_message_types: Iterable[str] = (),
    ) -> "DenylistFederationPolicy":
        return cls(
            blocked_senders=frozenset(blocked_senders),
            blocked_receivers=frozenset(blocked_receivers),
            blocked_message_types=frozenset(blocked_message_types),
        )

    def evaluate(self, envelope: Dict[str, Any]) -> FederationDecision:
        message_type = str(envelope.get("type", ""))
        sender = _extract_agent_id(envelope.get("sender"))
        receiver = _extract_agent_id(envelope.get("receiver"))

        if message_type in self.blocked_message_types:
            return FederationDecision(
                allowed=False,
                reason=f"blocked_message_type:{message_type}",
                policy=self.policy_name,
            )
        if sender and sender in self.blocked_senders:
            return FederationDecision(
                allowed=False,
                reason=f"blocked_sender:{sender}",
                policy=self.policy_name,
            )
        if receiver and receiver in self.blocked_receivers:
            return FederationDecision(
                allowed=False,
                reason=f"blocked_receiver:{receiver}",
                policy=self.policy_name,
            )
        return FederationDecision(allowed=True, reason="allowed", policy=self.policy_name)


def _extract_agent_id(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    agent_id = node.get("agent_id")
    if not isinstance(agent_id, str):
        return None
    return agent_id
