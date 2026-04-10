from __future__ import annotations

# ValidationEscalationHandler — acts on review_required signals from governance.
#
# When ValidationGovernanceEngine sets review_required=True it means the round
# is not safe to treat as settled consensus.  The base validator and governance
# layer emit the signal; what happens next is the escalation handler's job.
#
# Three implementations ship here:
#   NullEscalationHandler    — does nothing (default / tests)
#   LoggingEscalationHandler — logs a structured warning (production default)
#   RaisingEscalationHandler — raises EscalationRequired (strict / CI gate)
#
# Wire into CollectiveAnswerValidator via the escalation_handler= constructor
# parameter.  The handler is called only when review_required is True.

import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ls.cognition.collective_answer_validator import ValidationResult
    from ls.cognition.validation_governance import ValidationGovernanceReport

logger = logging.getLogger(__name__)


class EscalationRequired(Exception):
    """Raised by RaisingEscalationHandler when review_required is True."""

    def __init__(
        self,
        result: ValidationResult,
        report: ValidationGovernanceReport,
    ) -> None:
        self.result = result
        self.report = report
        reasons = "; ".join(report.escalation_recommendations) or "governance review required"
        super().__init__(
            f"Validation round requires review: winner={result.winner_agent_id!r} "
            f"status={result.consensus_status!r} — {reasons}"
        )


class ValidationEscalationHandler(Protocol):
    """Called after validation when governance sets review_required=True."""

    def handle_escalation(
        self,
        result: ValidationResult,
        report: ValidationGovernanceReport,
    ) -> None: ...


class NullEscalationHandler:
    """Does nothing — default for tests and contexts without escalation logic."""

    def handle_escalation(
        self,
        result: ValidationResult,
        report: ValidationGovernanceReport,
    ) -> None:
        return


class LoggingEscalationHandler:
    """Emits a structured warning log.  Safe for production use."""

    def __init__(self, *, log_level: int = logging.WARNING) -> None:
        self._level = log_level

    def handle_escalation(
        self,
        result: ValidationResult,
        report: ValidationGovernanceReport,
    ) -> None:
        logger.log(
            self._level,
            "Validation escalation: round requires human review",
            extra={
                "winner_agent_id": result.winner_agent_id,
                "governed_winner_agent_id": report.governed_winner_agent_id,
                "consensus_status": result.consensus_status,
                "governance_flags": report.governance_flags,
                "escalation_recommendations": report.escalation_recommendations,
                "coalition_alerts": len(report.coalition_alerts),
                "review_required": report.review_required,
            },
        )


class RaisingEscalationHandler:
    """Raises EscalationRequired — use in strict pipelines or CI gates."""

    def handle_escalation(
        self,
        result: ValidationResult,
        report: ValidationGovernanceReport,
    ) -> None:
        raise EscalationRequired(result, report)
