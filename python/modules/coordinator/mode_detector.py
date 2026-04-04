"""
Mode Detector - Analyzes input to determine A vs B

v0.1 skeleton: Returns decision based on simple heuristics
v0.2: Will use metrics, confidence, learned patterns
"""

from typing import Literal, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class ModeAnalysis:
    """Result of input analysis."""
    mode: Literal["A", "B", "both"]
    cognitive_mode: Literal["reactive", "deliberative", "creative"]
    engine_route: list[str]
    complexity_score: float  # 0.0 to 1.0
    ambiguity_score: float   # 0.0 to 1.0
    explanation_needed: bool
    load_factor: float       # 0.0 to 1.0
    reason: str
    timestamp: float


class ModeDetector:
    """Analyzes input to choose between Fast (A) and Deep (B) mode."""

    def analyze(
        self,
        input_data: str,
        context: Dict[str, Any],
        system_load: float = 0.0,
    ) -> ModeAnalysis:
        """
        v0.1: Simple heuristics
        v0.2: Will use ML models or learned patterns

        Decision tree (v0.1):
            1. If input is very simple (< 5 words, no questions) -> "A"
            2. If system under heavy load AND input medium -> "A"
            3. If input requires explanation ("why", "how", "explain") -> "B"
            4. If input is ambiguous OR complex -> "B"
            5. Default: "both" (safe, but slower)
        """

        # v0.2: Extended metrics for mode-family selection and routing.
        complexity = self._compute_complexity(input_data)
        ambiguity = self._compute_ambiguity(input_data)
        needs_explanation = self._needs_explanation(input_data)
        creative_request = self._is_creative_request(input_data, context)

        # v0.2: Select cognitive mode family first.
        if creative_request and system_load < 0.95:
            cognitive_mode = "creative"
            mode = "both"
            reason = "Creative request detected"
        elif system_load >= 0.8 and complexity <= 0.6 and not needs_explanation:
            cognitive_mode = "reactive"
            mode = "A"
            reason = "High load, prefer fast mode"
        elif complexity > 0.6 or needs_explanation or ambiguity > 0.5:
            cognitive_mode = "deliberative"
            mode = "B"
            reason = "Complex/ambiguous input or explanation needed"
        elif complexity < 0.3 and ambiguity < 0.25 and system_load < 0.5:
            cognitive_mode = "reactive"
            mode = "A"
            reason = "Simple input, low load"
        else:
            cognitive_mode = "deliberative"
            mode = "both"
            reason = "Medium complexity, verify with both modes"

        engine_route = self._build_engine_route(cognitive_mode, needs_explanation)

        return ModeAnalysis(
            mode=mode,
            cognitive_mode=cognitive_mode,
            engine_route=engine_route,
            complexity_score=complexity,
            ambiguity_score=ambiguity,
            explanation_needed=needs_explanation,
            load_factor=system_load,
            reason=reason,
            timestamp=time.time(),
        )

    def _build_engine_route(self, cognitive_mode: str, needs_explanation: bool) -> list[str]:
        if cognitive_mode == "reactive":
            route = ["perception", "policy_executor"]
        elif cognitive_mode == "creative":
            route = ["ideation_engine", "reasoning_engine", "novelty_guard"]
        else:
            route = ["reasoning_engine", "context_sync", "verifier"]
        if needs_explanation and "explanation_engine" not in route:
            route.append("explanation_engine")
        return route

    def _compute_complexity(self, input_data: str) -> float:
        """
        v0.1: Simple heuristic based on length and structure
        v0.2: Will use linguistic analysis or learned model

        Returns: 0.0 (simple) to 1.0 (complex)
        """
        word_count = len(input_data.split())

        # Very simple heuristic
        if word_count < 3:
            return 0.1
        elif word_count < 10:
            return 0.3
        elif word_count < 30:
            return 0.5
        else:
            return 0.8

    def _compute_ambiguity(self, input_data: str) -> float:
        """
        v0.1: Check for ambiguous markers ("could", "might", "maybe")
        v0.2: Will use semantic analysis

        Returns: 0.0 (clear) to 1.0 (ambiguous)
        """
        ambiguous_markers = {"could", "might", "maybe", "unclear", "confused"}
        input_lower = input_data.lower()

        count = sum(1 for marker in ambiguous_markers if marker in input_lower)
        return min(count * 0.2, 1.0)

    def _needs_explanation(self, input_data: str) -> bool:
        """
        v0.1: Check for explanation markers ("why", "how", "explain")
        v0.2: Will use intent detection
        """
        explanation_markers = {"why", "how", "explain", "reason", "understand"}
        input_lower = input_data.lower()

        return any(marker in input_lower for marker in explanation_markers)

    def _is_creative_request(self, input_data: str, context: Dict[str, Any]) -> bool:
        input_lower = input_data.lower()
        markers = {
            "creative",
            "creativity",
            "brainstorm",
            "invent",
            "novel",
            "design",
            "story",
            "idea",
        }
        if any(marker in input_lower for marker in markers):
            return True

        hint = str((context or {}).get("intent", "")).lower()
        if "creative" in hint or "ideation" in hint:
            return True
        return False
