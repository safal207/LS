"""Formatting utilities for Reflection Dashboard proposal rendering."""

from __future__ import annotations

from typing import Any, Dict, List


def format_proposal(proposal: Dict[str, Any]) -> str:
    """Render a single proposal as a compact multi-line summary."""
    return "\n".join(
        [
            f"Proposal ID: {proposal.get('proposal_id')}",
            f"Change Type: {proposal.get('change_type')} -> {proposal.get('target')}",
            f"Proposed Value: {proposal.get('proposed_value')}",
            f"Reason: {proposal.get('reason')}",
            f"Confidence: {float(proposal.get('confidence', 0.0)):.2f}",
            f"Expected Gain: {proposal.get('expected_gain')}",
            f"Auto Apply: {proposal.get('auto_apply')}",
        ]
    )


def format_proposals(proposals: List[Dict[str, Any]]) -> str:
    """Render a proposal list into a user-readable text block."""
    if not proposals:
        return "No proposals generated — data insufficient or stable."

    return "\n".join(f"{format_proposal(item)}\n{'-' * 60}" for item in proposals)
