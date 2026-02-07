from __future__ import annotations

from typing import Any, Dict

from .features import extract_llm_features, extract_stt_features
from .tracer import Tracer


def finalize_llm_metrics(tracer: Tracer, model_name: str, base_metrics: Dict[str, Any]) -> Dict[str, Any]:
    raw_signals = tracer.end_llm_session(model_name)
    causal_features = extract_llm_features(raw_signals)
    merged = dict(base_metrics)
    merged.update(causal_features)
    return merged


def finalize_stt_metrics(tracer: Tracer, model_name: str, base_metrics: Dict[str, Any]) -> Dict[str, Any]:
    raw_signals = tracer.end_stt_session(model_name)
    causal_features = extract_stt_features(raw_signals)
    merged = dict(base_metrics)
    merged.update(causal_features)
    return merged
