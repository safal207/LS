"""Standalone PyQt dashboard for DecisionPipeline reflection proposals."""

from __future__ import annotations

import sys
from typing import Any, Dict, List

from .decision_pipeline import DecisionPipeline

from importlib.util import find_spec

if find_spec('PyQt6') is not None:  # pragma: no cover - runtime dependent
    from PyQt6.QtWidgets import QApplication, QPushButton, QTextEdit, QVBoxLayout, QWidget
else:  # pragma: no cover - runtime dependent
    from PyQt5.QtWidgets import QApplication, QPushButton, QTextEdit, QVBoxLayout, QWidget


class ReflectionWidget(QWidget):
    """Minimal UI to trigger and inspect reflection proposals."""

    def __init__(self, pipeline: DecisionPipeline):
        super().__init__()
        self.pipeline = pipeline
        self.setWindowTitle("Reflection Engine Dashboard")
        self.resize(700, 480)

        layout = QVBoxLayout(self)

        self.reflect_button = QPushButton("Reflect")
        self.reflect_button.clicked.connect(self.show_reflections)
        layout.addWidget(self.reflect_button)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def show_reflections(self) -> None:
        """Fetch proposals from pipeline and render a readable summary."""
        proposals = self.pipeline.reflect_and_propose()
        self.output.setPlainText(self._format_proposals(proposals))

    @staticmethod
    def _format_proposals(proposals: List[Dict[str, Any]]) -> str:
        if not proposals:
            return "No proposals generated — data insufficient or stable."

        blocks: List[str] = []
        for proposal in proposals:
            blocks.append(
                "\n".join(
                    [
                        f"Proposal ID: {proposal.get('proposal_id')}",
                        f"Change Type: {proposal.get('change_type')} -> {proposal.get('target')}",
                        f"Proposed Value: {proposal.get('proposed_value')}",
                        f"Reason: {proposal.get('reason')}",
                        f"Confidence: {proposal.get('confidence', 0.0):.2f}",
                        f"Expected Gain: {proposal.get('expected_gain')}",
                        f"Auto Apply: {proposal.get('auto_apply')}",
                    ]
                )
            )
        return "\n".join(f"{block}\n{'-' * 60}" for block in blocks)


def build_demo_pipeline() -> DecisionPipeline:
    """Build a pipeline with synthetic history to make reflections visible in demo mode."""
    cognitive_state: Dict[str, Any] = {
        "action_history": [
            {"success": True} for _ in range(45)
        ]
        + [{"success": False} for _ in range(5)],
        "strategy_stats": {
            "retrieve_context": {"successes": 90, "attempts": 100, "total_value": 40.0},
            "answer_with_tool": {"successes": 70, "attempts": 80, "total_value": 35.0},
        },
        "action_log": [{"fallback_reason": None} for _ in range(100)],
        "tool_error_counts": {"answer_with_tool": 6},
    }
    return DecisionPipeline(cognitive_state)


def main() -> int:
    app = QApplication(sys.argv)
    widget = ReflectionWidget(build_demo_pipeline())
    widget.show()
    exec_fn = getattr(app, "exec", None) or getattr(app, "exec_", None)
    if exec_fn is None:
        raise RuntimeError("Unable to start Qt event loop: no exec/exec_ method found")
    return int(exec_fn())


if __name__ == "__main__":
    raise SystemExit(main())
