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
+--------------------------+--------------------------------------------+

``selection_source`` (``"original"`` / ``"phonetic"``) is kept in the
returned dict as a label for training — it is NOT part of the feature
vector fed to the model (callers must drop it before predict()).
"""

from __future__ import annotations

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
        avg_word_probability = asr_confidence

    # Text length in tokens
    original_text: str = item.get("_original_text", item.get("text", ""))
    text_length: int = len(original_text.split())

    # Vocab scores — set by SelectionStage if available, else 0
    vocab_score_original: float = float(item.get("_vocab_score_original", 0.0))
    vocab_score_corrected: float = float(item.get("_vocab_score_corrected", 0.0))

    # Context overlap — fraction of text words found in recent context
    context_overlap: float = float(item.get("_context_overlap", 0.0))

    # Label (for training — not a feature)
    selection_source: str = item.get("_selection_source", "original")

    # model_confidence from a previous inference pass (0 if not available)
    model_confidence: float = float(item.get("_model_confidence", 0.0))

    return {
        # ── Features ─────────────────────────────────────────────────
        "asr_confidence":       asr_confidence,
        "composite_confidence": composite_confidence,
        "num_corrections":      float(num_corrections),
        "avg_word_probability": avg_word_probability,
        "text_length":          float(text_length),
        "vocab_score_original": vocab_score_original,
        "vocab_score_corrected":vocab_score_corrected,
        "context_overlap":      context_overlap,
        "model_confidence":     model_confidence,
        # ── Label (training only) ─────────────────────────────────────
        "selection_source":     selection_source,
    }


# Ordered list of feature names (same order fed to sklearn)
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
]


def features_to_vector(features: dict) -> List[float]:
    """Convert a feature dict to an ordered list suitable for sklearn.

    Args:
        features: Dict produced by :func:`extract_features`.

    Returns:
        Ordered list of floats matching :data:`FEATURE_NAMES`.
    """
    return [features.get(name, 0.0) for name in FEATURE_NAMES]
