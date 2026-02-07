from __future__ import annotations

from typing import Any, Dict

from .monitor import PresenceMonitor


CAPU_FEATURE_KEYS = {
    "avg_attention_entropy",
    "logits_confidence_margin",
    "context_length",
    "segments_count",
    "rtf_estimate",
}


def extract_capu_features(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {key: metrics[key] for key in CAPU_FEATURE_KEYS if key in metrics}


def enrich_decision_context(
    context: Dict[str, Any],
    presence_monitor: PresenceMonitor,
) -> Dict[str, Any]:
    enriched = dict(context)
    enriched["system_state"] = presence_monitor.current_state.state.value
    return enriched
