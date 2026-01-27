import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

logger = logging.getLogger("CTE")


@dataclass
class LiminalAnchor:
    id: str
    decision: str
    alternatives: List[str]
    commitment: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "locked"  # locked -> resolved -> archived


@dataclass
class InsightNode:
    id: str
    parent_anchor_id: str
    content: str
    outcome_type: str  # "insight" | "conflict"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Convict:
    belief: str
    evidence: Dict[str, Any]
    confidence: float        # 0.0..1.0
    origin: str              # "liminal_experience" | "direct_learning" | "user_instruction" | "system_inference"
    strength: int
    timestamp: float         # epoch seconds
    last_validated: float    # epoch seconds

    def validate(self, new_evidence: Dict[str, Any]) -> bool:
        """
        Validates the belief against new evidence.
        - supports=True: increases confidence/strength
        - supports=False: decreases confidence, potentially weakens
        """
        supports = new_evidence.get("supports", True)
        now = datetime.now().timestamp()
        self.last_validated = now

        if supports:
            self.confidence = min(1.0, self.confidence + 0.1)
            self.strength += 1
            # Update evidence to latest
            self.evidence = new_evidence
            return True
        else:
            self.confidence = max(0.0, self.confidence - 0.2)
            # Evidence of conflict?
            return False

    @property
    def weakened(self) -> bool:
        return self.confidence < 0.5


class CognitiveTimelineEngine:
    """
    CTE v3.1:
    - Liminal Anchors (Choice)
    - Insights/Conflicts (Consequences)
    - Causal Chain: Choice -> Outcome
    - Oscillation Control (Anti-Runaway)
    - Convict Formation (Beliefs)
    """

    def __init__(self) -> None:
        self._anchors: Dict[str, LiminalAnchor] = {}
        self._insights: Dict[str, InsightNode] = {}
        # Key = belief string (consolidated)
        self._convicts: Dict[str, Convict] = {}

        self.active_anchor_id: Optional[str] = None
        self._trajectory: List[str] = []  # Stores node IDs in chronological order

        # Oscillation Control Config
        self.oscillation_threshold: int = 3
        self.oscillation_history: List[Dict[str, Any]] = []
        self.locked_due_to_oscillation: bool = False

    def reset_oscillation_lock(self) -> None:
        """Manually unlocks the system after an oscillation lock."""
        self.locked_due_to_oscillation = False
        # Do not clear history (needed for diagnostics)
        logger.info("🔓 Oscillation lock reset manually.")

    # --------- Liminal Transition API (Enhanced) ---------

    def _normalize_decision(self, decision: str) -> str:
        return decision.lower().strip()

    def _is_refinement(self, a: str, b: str) -> bool:
        """
        Refinement rule: B is refinement of A if:
        - B starts with A OR A is substring of B (and len(B) > len(A))
        - New token ratio <= 0.30
        """
        if not (b.startswith(a) or (a in b and len(b) > len(a))):
            return False

        tokens_a = set(re.findall(r"\w+", a))
        tokens_b = set(re.findall(r"\w+", b))
        if not tokens_a: return False # Avoid div by zero

        new_tokens = tokens_b - tokens_a
        ratio = len(new_tokens) / len(tokens_a)

        return ratio <= 0.30

    def check_oscillation(self, new_proposal: str) -> Dict[str, Any]:
        """
        Checks if the new proposal creates an ABAB pattern in the recent window.
        Returns: {is_oscillating, severity, attempt_count, recommendation, pattern, window_size}
        """
        if self.locked_due_to_oscillation:
            return {
                "is_oscillating": True,
                "severity": 1.0,
                "attempt_count": 0,
                "recommendation": "reject", # Spec says reject/lock.
                "pattern": None,
                "window_size": 0
            }

        # Analysis Window
        window_size = 2 * self.oscillation_threshold

        # Extract recent decisions from anchors in trajectory
        recent_decisions = []
        for node_id in reversed(self._trajectory):
            if node_id.startswith("anchor"):
                anchor = self._anchors.get(node_id)
                if anchor:
                    recent_decisions.insert(0, self._normalize_decision(anchor.decision))
            if len(recent_decisions) >= window_size:
                break

        normalized_new = self._normalize_decision(new_proposal)

        # Add new proposal tentatively to check pattern
        check_sequence = recent_decisions + [normalized_new]

        # Detect ABAB... pattern
        if len(check_sequence) < 2:
            return {"is_oscillating": False, "severity": 0.0, "attempt_count": 0, "recommendation": "allow", "pattern": None, "window_size": len(check_sequence)}

        attempt_count = 0
        pattern_found = None

        # We look for A -> B -> A -> B logic in the tail of the sequence
        # B is normalized_new.

        B = normalized_new
        A = check_sequence[-2] if len(check_sequence) >= 2 else None

        if A and A != B:
            # Check refinement
            is_ref = self._is_refinement(A, B) or self._is_refinement(B, A)
            if not is_ref:
                # Count alternating sequence at the end
                current_count = 1 # We have one A->B at the end

                # Check -3, -4 for B, A
                idx = len(check_sequence) - 3
                while idx >= 0:
                    prev_B = check_sequence[idx]
                    if idx - 1 < 0: break
                    prev_A = check_sequence[idx-1]

                    if prev_B == B and prev_A == A:
                        current_count += 1
                        idx -= 2
                    else:
                        break

                if current_count >= 2: # At least ABAB
                    attempt_count = current_count
                    pattern_found = [A, B] * current_count

        is_oscillating = attempt_count >= 2 # Minimal oscillation is ABAB (count 2)

        severity = 0.0
        recommendation = "allow"

        if is_oscillating:
            severity = min(1.0, attempt_count / self.oscillation_threshold)
            if attempt_count >= self.oscillation_threshold:
                recommendation = "lock"
            else:
                recommendation = "reject"

            # Log to history
            self.oscillation_history.append({
                "timestamp": datetime.now().isoformat(),
                "new_decision": new_proposal,
                "result": recommendation
            })

        return {
            "is_oscillating": is_oscillating,
            "severity": severity,
            "attempt_count": attempt_count,
            "recommendation": recommendation,
            "pattern": pattern_found,
            "window_size": len(check_sequence)
        }

    def commit_transition(self, decision: str, alternatives: Optional[List[str]] = None,
                          commitment: float = 0.9) -> Dict[str, Any]:
        """
        Creates a liminal anchor (decision point).
        Returns dict with status and anchor_id.
        """
        # 1. Check Oscillation
        osc = self.check_oscillation(decision)
        if osc["recommendation"] in ["reject", "lock"]:
             if osc["recommendation"] == "lock":
                 self.locked_due_to_oscillation = True
                 logger.critical(f"🔒 SYSTEM LOCKED due to oscillation! Pattern: {osc['pattern']}")

             return {
                 "status": "rejected_oscillation",
                 "anchor_id": self.active_anchor_id or "none",
                 "oscillation": osc
             }

        if alternatives is None:
            alternatives = []

        # 2. Proceed with creation
        # Use high-resolution timestamp to prevent ID collision in fast tests
        anchor_id = f"anchor_{datetime.now().timestamp()}"
        anchor = LiminalAnchor(
            id=anchor_id,
            decision=decision,
            alternatives=alternatives,
            commitment=commitment,
        )
        self._anchors[anchor_id] = anchor
        self.active_anchor_id = anchor_id
        self._trajectory.append(anchor_id)

        logger.info(
            f"🔒 LIMINAL LOCK: '{decision}' (commitment={commitment}, alternatives={alternatives})"
        )
        return {"status": "created", "anchor_id": anchor_id}

    # --------- Outcome & Convict API ---------

    def form_convict(self, anchor_id: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to form a belief (Convict) from the last outcome of an anchor.
        """
        # Find last insight for this anchor
        target_insight = None
        for node_id in reversed(self._trajectory):
            if node_id.startswith("insight"):
                node = self._insights.get(node_id)
                if node and node.parent_anchor_id == anchor_id:
                    target_insight = node
                    break

        if not target_insight:
            return None

        belief = target_insight.content
        evidence = {"source_id": target_insight.id, "content": target_insight.content, "supports": True}

        confidence = 0.7
        origin = "direct_learning"

        # Check if belief exists
        if belief in self._convicts:
            convict = self._convicts[belief]
            convict.validate(evidence)
            # Override evidence with new one as per spec
            convict.evidence = evidence
        else:
            convict = Convict(
                belief=belief,
                evidence=evidence,
                confidence=confidence,
                origin=origin,
                strength=1,
                timestamp=datetime.now().timestamp(),
                last_validated=datetime.now().timestamp()
            )
            self._convicts[belief] = convict
            logger.info(f"🧠 CONVICT FORMED: {convict.belief}")

        c = self._convicts[belief]
        return {
            "belief": c.belief,
            "evidence": c.evidence,
            "confidence": c.confidence,
            "origin": c.origin,
            "strength": c.strength,
            "timestamp": c.timestamp,
            "last_validated": c.last_validated,
            "weakened": c.weakened
        }

    def register_outcome(self, content: str, outcome_type: str = "insight") -> Dict[str, Any]:
        """
        Registers an outcome and attempts to form a convict.
        Closes the causal loop: Choice -> Outcome.
        """
        if not self.active_anchor_id:
            logger.warning("⚠️ Outcome without active anchor.")
            return {"status": "error", "reason": "no_active_anchor"}

        anchor = self._anchors.get(self.active_anchor_id)
        if not anchor:
            return {"status": "error", "reason": "anchor_not_found"}

        insight_id = f"insight_{datetime.now().timestamp()}"
        node = InsightNode(
            id=insight_id,
            parent_anchor_id=anchor.id,
            content=content,
            outcome_type=outcome_type,
        )
        self._insights[insight_id] = node
        self._trajectory.append(insight_id)

        anchor.status = "resolved"
        logger.info(
            f"💡 {outcome_type.upper()}: '{content}' derived from '{anchor.decision}'"
        )

        # Attempt to form convict
        convict_data = self.form_convict(anchor.id)

        # Reset active anchor — cycle complete
        self.active_anchor_id = None

        return {
            "status": "success",
            "insight_id": insight_id,
            "convict": convict_data
        }

    def get_convicts(self, min_confidence: float = 0.7) -> List[Dict[str, Any]]:
        """Retrieves active beliefs meeting confidence threshold, sorted."""
        candidates = [c for c in self._convicts.values() if c.confidence >= min_confidence]

        # Sort: confidence desc, strength desc, last_validated desc
        candidates.sort(key=lambda x: (x.confidence, x.strength, x.last_validated), reverse=True)

        results = []
        for c in candidates:
            results.append({
                "belief": c.belief,
                "confidence": c.confidence,
                "strength": c.strength,
                "origin": c.origin,
                "last_validated": c.last_validated
            })
        return results

    # --------- Read-only views for CaPUv3 ---------

    def export_summary(self) -> Dict[str, Any]:
        """
        Brief snapshot of CTE for prompt inclusion:
        - Active anchor (or last relevant one)
        - Last outcome
        """
        active_anchor = None
        if self.active_anchor_id:
            active_anchor = self._anchors.get(self.active_anchor_id)
        else:
            # Fallback: Find the last anchor in trajectory
            for node_id in reversed(self._trajectory):
                if node_id.startswith("anchor"):
                    active_anchor = self._anchors.get(node_id)
                    break

        last_insight: Optional[InsightNode] = None
        # Find last insight in trajectory
        for node_id in reversed(self._trajectory):
            if node_id.startswith("insight"):
                last_insight = self._insights.get(node_id)
                if last_insight:
                    break

        summary: Dict[str, Any] = {}
        if active_anchor:
            summary["active_anchor"] = {
                "decision": active_anchor.decision,
                "commitment": active_anchor.commitment,
                "status": active_anchor.status,
            }
        if last_insight:
            summary["last_outcome"] = {
                "content": last_insight.content,
                "type": last_insight.outcome_type,
                "from_decision": last_insight.parent_anchor_id,
            }
        return summary
