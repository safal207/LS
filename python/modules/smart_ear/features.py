"""Feature extractor for the SmartEar learned decision layer.

Pure function — no I/O, no side-effects, no external dependencies.

Features extracted from a SmartEar pipeline item dict:

+--------------------------+--------------------------------------------+
| Feature                  | Source key(s) in item                      |
+==========================+============================================+
| asr_confidence           | _asr_confidence                            |
| composite_confidence     | _composite_confidence                      |
| num_corrections          | len(_phonetic_corrections)                 |
| avg_word_probability     | mean of probability fields in _words       |
| text_length              | len(original text tokens)                  |
| vocab_score_original     | _vocab_score_original                      |
| vocab_score_corrected    | _vocab_score_corrected                     |
| context_overlap          | _context_overlap                           |
| model_confidence         | _model_confidence (prior inference)        |
| correction_ratio         | num_corrections / text_length              |
| avg_candidate_score      | mean of _candidates scores                 |
| max_candidate_score      | max of _candidates scores                  |
| entropy_word_probs       | -sum(p * log(p)) over word probabilities   |
+--------------------------+--------------------------------------------+

``selection_source`` (``"original"`` / ``"phonetic"``) is kept in the
returned dict as a label for training — it is NOT part of the feature
vector fed to the model (callers must drop it before predict()).
"""

from __future__ import annotations

import math
from typing import List


def extract_features(item: dict) -> dict:
    """Extract a flat feature dict from a SmartEar pipeline item.

    Args:
        item: The enriched dict produced by SmartEar stages.  All keys
              are optional — missing values fall back to safe defaults.

    Returns:
        A dict with float features + ``selection_source`` label string.
        All feature values are ``float``.
    """
    asr_confidence: float = float(item.get("_asr_confidence", 0.0))
    composite_confidence: float = float(item.get("_composite_confidence", 0.0))

    corrections: List[dict] = item.get("_phonetic_corrections", [])
    num_corrections: int = len(corrections)

    # Per-word probabilities (from Whisper word_timestamps)
    words: List[dict] = item.get("_words", [])
    if words:
        probs = [float(w.get("probability", 1.0)) for w in words if w.get("word", "").strip()]
        avg_word_probability = sum(probs) / len(probs) if probs else 1.0
    else:
        # Fall back to ASR confidence as proxy
        probs = []
        avg_word_probability = asr_confidence

    # Text length in tokens
    original_text: str = item.get("_original_text", item.get("text", ""))
    text_length: int = max(len(original_text.split()), 1)  # avoid div by zero

    # Vocab scores — set by SelectionStage if available, else 0
    vocab_score_original: float = float(item.get("_vocab_score_original", 0.0))
    vocab_score_corrected: float = float(item.get("_vocab_score_corrected", 0.0))

    # Context overlap — fraction of text words found in recent context
    context_overlap: float = float(item.get("_context_overlap", 0.0))

    # Label (for training — not a feature)
    selection_source: str = item.get("_selection_source", "original")

    # model_confidence from a previous inference pass (0 if not available)
    model_confidence: float = float(item.get("_model_confidence", 0.0))

    # ── New features ─────────────────────────────────────────────────────

    # Ratio of corrections to text length
    correction_ratio: float = float(num_corrections) / float(text_length)

    # Candidate scores (list of dicts with "score" key, or plain floats)
    candidates: List = item.get("_candidates", [])
    candidate_scores: List[float] = []
    for c in candidates:
        if isinstance(c, dict):
            s = c.get("score", c.get("confidence", 0.0))
        else:
            s = float(c) if c is not None else 0.0
        try:
            candidate_scores.append(float(s))
        except (TypeError, ValueError):
            pass

    avg_candidate_score: float = (
        sum(candidate_scores) / len(candidate_scores) if candidate_scores else 0.0
    )
    max_candidate_score: float = max(candidate_scores) if candidate_scores else 0.0

    # Shannon entropy over word probabilities: -sum(p * log(p))
    # Uses per-word probs if available, else falls back to asr_confidence singleton
    entropy_word_probs: float = _entropy(probs if probs else [asr_confidence])

    return {
        # ── Original features ────────────────────────────────────────────
        "asr_confidence":       asr_confidence,
        "composite_confidence": composite_confidence,
        "num_corrections":      float(num_corrections),
        "avg_word_probability": avg_word_probability,
        "text_length":          float(text_length),
        "vocab_score_original": vocab_score_original,
        "vocab_score_corrected":vocab_score_corrected,
        "context_overlap":      context_overlap,
        "model_confidence":     model_confidence,
        # ── New features ─────────────────────────────────────────────────
        "correction_ratio":     correction_ratio,
        "avg_candidate_score":  avg_candidate_score,
        "max_candidate_score":  max_candidate_score,
        "entropy_word_probs":   entropy_word_probs,
        # ── Label (training only) ─────────────────────────────────────────
        "selection_source":     selection_source,
    }


def _entropy(probs: List[float]) -> float:
    """Per-word surprise score: -sum(p * log(p)) over word probabilities.

    Note — this is intentionally *unnormalized* (word probs do not sum to 1).
    It measures total acoustic uncertainty across the utterance rather than a
    proper information-theoretic entropy.  The value therefore grows with
    utterance length, but ``text_length`` is a separate feature that lets
    tree-based models account for that correlation automatically.

    For the LogisticRegression fallback the two features are correlated, but
    the effect is bounded because StandardScaler centers both independently.
    """
    result = 0.0
    for p in probs:
        p = max(1e-12, min(1.0, p))  # clip to avoid log(0)
        result -= p * math.log(p)
    return result


# Ordered list of feature names (same order fed to sklearn / LightGBM)
FEATURE_NAMES: List[str] = [
    "asr_confidence",
    "composite_confidence",
    "num_corrections",
    "avg_word_probability",
    "text_length",
    "vocab_score_original",
    "vocab_score_corrected",
    "context_overlap",
    "model_confidence",
    "correction_ratio",
    "avg_candidate_score",
    "max_candidate_score",
    "entropy_word_probs",
]


def features_to_vector(features: dict) -> List[float]:
    """Convert a feature dict to an ordered list suitable for sklearn/LightGBM.

    Args:
        features: Dict produced by :func:`extract_features`.

    Returns:
        Ordered list of floats matching :data:`FEATURE_NAMES`.
    """
    return [features.get(name, 0.0) for name in FEATURE_NAMES]
