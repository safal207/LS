"""Standalone PyQt dashboard for DecisionPipeline reflection proposals."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

from importlib.util import find_spec

if find_spec("PyQt6") is not None:  # pragma: no cover - runtime dependent
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
else:  # pragma: no cover - runtime dependent
    from PyQt5.QtGui import QColor
    from PyQt5.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

try:  # pragma: no cover - runtime import convenience
    from .decision_pipeline import DecisionPipeline
    from .reflection_actions import ReflectionActionHandler
    from .reflection_formatting import format_proposals
except ImportError:  # pragma: no cover - direct script execution
    from agent.decision_pipeline import DecisionPipeline
    from agent.reflection_actions import ReflectionActionHandler
    from agent.reflection_formatting import format_proposals


class ReflectionWidget(QWidget):
    """Interactive dashboard for reviewing and applying reflection proposals."""

    def __init__(self, pipeline: DecisionPipeline):
        super().__init__()
        self.pipeline = pipeline
        self.action_handler = ReflectionActionHandler(pipeline)
        self.current_proposals: List[Dict[str, Any]] = []

        self.setWindowTitle("Reflection Dashboard")
        self.resize(1080, 720)
        self._build_ui()
        self._refresh_dashboard()

    def _build_ui(self) -> None:
        """Create and connect dashboard widgets."""
        root = QVBoxLayout(self)

        control_row = QHBoxLayout()
        self.reflect_button = QPushButton("Reflect & Propose")
        self.reflect_button.clicked.connect(self.on_reflect_clicked)
        control_row.addWidget(self.reflect_button)

        self.approve_button = QPushButton("Approve Selected")
        self.approve_button.clicked.connect(self.on_approve_selected)
        control_row.addWidget(self.approve_button)

        self.reject_button = QPushButton("Reject Selected")
        self.reject_button.clicked.connect(self.on_reject_selected)
        control_row.addWidget(self.reject_button)
        root.addLayout(control_row)

        grid = QGridLayout()

        proposal_box = QGroupBox("Proposals")
        proposal_layout = QVBoxLayout(proposal_box)
        self.proposal_summary = QTextEdit()
        self.proposal_summary.setReadOnly(True)
        proposal_layout.addWidget(self.proposal_summary)

        self.proposal_list = QListWidget()
        self.proposal_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        proposal_layout.addWidget(self.proposal_list)
        grid.addWidget(proposal_box, 0, 0)

        settings_box = QGroupBox("Current Pipeline Settings")
        settings_layout = QVBoxLayout(settings_box)
        self.threshold_label = QLabel()
        self.fallback_label = QLabel()
        settings_layout.addWidget(self.threshold_label)
        settings_layout.addWidget(self.fallback_label)
        grid.addWidget(settings_box, 0, 1)

        heatmap_box = QGroupBox("Strategy Heatmap")
        heatmap_layout = QVBoxLayout(heatmap_box)
        self.heatmap_table = QTableWidget(0, 3)
        self.heatmap_table.setHorizontalHeaderLabels(["Strategy", "Success Rate", "Efficiency"])
        heatmap_layout.addWidget(self.heatmap_table)
        grid.addWidget(heatmap_box, 1, 0)

        trends_box = QGroupBox("Recent Trends")
        trends_layout = QVBoxLayout(trends_box)
        self.trends_text = QTextEdit()
        self.trends_text.setReadOnly(True)
        trends_layout.addWidget(self.trends_text)
        grid.addWidget(trends_box, 1, 1)

        root.addLayout(grid)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        root.addWidget(self.log_output)

    def on_reflect_clicked(self) -> None:
        """Request reflection proposals from pipeline and refresh the panel."""
        self.current_proposals = self.pipeline.reflect_and_propose()
        self._render_proposals()
        self._append_log(f"generated {len(self.current_proposals)} proposals")

    def on_approve_selected(self) -> None:
        """Apply selected proposals and update metrics/controls immediately."""
        selected = self._selected_proposals()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select at least one proposal to approve.")
            return

        messages = self.action_handler.apply_selected(selected)
        # Apply flow: mutate controls/tool runtime, clear handled proposals, then update derived views.
        self._remove_selected_proposals(selected)
        self._refresh_dashboard()
        self._append_log("; ".join(messages))
        self._auto_save_state()

    def on_reject_selected(self) -> None:
        """Reject selected proposals and clear them from current proposal list."""
        selected = self._selected_proposals()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select at least one proposal to reject.")
            return

        messages = self.action_handler.reject_selected(selected)
        self._remove_selected_proposals(selected)
        self._refresh_dashboard()
        self._append_log("; ".join(messages))

    def _selected_proposals(self) -> List[Dict[str, Any]]:
        """Resolve selected list items to proposal dictionaries."""
        selected_indices = [self.proposal_list.row(item) for item in self.proposal_list.selectedItems()]
        return [self.current_proposals[index] for index in selected_indices if 0 <= index < len(self.current_proposals)]

    def _remove_selected_proposals(self, proposals: List[Dict[str, Any]]) -> None:
        """Drop handled proposals from in-memory state and re-render list."""
        selected_ids = {item.get("proposal_id") for item in proposals}
        self.current_proposals = [item for item in self.current_proposals if item.get("proposal_id") not in selected_ids]
        self._render_proposals()

    def _render_proposals(self) -> None:
        """Render proposal details and selectable entries."""
        self.proposal_summary.setPlainText(format_proposals(self.current_proposals))
        self.proposal_list.clear()

        if not self.current_proposals:
            QMessageBox.warning(self, "No Proposals", "No proposals available. Run reflection first.")
            return

        for proposal in self.current_proposals:
            confidence = float(proposal.get("confidence", 0.0))
            text = f"{proposal.get('proposal_id')} | {proposal.get('change_type')} | conf={confidence:.2f}"
            item = QListWidgetItem(text)
            if confidence > 0.8:
                item.setBackground(QColor("#c8f7c5"))
            self.proposal_list.addItem(item)

    def _refresh_dashboard(self) -> None:
        """Refresh settings, heatmap, and trend data after each user action."""
        self.threshold_label.setText(f"low_confidence_threshold: {self.pipeline.low_confidence_threshold:.2f}")
        self.fallback_label.setText(f"fallback_action: {self.pipeline.fallback_action}")
        self._refresh_heatmap()
        self._refresh_trends()

    def _refresh_heatmap(self) -> None:
        """Recompute heatmap values from strategy stats after state updates."""
        stats = self.pipeline.cognitive_state.get("strategy_stats", {})
        rows = [item for item in stats.items() if isinstance(item[1], dict)]
        self.heatmap_table.setRowCount(len(rows))

        for row_idx, (strategy, metrics) in enumerate(rows):
            attempts = float(metrics.get("attempts", 0) or 0)
            successes = float(metrics.get("successes", 0) or 0)
            total_value = float(metrics.get("total_value", 0.0) or 0.0)
            success_rate = successes / attempts if attempts else 0.0
            efficiency = total_value / attempts if attempts else 0.0

            self.heatmap_table.setItem(row_idx, 0, QTableWidgetItem(strategy))
            self.heatmap_table.setItem(row_idx, 1, QTableWidgetItem(f"{success_rate:.2f}"))
            self.heatmap_table.setItem(row_idx, 2, QTableWidgetItem(f"{efficiency:.2f}"))

    def _refresh_trends(self, window: int = 20) -> None:
        """Show compact trend summary for the last ``window`` decisions."""
        history = self.pipeline.cognitive_state.get("action_history", [])[-window:]
        if not history:
            self.trends_text.setPlainText("No action history yet.")
            return

        marks = "".join("✓" if item.get("success") else "✗" for item in history)
        success_count = sum(1 for item in history if item.get("success") is True)
        rate = success_count / len(history)
        self.trends_text.setPlainText(f"Last {len(history)} actions success trend:\n{marks}\nSuccess rate: {rate:.2f}")

    def _append_log(self, message: str) -> None:
        """Append dashboard user action messages to the visible event log."""
        current = self.log_output.toPlainText().strip()
        new_text = f"{current}\n{message}" if current else message
        self.log_output.setPlainText(new_text)

    def _auto_save_state(self) -> None:
        """Persist cognitive state after approve flow for reproducible demos."""
        target = Path("reflection_state.json")
        self.pipeline.save_state(str(target))


def build_demo_pipeline() -> DecisionPipeline:
    """Build demo pipeline with synthetic cognitive state for quick local testing."""
    cognitive_state: Dict[str, Any] = {
        "action_history": [{"success": True} for _ in range(45)] + [{"success": False} for _ in range(15)],
        "strategy_stats": {
            "retrieve_context": {"successes": 90, "attempts": 120, "total_value": 40.0},
            "answer_with_tool": {"successes": 60, "attempts": 95, "total_value": 25.0},
            "structured_reasoning": {"successes": 50, "attempts": 70, "total_value": 22.0},
        },
        "action_log": [{"fallback_reason": None} for _ in range(40)]
        + [{"fallback_reason": "tool_error"} for _ in range(40)]
        + [{"fallback_reason": "tool_timeout"} for _ in range(20)],
        "tool_error_counts": {"answer_with_tool": 6},
    }
    return DecisionPipeline(cognitive_state)


def main() -> int:
    """Launch Reflection Dashboard in standalone mode."""
    app = QApplication(sys.argv)
    widget = ReflectionWidget(build_demo_pipeline())
    widget.show()
    exec_fn = getattr(app, "exec", None) or getattr(app, "exec_", None)
    if exec_fn is None:
        raise RuntimeError("Unable to start Qt event loop: no exec/exec_ method found")
    return int(exec_fn())


if __name__ == "__main__":
    raise SystemExit(main())
