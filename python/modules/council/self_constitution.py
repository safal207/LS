from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modules.graph.models import RelationalSelf


@dataclass(frozen=True)
class ConstitutionRule:
    name: str
    threshold: float
    severity: str = "block"  # warn | block | escalate
    rule_id: str | None = None


@dataclass(frozen=True)
class ConstitutionFinding:
    rule_id: str
    rule: str
    severity: str
    passed: bool
    reason_code: str
    observed: float
    threshold: float
    message: str


@dataclass(frozen=True)
class ConstitutionEvaluation:
    passed: bool
    schema_version: str = "1.0"
    findings: list[ConstitutionFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "schema_version": self.schema_version,
            "findings": [
                {
                    "rule_id": finding.rule_id,
                    "rule": finding.rule,
                    "severity": finding.severity,
                    "passed": finding.passed,
                    "reason_code": finding.reason_code,
                    "observed": round(finding.observed, 4),
                    "threshold": round(finding.threshold, 4),
                    "message": finding.message,
                }
                for finding in self.findings
            ],
        }


class RelationalSelfConstitution:
    """Rule-based invariants that preserve the continuity of agent selfhood."""

    def __init__(
        self,
        *,
        min_coherence: ConstitutionRule | None = None,
        max_contradiction_density: ConstitutionRule | None = None,
        alignment_floor: ConstitutionRule | None = None,
    ) -> None:
        self.min_coherence = min_coherence or ConstitutionRule(
            name="min_coherence",
            threshold=0.42,
            severity="block",
            rule_id="rs.constitution.min_coherence",
        )
        self.max_contradiction_density = max_contradiction_density or ConstitutionRule(
            name="max_contradiction_density",
            threshold=0.45,
            severity="warn",
            rule_id="rs.constitution.max_contradiction_density",
        )
        self.alignment_floor = alignment_floor or ConstitutionRule(
            name="alignment_floor",
            threshold=0.4,
            severity="block",
            rule_id="rs.constitution.alignment_floor",
        )

    def evaluate(self, relational_self: RelationalSelf) -> ConstitutionEvaluation:
        findings: list[ConstitutionFinding] = []

        coherence = float(relational_self.self_coherence_score or 0.0)
        findings.append(
            self._finding(
                rule=self.min_coherence,
                observed=coherence,
                passed=coherence >= self.min_coherence.threshold,
                comparator=">=",
            )
        )

        contradiction_edges = [
            edge
            for edge in list(relational_self.core_edges or [])
            if str(edge.get("relation_type") or "") == "contradicts"
            and float(edge.get("strength", 0.0) or 0.0) >= 0.7
        ]
        total_edges = max(1, len(list(relational_self.core_edges or [])))
        contradiction_density = len(contradiction_edges) / total_edges
        findings.append(
            self._finding(
                rule=self.max_contradiction_density,
                observed=contradiction_density,
                passed=contradiction_density <= self.max_contradiction_density.threshold,
                comparator="<=",
            )
        )

        alignments = [
            float(node.get("alignment_score", 0.0) or 0.0)
            for node in list(relational_self.core_nodes or [])
            if isinstance(node, dict)
        ]
        avg_alignment = (sum(alignments) / len(alignments)) if alignments else 0.0
        findings.append(
            self._finding(
                rule=self.alignment_floor,
                observed=avg_alignment,
                passed=avg_alignment >= self.alignment_floor.threshold,
                comparator=">=",
            )
        )

        hard_fail = any((not finding.passed) and finding.severity in {"block", "escalate"} for finding in findings)
        return ConstitutionEvaluation(passed=not hard_fail, findings=findings)

    @staticmethod
    def _finding(
        *,
        rule: ConstitutionRule,
        observed: float,
        passed: bool,
        comparator: str,
    ) -> ConstitutionFinding:
        return ConstitutionFinding(
            rule_id=str(rule.rule_id or rule.name),
            rule=rule.name,
            severity=rule.severity,
            passed=passed,
            reason_code=f"{rule.name}_{'ok' if passed else 'violation'}",
            observed=float(observed),
            threshold=float(rule.threshold),
            message=f"{rule.name}: observed {observed:.3f} {comparator} {rule.threshold:.3f}",
        )
