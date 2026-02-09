from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .trust_graph import GraphTrustFSM, GraphTrustLevel


@dataclass(frozen=True)
class RoutingPolicy:
    max_hops: int = 3


def should_route(destination: str, origin: str, hops: list[str], trust: GraphTrustFSM, policy: RoutingPolicy) -> bool:
    if destination == origin:
        return True
    if destination in hops:
        return False
    if len(hops) >= policy.max_hops:
        return False
    if trust.get(destination) == GraphTrustLevel.BLOCKED:
        return False
    return True


def next_hop(destination: str, origin: str, hops: list[str], trust: GraphTrustFSM, policy: RoutingPolicy) -> Optional[str]:
    if not should_route(destination, origin, hops, trust, policy):
        return None
    return destination
