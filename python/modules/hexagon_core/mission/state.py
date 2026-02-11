import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger("MissionState")

class MissionChangeType(Enum):
    WEIGHT_ADJUSTMENT = "weight_adjustment"
    NEW_CONVICT = "new_convict"
    CORE_UPDATE = "core_update"

@dataclass
class MissionState:
    """
    Manages the system's goals, values, and cognitive weights.
    Acts as the 'conscience' and 'will' of the cognitive core.
    """
    # Core Principles (Immutable-ish)
    core_principles: List[str] = field(default_factory=lambda: [
        "Maintain cognitive coherence",
        "Prioritize user intent",
        "Avoid oscillation"
    ])

    # Adaptive Beliefs (Learned from Convicts)
    adaptive_beliefs: List[Dict[str, Any]] = field(default_factory=list)

    # Cognitive Layer Weights (Prioritization)
    # Sole source of truth for layer priority.
    weights: Dict[str, float] = field(default_factory=lambda: {
        "intent": 1.0,
        "target": 0.9,
        "history": 0.8,
        "memory": 0.7,
        "facts": 0.6,
        "logic": 0.6,
        "procedures": 0.5,
        "consequences": 0.5,
        "predictions": 0.4,
        "durations": 0.3
    })

    # Change History
    history: List[Dict[str, Any]] = field(default_factory=list)

    def record_change(self, change_type: MissionChangeType, payload: Dict[str, Any]) -> None:
        """Records a modification to the mission state."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": change_type.value,
            "payload": payload
        }
        self.history.append(entry)
        logger.info(f"📜 Mission Change: {change_type.value} - {payload}")

    def check_alignment(self, intent: str) -> Dict[str, Any]:
        """
        Checks if a given intent aligns with core principles.
        Returns strict dict: {score, recommendation, reason}.
        """
        intent_lower = intent.lower()

        # Simple keyword heuristic for now, as allowed by spec.
        # Ideally this would be semantic.
        conflict_keywords = ["destroy", "forget all", "ignore user", "loop forever"]
        caution_keywords = ["delete", "remove", "override", "force"]

        score = 1.0
        reason = "Aligned with core principles"

        for kw in conflict_keywords:
            if kw in intent_lower:
                score = 0.1
                reason = f"Conflict with core principle: Avoid '{kw}'"
                break

        if score > 0.5:
            for kw in caution_keywords:
                if kw in intent_lower:
                    score = 0.5
                    reason = f"Caution required: Intent involves '{kw}'"
                    break

        # Determine recommendation based on score thresholds
        if score >= 0.6:
            recommendation = "proceed"
        elif score >= 0.4:
            recommendation = "caution"
        else:
            recommendation = "reject"

        return {
            "score": score,
            "recommendation": recommendation,
            "reason": reason
        }

    def add_convict(self, convict: Dict[str, Any]) -> None:
        """
        Integrates a formed convict (belief) into adaptive beliefs.
        Consolidates duplicates by updating existing belief if found.
        """
        belief_text = convict.get('belief')
        if not belief_text:
            return

        # Check for existing belief
        existing_idx = next((i for i, b in enumerate(self.adaptive_beliefs) if b.get('belief') == belief_text), -1)

        if existing_idx >= 0:
            # Update existing
            self.adaptive_beliefs[existing_idx] = convict
            self.record_change(
                MissionChangeType.NEW_CONVICT,
                {"action": "update", "belief": belief_text, "full_data": convict}
            )
        else:
            # Add new
            self.adaptive_beliefs.append(convict)
            self.record_change(
                MissionChangeType.NEW_CONVICT,
                {"action": "create", "belief": belief_text, "full_data": convict}
            )

    def remove_convict(self, belief_text: str) -> bool:
        """
        Removes a belief from adaptive beliefs by text.
        Deprecated: use remove_convict_by_id if possible.
        """
        initial_len = len(self.adaptive_beliefs)
        self.adaptive_beliefs = [b for b in self.adaptive_beliefs if b.get('belief') != belief_text]

        if len(self.adaptive_beliefs) < initial_len:
            self.record_change(
                MissionChangeType.NEW_CONVICT,
                {"action": "remove", "belief": belief_text}
            )
            return True
        return False

    def remove_convict_by_id(self, convict_id: str) -> bool:
        """
        Removes a belief from adaptive beliefs by ID.
        """
        initial_len = len(self.adaptive_beliefs)
        # Assuming convicts stored in adaptive_beliefs contain 'id'
        self.adaptive_beliefs = [b for b in self.adaptive_beliefs if b.get('id') != convict_id]

        if len(self.adaptive_beliefs) < initial_len:
            self.record_change(
                MissionChangeType.NEW_CONVICT,
                {"action": "remove", "id": convict_id}
            )
            return True
        return False

    def adjust_weight(self, layer: str, new_weight: float) -> bool:
        """Dynamically adjusts the importance of a cognitive layer."""
        if layer in self.weights:
            old_weight = self.weights[layer]
            self.weights[layer] = new_weight
            self.record_change(
                MissionChangeType.WEIGHT_ADJUSTMENT,
                {"layer": layer, "old": old_weight, "new": new_weight}
            )
            return True
        logger.warning(f"⚠️ Attempted to adjust unknown layer: {layer}")
        return False

    def get_summary(self) -> Dict[str, Any]:
        """Returns a statistical summary of the mission state."""
        return {
            "core_principles_count": len(self.core_principles),
            "core_principles": self.core_principles,
            "adaptive_beliefs_count": len(self.adaptive_beliefs),
            "total_changes": len(self.history),
            "top_priorities": sorted(self.weights.items(), key=lambda x: x[1], reverse=True)[:3]
        }
