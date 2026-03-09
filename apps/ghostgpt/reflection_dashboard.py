from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from agent.reflection import ReflectionPipeline
from agent.reflection_handler import ReflectionActionHandler


class ReflectionDashboard(QDialog):
    def __init__(self, pipeline: ReflectionPipeline, log_path: str = "logs/reflection_dashboard_log.json"):
        super().__init__()
        self.pipeline = pipeline
        self.action_handler = ReflectionActionHandler(self.pipeline.decision_pipeline)
        self.log_path = Path(log_path)
        self.proposals: List[Dict[str, Any]] = []

        self.setWindowTitle("Reflection Dashboard")
        self.resize(900, 650)

        layout = QVBoxLayout(self)
        self.proposal_list = QListWidget()
        layout.addWidget(self.proposal_list)

        self.apply_high_btn = QPushButton("Apply All High-Confidence (>0.9)")
        self.apply_high_btn.clicked.connect(self.apply_all_high_confidence)
        layout.addWidget(self.apply_high_btn)

        self.heatmap_placeholder = QLabel("Heatmap / Trends placeholder")
        layout.addWidget(self.heatmap_placeholder)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.refresh()

    def refresh(self) -> None:
        self.proposals = self.pipeline.generate_proposals()
        self.proposal_list.clear()

        for proposal in self.proposals:
            item = QListWidgetItem()
            widget = self._build_item_widget(proposal)
            if float(proposal.get("confidence", 0.0)) > 0.9:
                proposal["high_confidence"] = True
            item.setSizeHint(widget.sizeHint())
            self.proposal_list.addItem(item)
            self.proposal_list.setItemWidget(item, widget)

    def _build_item_widget(self, proposal: Dict[str, Any]) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        high_flag = " [HIGH]" if proposal.get("high_confidence") else ""
        text = f"{proposal.get('proposal_id')} | {proposal.get('change_type')} | conf={proposal.get('confidence',0.0):.2f}{high_flag}"
        row.addWidget(QLabel(text))

        approve = QPushButton("Approve")
        reject = QPushButton("Reject")
        approve.clicked.connect(lambda: self._approve(proposal))
        reject.clicked.connect(lambda: self._reject(proposal))
        row.addWidget(approve)
        row.addWidget(reject)
        return container

    def apply_all_high_confidence(self) -> None:
        for proposal in self.proposals:
            if float(proposal.get("confidence", 0.0)) > 0.9:
                self._approve(proposal)

    def _approve(self, proposal: Dict[str, Any]) -> None:
        result = self.action_handler.apply(proposal)
        if result.get("status") == "applied":
            self.pipeline.save_state()
        self._log_action(proposal, result.get("status", "unknown"))

    def _reject(self, proposal: Dict[str, Any]) -> None:
        result = self.action_handler.reject(proposal)
        self._log_action(proposal, result.get("status", "unknown"))

    def _log_action(self, proposal: Dict[str, Any], result: str) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "proposal_id": proposal.get("proposal_id"),
            "result": result,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if self.log_path.exists():
            existing = json.loads(self.log_path.read_text(encoding="utf-8"))
        existing.append(payload)
        self.log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log_output.setPlainText("\n".join(f"{e['timestamp']} {e['proposal_id']} -> {e['result']}" for e in existing[-10:]))
