from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules.graph.models import CollectiveRelationalSelf, RelationalSelf


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CollectiveRelationalSelfEngine:
    """Merge multiple RelationalSelf snapshots into a collective representation."""

    def merge(self, *, fellowship_id: str, members: dict[str, RelationalSelf]) -> CollectiveRelationalSelf:
        member_ids = sorted(members.keys())
        core_nodes: list[dict[str, Any]] = []
        emotional_arc: list[dict[str, Any]] = []
        tones: dict[str, int] = {}
        coherence_scores: list[float] = []

        for member_id, snapshot in members.items():
            coherence_scores.append(float(snapshot.self_coherence_score or 0.0))
            for node in list(snapshot.core_nodes or []):
                if not isinstance(node, dict):
                    continue
                enriched = dict(node)
                enriched.setdefault("member_id", member_id)
                core_nodes.append(enriched)

            emotional = dict(snapshot.emotional_summary or {})
            tone = str(emotional.get("dominant_tone") or snapshot.last_emotional_state or "neutral")
            tones[tone] = tones.get(tone, 0) + 1
            emotional_arc.append(
                {
                    "timestamp": _utc_now(),
                    "member_id": member_id,
                    "tone": tone,
                    "bond_strength": float(snapshot.bond_strength or emotional.get("bond_strength", 0.0) or 0.0),
                }
            )

        dominant_tone = "neutral"
        if tones:
            dominant_tone = sorted(tones.items(), key=lambda item: item[1], reverse=True)[0][0]
        coherence = sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.0

        return CollectiveRelationalSelf(
            fellowship_id=str(fellowship_id or ""),
            member_ids=member_ids,
            merged_core_nodes=core_nodes[:100],
            merged_emotional_summary={
                "dominant_tone": dominant_tone,
                "member_count": len(member_ids),
                "tone_distribution": tones,
            },
            collective_emotional_arc=emotional_arc[-200:],
            collective_coherence_score=coherence,
            metadata={"merged_at": _utc_now()},
        )
