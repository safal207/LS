from __future__ import annotations

import importlib.util
from typing import Any, Dict


def extract_llm_features(signals: Dict[str, Any]) -> Dict[str, float]:
    features: Dict[str, float] = {}
    attentions = signals.get("attentions") or []
    logits_list = signals.get("logits") or []
    context_length = signals.get("context_length")

    if context_length is not None:
        features["context_length"] = float(context_length)

    if importlib.util.find_spec("torch") is None:
        return features
    import torch

    if attentions:
        entropies = []
        max_focus = []
        for attn in attentions:
            if not hasattr(attn, "float"):
                continue
            probs = attn.float().softmax(dim=-1)
            logp = (probs + 1e-9).log()
            entropy = -(probs * logp).sum(dim=-1).mean().item()
            entropies.append(entropy)
            max_focus.append(probs.max(dim=-1).values.mean().item())
        if entropies:
            features["avg_attention_entropy"] = float(sum(entropies) / len(entropies))
        if max_focus:
            features["max_attention_focus"] = float(max(max_focus))

    if logits_list:
        logits = logits_list[-1]
        if hasattr(logits, "float"):
            probs = logits.float().softmax(dim=-1)
            top2 = probs.topk(2, dim=-1).values
            margin = (top2[..., 0] - top2[..., 1]).mean().item()
            features["logits_confidence_margin"] = float(margin)

    return features


def extract_stt_features(signals: Dict[str, Any]) -> Dict[str, float]:
    features: Dict[str, float] = {}
    segments = signals.get("segments_count")
    transcription_time = signals.get("transcription_time")
    audio_seconds = signals.get("audio_seconds")

    if isinstance(segments, (int, float)):
        features["segments_count"] = float(segments)

    if isinstance(transcription_time, (int, float)):
        features["transcription_time"] = float(transcription_time)

    if isinstance(audio_seconds, (int, float)) and isinstance(transcription_time, (int, float)):
        if audio_seconds > 0:
            features["rtf_estimate"] = float(transcription_time / audio_seconds)

    return features
