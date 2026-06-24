from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .causal import CausalAuditReport
from .contracts import EvidenceDecision, RouteDecision
from .pr_review_analysis import DiffAnalysis


def render_review_markdown(
    *,
    scenario: str,
    analysis: DiffAnalysis,
    decision: EvidenceDecision,
    causal_audit: CausalAuditReport,
    routes: Sequence[RouteDecision],
    contributions: Sequence[Mapping[str, Any]],
    protected_effect_written: bool,
    replay_decision: str,
    artifact: Optional[Mapping[str, Any]] = None,
) -> str:
    route_lines = "\n".join(
        f"- `{route.role_id}` -> `{route.selected_backend}`"
        for route in routes
    )
    contribution_lines = "\n".join(
        f"- **{item['role_id']}**: {item['summary']}"
        for item in contributions
    )
    finding_lines = "\n".join(f"- {item}" for item in analysis.findings)
    artifact_line = (
        "`artifact.json` with digest "
        f"`{artifact['integrity']['artifact_digest']}`"
        if artifact is not None
        else "Not created because the evidence decision was not ALLOW."
    )
    return (
        "# Trusted PR Review\n\n"
        f"**Scenario:** `{scenario.upper()}`  \n"
        f"**Evidence decision:** `{decision.decision.value}`  \n"
        f"**Decision reason:** `{decision.reason}`  \n"
        f"**Causal authorization:** `{causal_audit.authorization_allowed}`  \n"
        f"**Replay decision:** `{replay_decision}`  \n"
        f"**Protected effect written:** `{protected_effect_written}`\n\n"
        "## Diff summary\n\n"
        f"{analysis.summary}\n\n"
        f"Changed files: `{len(analysis.changed_files)}`; "
        f"added lines: `{analysis.added_lines}`; "
        f"removed lines: `{analysis.removed_lines}`.\n\n"
        "## Findings\n\n"
        f"{finding_lines}\n\n"
        "## Routes\n\n"
        f"{route_lines}\n\n"
        "## Contributions\n\n"
        f"{contribution_lines}\n\n"
        "## Reusable artifact\n\n"
        f"{artifact_line}\n\n"
        "## Safety boundary\n\n"
        "A HOLD or BLOCK decision never reaches ProofPath authorization or the "
        "CaPU-protected file effect. Replay inspects durable events and does not "
        "rerun models, tools, or side effects.\n"
    )
