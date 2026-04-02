# -*- coding: utf-8 -*-
"""CognitiveCycleLogger — full cognitive cycle JSONL logger.

Records every complete pass through the pipeline:

    Input → Perception → Interpretation → Intent → Decision → Output → Feedback

Each record (one JSON line) captures:

    {
      "cycle_id":      "uuid-...",
      "ts":            "2025-01-01T12:00:00.000Z",
      "input":         "что такое реак",        ← raw STT output
      "raw_stt":       "что такое реак",        ← pre-correction text
      "corrected":     "что такое React",       ← post-phonetic-correction
      "confidence":    0.78,                    ← composite SmartEar confidence
      "decision_zone": "uncertain",             ← ML routing zone
      "intent":        {"type": "definition", "entity": "React", ...},
      "final_output":  "React — это...",        ← LLM response
      "generation_time": 1.23,
      "user_feedback": null                     ← filled later via feedback()
    }

Two-phase API
-------------
Phase 1 — called by SmartEar after interpretation::

    cycle_id = logger.start_cycle(item)  # stores pending record + returns id
    item["_cycle_id"] = cycle_id

Phase 2 — called by AgentLoop after LLM responds::

    logger.complete_cycle(cycle_id, output=response, generation_time=dt)

Feedback (optional, called any time after phase 2)::

    logger.add_feedback(cycle_id, feedback="incorrect entity")

One-shot convenience (when both phases happen in the same scope)::

    logger.log_complete(item, output=response, generation_time=dt)

This log is the *gold dataset* for all future ML improvements.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from cognitive_flow.resonance_learner import ResonanceLearner

logger = logging.getLogger(__name__)

# Default log path — override via constructor or COGNITIVE_CYCLE_LOG env var
_DEFAULT_LOG = os.environ.get(
    "COGNITIVE_CYCLE_LOG",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs", "cognitive_cycle.jsonl"),
)
_DEFAULT_MAX_MB = 50
# Pending cycles older than this are evicted (never completed — timeout / crash)
_PENDING_TTL_SECS = 300  # 5 minutes


class CognitiveCycleLogger:
    """Thread-safe JSONL logger for the full cognitive cycle.

    Args:
        path:    Path to the JSONL log file.  Empty string disables writing.
        max_mb:  Rotate log when it exceeds this size (MB).  Default 50 MB.
    """

    def __init__(
        self,
        path: str = _DEFAULT_LOG,
        max_mb: float = _DEFAULT_MAX_MB,
        learner: "Optional[ResonanceLearner]" = None,
    ) -> None:
        self.path = path
        self.max_bytes = int(max_mb * 1024 * 1024)
        self._enabled = bool(path)
        self._lock = threading.Lock()
        # Optional learner — if provided, learn() is called after each complete_cycle
        self._learner = learner
        # In-memory pending cycles: cycle_id → (partial_record, created_monotonic)
        # TTL eviction prevents unbounded growth when complete_cycle is never called.
        self._pending: Dict[str, Tuple[dict, float]] = {}

    # ------------------------------------------------------------------
    # Phase 1: start
    # ------------------------------------------------------------------

    def start_cycle(self, item: dict) -> str:
        """Create a pending cycle record from a SmartEar-enriched item.

        Returns a ``cycle_id`` (UUID string) that must be stored on the item
        (``item["_cycle_id"] = cycle_id``) so AgentLoop can call
        :meth:`complete_cycle` later.
        """
        cycle_id = str(uuid.uuid4())
        record = self._build_perception_record(cycle_id, item)
        with self._lock:
            self._pending[cycle_id] = (record, time.monotonic())
            self._evict_stale_locked()
        logger.debug("CognitiveCycleLogger: started cycle %s", cycle_id)
        return cycle_id

    # ------------------------------------------------------------------
    # Phase 2: complete
    # ------------------------------------------------------------------

    def complete_cycle(
        self,
        cycle_id: str,
        output: str,
        generation_time: float = 0.0,
        feedback: Optional[str] = None,
        llm_metadata: Optional[dict] = None,
    ) -> None:
        """Finalise a cycle and flush to disk.

        Args:
            cycle_id:        ID returned by :meth:`start_cycle`.
            output:          LLM / handler response text.
            generation_time: Wall-clock seconds to generate the response.
            feedback:        Optional immediate user feedback string.
        """
        with self._lock:
            entry = self._pending.pop(cycle_id, None)

        record = entry[0] if entry is not None else None
        if record is None:
            logger.debug(
                "CognitiveCycleLogger: unknown cycle_id %s — writing standalone record",
                cycle_id,
            )
            record = {"cycle_id": cycle_id, "ts": _now_iso()}

        record["final_output"] = output
        record["generation_time"] = round(generation_time, 4)
        record["user_feedback"] = feedback
        if llm_metadata:
            record["llm"] = llm_metadata
        self._flush(record)
        logger.debug("CognitiveCycleLogger: completed cycle %s", cycle_id)
        # Trigger learning on the completed record (non-blocking — learner is fast)
        if self._learner is not None:
            try:
                self._learner.learn(record)
            except Exception as _le:
                logger.debug("CognitiveCycleLogger: learner.learn failed: %s", _le)

    # ------------------------------------------------------------------
    # Convenience: one-shot
    # ------------------------------------------------------------------

    def log_complete(
        self,
        item: dict,
        output: str,
        generation_time: float = 0.0,
        feedback: Optional[str] = None,
        llm_metadata: Optional[dict] = None,
    ) -> str:
        """Log a full cycle in a single call (no start/complete split).

        Returns the cycle_id for reference.
        """
        cycle_id = str(uuid.uuid4())
        record = self._build_perception_record(cycle_id, item)
        record["final_output"] = output
        record["generation_time"] = round(generation_time, 4)
        record["user_feedback"] = feedback
        if llm_metadata:
            record["llm"] = llm_metadata
        self._flush(record)
        return cycle_id

    # ------------------------------------------------------------------
    # Post-hoc feedback
    # ------------------------------------------------------------------

    def add_feedback(self, cycle_id: str, feedback: str) -> None:
        """Append a feedback-update record referencing a completed cycle.

        Since JSONL is append-only, this writes a small patch record rather
        than modifying the original line.
        """
        patch = {
            "event": "feedback_update",
            "cycle_id": cycle_id,
            "ts": _now_iso(),
            "user_feedback": feedback,
        }
        self._flush(patch)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_perception_record(self, cycle_id: str, item: dict) -> dict:
        """Build the perception half of a cycle record from a SmartEar item."""
        # Raw STT text (before phonetic correction)
        raw_stt = item.get("_original_text") or item.get("text", "")
        corrected = item.get("_corrected_text") or item.get("text", "")
        # If no correction happened, raw == corrected
        final_text = item.get("text", corrected)

        why_strategy = item.get("_why_strategy")
        anchor_ctx = item.get("_anchor_context")
        empathy_result = item.get("_empathy_result")
        copilot_output = item.get("_copilot_output")
        body_cues = (
            copilot_output.get("empathy_cues") if copilot_output else None
        )
        return {
            "cycle_id":            cycle_id,
            "ts":                  _now_iso(),
            "input":               final_text,
            "raw_stt":             raw_stt,
            "corrected":           corrected,
            "confidence":          round(float(item.get("_composite_confidence", 0.0)), 4),
            "decision_zone":       item.get("_routing_zone", ""),
            "selection_source":    item.get("_selection_source", ""),
            "intent":              item.get("_intent"),
            "why":                 item.get("_why"),
            "why_strategy":        why_strategy,
            "anchor_used":         anchor_ctx or [],
            "interviewer_profile": item.get("_interviewer_profile"),
            "empathy":             empathy_result,
            "body_cues":           body_cues,
            "copilot": {
                "pre_prompt":         copilot_output.get("pre_prompt") if copilot_output else None,
                "intervention_level": copilot_output.get("intervention_level") if copilot_output else None,
                "active_rules":       copilot_output.get("active_rules") if copilot_output else [],
            } if copilot_output else None,
            "resonance_score":     item.get("_resonance_score"),
            "resonance_detail":    item.get("_resonance_detail"),
            "final_output":        None,
            "generation_time":     None,
            "user_feedback":       None,
        }

    def _flush(self, record: dict) -> None:
        """Write one record to the JSONL log (thread-safe)."""
        if not self._enabled:
            return
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            with self._lock:
                self._rotate_if_needed()
                dir_path = os.path.dirname(os.path.abspath(self.path))
                os.makedirs(dir_path, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line)
        except Exception as exc:
            logger.warning("CognitiveCycleLogger: write failed: %s", exc)

    def _evict_stale_locked(self) -> None:
        """Drop _pending entries older than _PENDING_TTL_SECS (caller holds lock)."""
        cutoff = time.monotonic() - _PENDING_TTL_SECS
        stale = [cid for cid, (_, ts) in self._pending.items() if ts < cutoff]
        for cid in stale:
            self._pending.pop(cid, None)
        if stale:
            logger.debug(
                "CognitiveCycleLogger: evicted %d stale pending cycle(s): %s",
                len(stale), stale,
            )

    def _rotate_if_needed(self) -> None:
        """Rotate log file when it exceeds max_bytes (caller holds lock).

        Uses a timestamp in the backup name so successive rotations never
        overwrite each other: cognitive_cycle.jsonl.2025-01-01T120000.bak
        """
        try:
            if os.path.getsize(self.path) >= self.max_bytes:
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                bak = f"{self.path}.{ts}.bak"
                os.rename(self.path, bak)
                logger.info("CognitiveCycleLogger: rotated → %s", bak)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def pending_count(self) -> int:
        """Number of cycles started but not yet completed (excludes stale)."""
        with self._lock:
            self._evict_stale_locked()
            return len(self._pending)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
