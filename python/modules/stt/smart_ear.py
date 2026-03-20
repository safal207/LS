"""SmartEar — cognitive interpretation layer between STT and AgentLoop.

Pipeline position::

    AudioIngestion → SpeechToText → [stt_queue]
        → SmartEar (this module) → [enriched_queue]
            → AgentLoop

SmartEar processes each STT item through three explicit stages:

1. **FilterStage**    — composite confidence gate (Amygdala-aware)
2. **HypothesisStage**— PhoneticCorrector: low-confidence words → domain candidates
3. **SelectionStage** — pick original or corrected text; add context boost

Additionally provides:

* **SmartEarAuditLog** — JSONL file with every decision (accepted / rejected /
  corrected).  Rotated when the file exceeds ``SMART_EAR_AUDIT_MAX_MB``.
  Serves as the *gold mine* for offline tuning and error analysis.

* **Feedback loop** — ``SmartEar.user_feedback(original, correct)`` lets the
  caller tell the system "this is what was actually meant".  The correct terms
  are added to the domain vocab immediately, logged, and published on EventBus.

* **Domain packs** — named vocabulary sets (``web_dev``, ``devops``,
  ``crypto``, ``qa``) that can be loaded via ``SMART_EAR_DOMAIN_PACKS`` config
  or the ``domain_packs`` constructor argument.

Configuration via ``config.py`` (``[smart_ear]`` section):
* ``weights.asr``           — ASR weight (default 0.50)
* ``weights.context``       — CausalMemory context match weight (default 0.25)
* ``weights.vocab``         — Domain vocab match weight (default 0.25)
* ``threshold``             — Min composite to pass FilterStage (default 0.25)
* ``low_word_prob``         — Per-word probability threshold (default 0.50)
* ``vocab_similarity``      — Fuzzy vocab-match threshold (default 0.60)
* ``selection_margin``      — Corrected must beat original by this much (default 1)
* ``vocab_min_length``      — Min length for dynamic vocab terms (default 3)
* ``vocab_refresh_every``   — Refresh interval in processed items (default 60)
* ``domain_packs``          — List of pack names to load (default [])
* ``audit_log``             — Path to JSONL audit log file (default "" = disabled)
* ``audit_max_mb``          — Rotate log when it exceeds this size (default 10)

EventBus topics:
* ``smart_ear_candidates``  — phonetic expansion results
* ``smart_ear_selected``    — committed text + composite confidence
* ``smart_ear_rejected``    — dropped items with reason
* ``smart_ear_feedback``    — user-provided correction recorded
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import queue
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .phonetic import PhoneticCorrector, STATIC_IT_VOCAB

# Intent Layer (optional — graceful fallback if module unavailable)
try:
    import sys as _sys_intent
    _intent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _intent_root not in _sys_intent.path:
        _sys_intent.path.insert(0, _intent_root)
    from intent.intent_layer import IntentLayer as _IntentLayer
    _INTENT_AVAILABLE = True
except Exception:
    _INTENT_AVAILABLE = False
    _IntentLayer = None  # type: ignore[assignment,misc]

# CognitiveCycleLogger (optional — graceful fallback)
try:
    from cognitive_flow.cycle_logger import CognitiveCycleLogger as _CycleCognitiveLogger
    _CYCLE_LOGGER_AVAILABLE = True
except Exception:
    _CYCLE_LOGGER_AVAILABLE = False
    _CycleCognitiveLogger = None  # type: ignore[assignment,misc]

# ML decision layer (optional — graceful fallback if sklearn missing)
# Add the modules root to sys.path idempotently so sibling package smart_ear
# can be imported without permanently mutating the interpreter's path.
_modules_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
try:
    import sys as _sys
    if _modules_root not in _sys.path:
        _sys.path.insert(0, _modules_root)
    from smart_ear.features import extract_features, features_to_vector
    from smart_ear.decision_model import SmartEarDecisionModel
    from smart_ear.metrics import SmartEarMetrics
    from smart_ear.auto_trainer import SmartEarAutoTrainer
    _ML_AVAILABLE = True
except Exception:
    _ML_AVAILABLE = False
    SmartEarDecisionModel = None  # type: ignore[assignment,misc]
    SmartEarMetrics = None        # type: ignore[assignment,misc]
    SmartEarAutoTrainer = None    # type: ignore[assignment,misc]
    def extract_features(item: dict) -> dict:  # type: ignore[misc]
        return {}
    def features_to_vector(f: dict) -> list:  # type: ignore[misc]
        return []

try:
    from shared.utils import is_question
except ImportError:
    def is_question(text: str) -> bool:  # type: ignore[misc]
        """Minimal fallback: ends with '?' or starts with a question word."""
        text = text.strip()
        if text.endswith("?"):
            return True
        _Q = {"что", "как", "почему", "зачем", "когда", "где", "кто",
              "what", "how", "why", "when", "where", "who", "which"}
        return text.lower().split()[0] in _Q if text else False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load weights / settings from config (graceful fallback)
# ---------------------------------------------------------------------------
try:
    from config import (
        SMART_EAR_W_ASR,
        SMART_EAR_W_CONTEXT,
        SMART_EAR_W_VOCAB,
        SMART_EAR_THRESHOLD,
        SMART_EAR_LOW_WORD_PROB,
        SMART_EAR_VOCAB_SIMILARITY,
        SMART_EAR_SELECTION_MARGIN,
        SMART_EAR_VOCAB_MIN_LENGTH,
        SMART_EAR_VOCAB_REFRESH_EVERY,
        SMART_EAR_DOMAIN_PACKS,
        SMART_EAR_AUDIT_LOG,
        SMART_EAR_AUDIT_MAX_MB,
    )
except ImportError:
    SMART_EAR_W_ASR               = 0.50
    SMART_EAR_W_CONTEXT           = 0.25
    SMART_EAR_W_VOCAB             = 0.25
    SMART_EAR_THRESHOLD           = 0.25
    SMART_EAR_LOW_WORD_PROB       = 0.50
    SMART_EAR_VOCAB_SIMILARITY    = 0.60
    SMART_EAR_SELECTION_MARGIN    = 1
    SMART_EAR_VOCAB_MIN_LENGTH    = 3
    SMART_EAR_VOCAB_REFRESH_EVERY = 60
    SMART_EAR_DOMAIN_PACKS        = []
    SMART_EAR_AUDIT_LOG           = ""
    SMART_EAR_AUDIT_MAX_MB        = 10

# Regex: term looks like an IT/Latin identifier
_IT_TERM_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_./-]{1,}$')


# ---------------------------------------------------------------------------
# Tiny event wrapper
# ---------------------------------------------------------------------------
@dataclass
class _Event:
    type: str
    payload: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# SmartEarAuditLog — JSONL decision log
# ---------------------------------------------------------------------------

class SmartEarAuditLog:
    """Append-only JSONL log of every SmartEar decision.

    Records:
    * ``accepted`` — item passed all stages (includes final text & corrections)
    * ``rejected`` — item dropped by FilterStage (reason included)
    * ``feedback`` — user-supplied correction (original → correct terms)

    The log is rotated (old file renamed to ``<path>.bak``) when it exceeds
    ``max_bytes``.  This keeps disk usage bounded without losing the last run.

    When ``path`` is empty the logger is a no-op.
    """

    def __init__(self, path: str = "", max_bytes: int = 10 * 1024 * 1024) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self._enabled = bool(path)

    def _rotate_if_needed(self) -> None:
        try:
            if os.path.getsize(self.path) >= self.max_bytes:
                bak = self.path + ".bak"
                if os.path.exists(bak):
                    os.remove(bak)
                os.rename(self.path, bak)
                logger.info("SmartEarAuditLog rotated → %s", bak)
        except OSError:
            pass

    def _write(self, record: dict) -> None:
        if not self._enabled:
            return
        record["ts"] = datetime.now(timezone.utc).isoformat()
        try:
            self._rotate_if_needed()
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug("SmartEarAuditLog write failed: %s", exc)

    def log_accepted(
        self,
        original: str,
        final: str,
        source: str,
        composite: float,
        corrections: List[dict],
    ) -> None:
        self._write({
            "event": "accepted",
            "original": original,
            "final": final,
            "source": source,
            "composite": round(composite, 4),
            "corrections": corrections,
        })

    def log_rejected(self, text: str, reason: str, composite: float = 0.0) -> None:
        self._write({
            "event": "rejected",
            "text": text,
            "reason": reason,
            "composite": round(composite, 4),
        })

    def log_feedback(self, original: str, correct: str, new_terms: List[str]) -> None:
        self._write({
            "event": "feedback",
            "original": original,
            "correct": correct,
            "new_terms": new_terms,
        })

    def log_no_correction(self, word: str, asr_prob: float, candidates: List) -> None:
        """Word was low-confidence but nothing in vocab matched well enough."""
        self._write({
            "event": "no_correction",
            "word": word,
            "asr_prob": round(asr_prob, 4),
            "top_candidates": candidates[:3],
        })


# ---------------------------------------------------------------------------
# SmartEarDatasetLogger — training data collector
# ---------------------------------------------------------------------------

class SmartEarDatasetLogger:
    """Collects labeled examples for training the learned decision model.

    Writes to a JSONL file one record per processed item that contained at
    least one phonetic correction.  Thread-safe via a per-instance lock.

    Record format::

        {
          "original_text":        "что такое реак",
          "corrected_text":       "что такое React",
          "asr_confidence":       0.42,
          "composite_confidence": 0.38,
          "num_corrections":      1,
          "avg_word_prob":        0.45,
          "context_overlap":      0.2,
          "vocab_score_original": 0.1,
          "vocab_score_corrected":0.8,
          "model_confidence":     0.0,
          "routing_zone":         "corrected",
          "decision_source":      "phonetic_ml",
          "chosen":               "corrected"
        }

    ``chosen`` is a **binary training label**: ``"corrected"`` if the corrected
    text was used (any source), ``"original"`` if the original was kept.

    ``decision_source`` preserves the full source tag (``"phonetic"``,
    ``"phonetic_ml"``, ``"original"``, ``"feedback"``) for analysis.

    When ``path`` is empty the logger is a no-op.
    """

    def __init__(self, path: str = "") -> None:
        self.path = path
        self._enabled = bool(path)
        self._lock = threading.Lock()

    def log(self, item: dict) -> None:
        """Write one training record if item has corrections."""
        if not self._enabled:
            return

        corrections: List[dict] = item.get("_phonetic_corrections", [])
        if not corrections:
            return  # Only log items where correction was attempted

        original_text: str = item.get("_original_text", item.get("text", ""))
        corrected_text: str = item.get("_corrected_text", original_text)

        # avg_word_prob from per-word Whisper data
        words: List[dict] = item.get("_words", [])
        if words:
            probs = [float(w.get("probability", 1.0)) for w in words if w.get("word", "").strip()]
            avg_word_prob = sum(probs) / len(probs) if probs else float(item.get("_asr_confidence", 0.0))
        else:
            avg_word_prob = float(item.get("_asr_confidence", 0.0))

        decision_source: str = item.get("_selection_source", "original")
        # Binary training label: "corrected" if any non-original source was
        # chosen; "original" otherwise.  Keeping these two concepts separate
        # prevents self-confirmation in the dataset: "phonetic_ml" was
        # previously stripped to "phonetic" → label 0 (original), meaning the
        # model's own correct decisions were trained away.
        chosen = "corrected" if decision_source != "original" else "original"

        record = {
            "original_text":         original_text,
            "corrected_text":        corrected_text,
            "asr_confidence":        round(float(item.get("_asr_confidence", 0.0)), 4),
            "composite_confidence":  round(float(item.get("_composite_confidence", 0.0)), 4),
            "num_corrections":       len(corrections),
            "avg_word_prob":         round(avg_word_prob, 4),
            "context_overlap":       round(float(item.get("_context_overlap", 0.0)), 4),
            "vocab_score_original":  round(float(item.get("_vocab_score_original", 0.0)), 4),
            "vocab_score_corrected": round(float(item.get("_vocab_score_corrected", 0.0)), 4),
            "model_confidence":      round(float(item.get("_model_confidence", 0.0)), 4),
            "routing_zone":          item.get("_routing_zone", ""),
            "decision_source":       decision_source,
            "chosen":                chosen,
        }

        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            with self._lock:
                os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line)
        except Exception as exc:
            logger.debug("SmartEarDatasetLogger write failed: %s", exc)


# ---------------------------------------------------------------------------
# Stage 1: FilterStage
# ---------------------------------------------------------------------------

class FilterStage:
    """Gate noisy / low-confidence STT items using a composite score.

    Key design decisions:
    * Single-word items are still allowed if ``is_question()`` returns True
      (e.g. "Docker?" or "Почему?" are valid inputs).
    * Vocab match uses fuzzy SequenceMatcher — handles morphological variants
      and partial matches without binary in/not-in.
    * Amygdala.state is read as a stress signal to tighten threshold under
      high cognitive load.  No Amygdala API calls — attribute access only.
    """

    def __init__(
        self,
        amygdala=None,
        causal_memory=None,
        phonetic_corrector: PhoneticCorrector | None = None,
        threshold: float = SMART_EAR_THRESHOLD,
        audit_log: SmartEarAuditLog | None = None,
    ) -> None:
        self.amygdala = amygdala
        self.causal_memory = causal_memory
        self._corrector = phonetic_corrector
        self.threshold = threshold
        self._audit = audit_log or SmartEarAuditLog()

        self._vocab_lower: List[str] = [
            v.lower() for v in (
                phonetic_corrector.domain_vocab if phonetic_corrector else STATIC_IT_VOCAB
            )
        ]

    # ------------------------------------------------------------------
    # CausalMemory
    # ------------------------------------------------------------------

    def _get_recent_context(self) -> str:
        if self.causal_memory is None:
            return ""
        try:
            if hasattr(self.causal_memory, "get_recent_context"):
                return str(self.causal_memory.get_recent_context())
            mem = getattr(self.causal_memory, "memory", None)
            if isinstance(mem, dict):
                return str(mem.get("last_question", ""))
        except Exception as exc:
            logger.debug("FilterStage: causal_memory access failed: %s", exc)
        return ""

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _context_match(self, text: str, context: str) -> float:
        if not context:
            return 0.0
        ctx_words = set(context.lower().split())
        txt_words = set(text.lower().split())
        overlap = ctx_words & txt_words
        return min(1.0, len(overlap) / max(len(txt_words), 1))

    def _vocab_match(self, text: str) -> float:
        """Fuzzy vocab match: each word scored via SequenceMatcher against vocab."""
        words = text.lower().split()
        if not words:
            return 0.0

        total = 0.0
        for word in words:
            best = max(
                (difflib.SequenceMatcher(None, word, v).ratio() for v in self._vocab_lower),
                default=0.0,
            )
            total += min(best, 1.0)

        return total / len(words)

    def compute_composite(self, text: str, asr_confidence: float, context: str) -> float:
        ctx   = self._context_match(text, context)
        vocab = self._vocab_match(text)
        return SMART_EAR_W_ASR * asr_confidence + SMART_EAR_W_CONTEXT * ctx + SMART_EAR_W_VOCAB * vocab

    # ------------------------------------------------------------------
    # Amygdala stress adjustment
    # ------------------------------------------------------------------

    def _threshold_boost(self) -> float:
        if self.amygdala is None:
            return 0.0
        try:
            state = float(getattr(self.amygdala, "state", 0.0))
            if state > 0.8:
                return 0.15
            if state > 0.6:
                return 0.07
        except Exception:
            pass
        return 0.0

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def process(self, item: dict) -> Optional[dict]:
        text: str = item.get("text", "").strip()
        words = text.split()

        if not words:
            self._audit.log_rejected(text, "empty")
            return None

        # Single-word: pass only if it looks like a question
        if len(words) == 1 and not is_question(text):
            self._audit.log_rejected(text, "single_non_question")
            logger.debug("FilterStage: rejected (single non-question word): %r", text)
            return None

        asr_confidence: float = item.get("_asr_confidence", 0.0)
        context = self._get_recent_context()
        composite = self.compute_composite(text, asr_confidence, context)
        effective_threshold = self.threshold + self._threshold_boost()

        if composite < effective_threshold:
            self._audit.log_rejected(text, "low_composite", composite)
            logger.debug(
                "FilterStage: rejected (composite=%.3f < %.3f): %r",
                composite, effective_threshold, text,
            )
            return None

        item["_composite_confidence"] = round(composite, 4)
        item["_recent_context"] = context
        return item


# ---------------------------------------------------------------------------
# Stage 2: HypothesisStage
# ---------------------------------------------------------------------------

class HypothesisStage:
    """Correct low-confidence words via PhoneticCorrector.

    Logs ``no_correction`` events for words that were low-confidence but had
    no good candidate — these are the most valuable entries for vocab expansion.
    """

    def __init__(
        self,
        phonetic_corrector: PhoneticCorrector,
        audit_log: SmartEarAuditLog | None = None,
    ) -> None:
        self.corrector = phonetic_corrector
        self._audit = audit_log or SmartEarAuditLog()

    def process(self, item: dict) -> Optional[dict]:
        text: str = item.get("text", "")
        words_with_prob: List[dict] = item.get("_words", [])

        if words_with_prob:
            corrected_words, corrections = self.corrector.correct_words_with_prob(
                words_with_prob, low_prob_threshold=SMART_EAR_LOW_WORD_PROB
            )
            corrected_text = " ".join(corrected_words)

            # Log words that were low-confidence but didn't get corrected
            corrected_originals = {c["original"].lower() for c in corrections}
            for entry in words_with_prob:
                word = entry.get("word", "").strip()
                prob = float(entry.get("probability", 1.0))
                if prob < SMART_EAR_LOW_WORD_PROB and word.lower() not in corrected_originals:
                    cands = self.corrector.candidates(word)
                    self._audit.log_no_correction(word, prob, cands)
        else:
            corrected_text, corrections = self.corrector.correct_text(text)

        per_word_candidates = self.corrector.all_candidates_for_text(text)

        item["_corrected_text"] = corrected_text
        item["_phonetic_corrections"] = corrections
        item["_per_word_candidates"] = per_word_candidates
        return item


# ---------------------------------------------------------------------------
# Stage 3: SelectionStage
# ---------------------------------------------------------------------------

class SelectionStage:
    """Choose between original and phonetically corrected text.

    Decision routing (in priority order):

    1. **3-zone ML routing** (when model loaded and metrics show no drift):
       * ``prob < low_threshold``  → "original"  (confident, skip heuristic)
       * ``prob > high_threshold`` → "corrected" (confident)
       * ``low ≤ prob ≤ high``     → "uncertain" → falls through to heuristic

    2. **Heuristic fallback** (model absent, not loaded, or uncertain zone):
       corrected wins if ``corr_score >= orig_score + margin``

    Stores vocab/context scores on item so dataset logger and feature
    extractor can read them without recomputing.
    """

    def __init__(
        self,
        phonetic_corrector: PhoneticCorrector,
        decision_model: "SmartEarDecisionModel | None" = None,
        metrics: "SmartEarMetrics | None" = None,
    ) -> None:
        self.corrector = phonetic_corrector
        self._model = decision_model
        self._metrics = metrics
        # Cached vocab set — rebuilt only when domain_vocab grows
        self._vocab_cache: Optional[frozenset] = None
        self._vocab_cache_len: int = 0

    def _get_vocab_set(self) -> frozenset:
        current_len = len(self.corrector.domain_vocab)
        if self._vocab_cache is None or current_len != self._vocab_cache_len:
            self._vocab_cache = frozenset(w.lower() for w in self.corrector.domain_vocab)
            self._vocab_cache_len = current_len
        return self._vocab_cache

    def _vocab_scores(
        self, original_text: str, corrected_text: str, context: str
    ) -> tuple[float, float]:
        vocab_set = self._get_vocab_set()
        ctx_words = set(context.lower().split())

        def score(text: str) -> float:
            words = set(text.lower().split())
            return float(len(words & vocab_set) + len(words & ctx_words))

        return score(original_text), score(corrected_text)

    def _heuristic(self, orig_score: float, corr_score: float) -> tuple[bool, str]:
        """Returns (use_corrected, source_tag)."""
        if corr_score >= orig_score + SMART_EAR_SELECTION_MARGIN:
            return True, "phonetic"
        return False, "original"

    def process(self, item: dict) -> Optional[dict]:
        original_text: str = item.get("text", "")
        corrected_text: str = item.get("_corrected_text", original_text)
        context: str = item.get("_recent_context", "")
        composite: float = item.get("_composite_confidence", 0.0)

        selected = original_text
        source = "original"
        model_confidence = 0.0

        if corrected_text != original_text:
            orig_score, corr_score = self._vocab_scores(original_text, corrected_text, context)

            # Persist scores for feature extractor & dataset logger
            item["_vocab_score_original"]  = orig_score
            item["_vocab_score_corrected"] = corr_score
            item["_original_text"]         = original_text

            ctx_words = set(context.lower().split())
            txt_words = set(original_text.lower().split())
            item["_context_overlap"] = len(ctx_words & txt_words) / max(len(txt_words), 1)

            ml_active = (
                _ML_AVAILABLE
                and self._model is not None
                and self._model.is_loaded
                and not (self._metrics and self._metrics.is_drifted)
            )

            if ml_active:
                features = extract_features(item)
                model_confidence = self._model.predict_proba(features)  # single inference
                z = self._model.zone_from_prob(model_confidence)         # no second call
                item["_model_confidence"] = round(model_confidence, 4)
                item["_routing_zone"]     = z

                if z == "corrected":
                    selected = corrected_text
                    source = "phonetic_ml"
                    logger.debug(
                        "SelectionStage [ML/high]: corrected (conf=%.3f) %r → %r",
                        model_confidence, original_text, corrected_text,
                    )
                elif z == "original":
                    # Confident keep — skip heuristic
                    logger.debug(
                        "SelectionStage [ML/low]: keep original (conf=%.3f): %r",
                        model_confidence, original_text,
                    )
                else:
                    # "uncertain" zone — fall through to heuristic
                    use_corr, source = self._heuristic(orig_score, corr_score)
                    if use_corr:
                        selected = corrected_text
                    logger.debug(
                        "SelectionStage [uncertain→heuristic]: conf=%.3f, src=%s",
                        model_confidence, source,
                    )
            else:
                # No model / drift active — pure heuristic
                use_corr, source = self._heuristic(orig_score, corr_score)
                if use_corr:
                    selected = corrected_text

        # Record in metrics
        if self._metrics is not None:
            self._metrics.record(source=source, model_confidence=model_confidence)

        item["text"] = selected
        item["_selection_source"] = source
        item["_model_confidence"] = round(model_confidence, 4)
        item["_final_composite"]  = composite
        item["type"] = "question"
        return item


# ---------------------------------------------------------------------------
# Stage 4: IntentStage
# ---------------------------------------------------------------------------

class IntentStage:
    """Extract structured intent from the resolved utterance.

    Transforms ``item["text"]`` into a typed IntentResult stored at
    ``item["_intent"]``.  Requires the ``intent`` package; graceful no-op
    when unavailable.

    Example output added to item::

        item["_intent"] = {
            "type": "definition",
            "entity": "React",
            "params": {"domain": "web_dev"},
            "confidence": 0.95,
            "raw_text": "что такое React",
        }
    """

    def __init__(self, intent_layer=None) -> None:
        self._layer = intent_layer

    def process(self, item: dict) -> Optional[dict]:
        if self._layer is None:
            return item
        try:
            self._layer.process_item(item)
        except Exception as exc:
            logger.debug("IntentStage failed: %s", exc)
        return item


# ---------------------------------------------------------------------------
# SmartEar — orchestrator
# ---------------------------------------------------------------------------

class SmartEar:
    """Cognitive interpretation layer between SpeechToText and AgentLoop.

    Processes each STT item through:
        FilterStage → HypothesisStage → SelectionStage

    Public methods:
        run()                       — blocking worker loop
        stop()                      — signal shutdown
        user_feedback(orig, correct)— teach the system: "I meant <correct>"
    """

    def __init__(
        self,
        input_queue: queue.Queue,
        output_queue: queue.Queue,
        *,
        amygdala=None,
        causal_memory=None,
        event_bus=None,
        cognitive_flow=None,
        domain_vocab: List[str] | None = None,
        domain_packs: List[str] | None = None,
        confidence_threshold: float = SMART_EAR_THRESHOLD,
        audit_log_path: str = SMART_EAR_AUDIT_LOG,
        audit_max_mb: int = SMART_EAR_AUDIT_MAX_MB,
        dataset_log_path: str = "",
        model_path: str = "",
        auto_retrain: bool = False,
        retrain_every: int = 50,
        metrics_window: int = 200,
        # Intent Layer (Stage 4)
        intent_enabled: bool = True,
        # Cognitive Cycle Logger
        cycle_log_path: str = "",
        cycle_log_max_mb: float = 50,
    ) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.event_bus = event_bus
        self.cognitive_flow = cognitive_flow
        self.running = False

        # Build vocabulary: static + domain packs + caller-supplied
        vocab = list(STATIC_IT_VOCAB)
        packs_to_load = domain_packs if domain_packs is not None else SMART_EAR_DOMAIN_PACKS
        if packs_to_load:
            try:
                from .domain_packs import load_packs
                pack_terms = load_packs(packs_to_load)
                vocab = list({*vocab, *pack_terms})
                logger.info("SmartEar: loaded domain packs %s (+%d terms)", packs_to_load, len(pack_terms))
            except Exception as exc:
                logger.warning("SmartEar: domain_packs load failed: %s", exc)

        if domain_vocab:
            vocab = list({*vocab, *domain_vocab})

        self._corrector = PhoneticCorrector(domain_vocab=vocab, threshold=0.35)

        # Audit log
        self._audit = SmartEarAuditLog(
            path=audit_log_path,
            max_bytes=audit_max_mb * 1024 * 1024,
        )

        # Dataset logger (for training ML decision model)
        self._dataset_log = SmartEarDatasetLogger(path=dataset_log_path)

        # Online metrics + drift detection
        _metrics = None
        if _ML_AVAILABLE and SmartEarMetrics is not None:
            _metrics = SmartEarMetrics(window=metrics_window)
        self._metrics = _metrics

        # Resolved model path
        _model_path = model_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "models", "smart_ear_model.pkl"
        )

        # ML decision model
        _decision_model = None
        if _ML_AVAILABLE and SmartEarDecisionModel is not None:
            _decision_model = SmartEarDecisionModel(model_path=_model_path)
            _decision_model.load_model()
        self._decision_model = _decision_model

        # Auto-retrain watchdog
        self._auto_trainer = None
        if auto_retrain and _ML_AVAILABLE and SmartEarAutoTrainer is not None and dataset_log_path:
            self._auto_trainer = SmartEarAutoTrainer(
                dataset_path=dataset_log_path,
                model_path=_model_path,
                decision_model=_decision_model,
                retrain_every=retrain_every,
                metrics=_metrics,
            )

        self._filter = FilterStage(
            amygdala=amygdala,
            causal_memory=causal_memory,
            phonetic_corrector=self._corrector,
            threshold=confidence_threshold,
            audit_log=self._audit,
        )
        self._hypothesis = HypothesisStage(self._corrector, audit_log=self._audit)
        self._selection = SelectionStage(
            self._corrector,
            decision_model=_decision_model,
            metrics=_metrics,
        )

        # Stage 4 — Intent Layer
        _intent_layer = None
        if intent_enabled and _INTENT_AVAILABLE and _IntentLayer is not None:
            try:
                _intent_layer = _IntentLayer()
                logger.info("SmartEar: IntentLayer enabled")
            except Exception as exc:
                logger.warning("SmartEar: IntentLayer init failed: %s", exc)
        self._intent = IntentStage(intent_layer=_intent_layer)

        # Cognitive Cycle Logger
        self._cycle_logger = None
        if _CYCLE_LOGGER_AVAILABLE and _CycleCognitiveLogger is not None:
            _cycle_path = cycle_log_path or os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "logs", "cognitive_cycle.jsonl"
            )
            try:
                self._cycle_logger = _CycleCognitiveLogger(
                    path=_cycle_path, max_mb=cycle_log_max_mb
                )
                logger.info("SmartEar: CognitiveCycleLogger → %s", _cycle_path)
            except Exception as exc:
                logger.warning("SmartEar: CognitiveCycleLogger init failed: %s", exc)

        self._vocab_refresh_counter = 0
        self._causal_memory = causal_memory

    # ------------------------------------------------------------------
    # Public: feedback loop
    # ------------------------------------------------------------------

    def user_feedback(self, original_text: str, correct_text: str) -> None:
        """Tell SmartEar what you actually meant.

        New terms extracted from *correct_text* are added to the domain vocab
        immediately so the next utterance benefits from the correction.

        Also writes a **gold-label training record** to the dataset JSONL
        (``chosen = "corrected"``) — human corrections are the highest-quality
        training signal available.

        Args:
            original_text: What the system heard / produced.
            correct_text:  What the user actually said / intended.
        """
        new_terms = [
            t for t in correct_text.split()
            if _IT_TERM_RE.match(t) and len(t) >= SMART_EAR_VOCAB_MIN_LENGTH
        ]
        if new_terms:
            self._corrector.update_vocab(new_terms)
            # Keep FilterStage fuzzy-vocab in sync
            self._filter._vocab_lower = [v.lower() for v in self._corrector.domain_vocab]
            logger.info("SmartEar feedback: added %d terms from correction: %s", len(new_terms), new_terms)

        # ── Gold-label dataset record ────────────────────────────────
        self._dataset_log.log({
            "_original_text":         original_text,
            "_corrected_text":        correct_text,
            "_asr_confidence":        0.0,   # not available at feedback time
            "_composite_confidence":  0.0,
            "_phonetic_corrections":  [{"feedback": True}],  # non-empty → triggers log
            "_words":                 [],
            "_vocab_score_original":  0.0,
            "_vocab_score_corrected": 1.0,   # human says corrected is right
            "_context_overlap":       0.0,
            "_model_confidence":      0.0,
            "_selection_source":      "corrected",  # gold label
        })

        # Mark as feedback event in metrics
        if self._metrics is not None:
            self._metrics.record(source="feedback", model_confidence=0.0, is_feedback=True)

        self._audit.log_feedback(original_text, correct_text, new_terms)
        self._publish("smart_ear_feedback", {
            "original": original_text,
            "correct": correct_text,
            "new_terms": new_terms,
        })

    def get_metrics(self) -> dict:
        """Return current runtime metrics snapshot (for monitoring / dashboards).

        Returns an empty dict when the metrics module is unavailable.
        """
        if self._metrics is None:
            return {}
        return self._metrics.get_dashboard()

    # ------------------------------------------------------------------
    # EventBus
    # ------------------------------------------------------------------

    def _publish(self, event_type: str, payload: dict) -> None:
        if self.event_bus is None:
            return
        try:
            self.event_bus.publish_async(_Event(event_type, payload))
        except Exception as exc:
            logger.debug("SmartEar._publish failed: %s", exc)

    # ------------------------------------------------------------------
    # CognitiveFlow
    # ------------------------------------------------------------------

    def _step_flow(self, event_type: str, payload: dict) -> None:
        if self.cognitive_flow is None:
            return
        try:
            self.cognitive_flow.step({"type": event_type, "payload": payload})
        except Exception as exc:
            logger.debug("SmartEar._step_flow failed: %s", exc)

    # ------------------------------------------------------------------
    # Dynamic vocab refresh — with IT-term filtering
    # ------------------------------------------------------------------

    def _maybe_refresh_vocab(self) -> None:
        self._vocab_refresh_counter += 1
        if self._vocab_refresh_counter % SMART_EAR_VOCAB_REFRESH_EVERY != 0:
            return
        if self._causal_memory is None:
            return
        try:
            if not hasattr(self._causal_memory, "get_frequent_terms"):
                return
            raw_terms: List[str] = self._causal_memory.get_frequent_terms(top_k=50)
            if not raw_terms:
                return

            clean: List[str] = [
                t for t in raw_terms
                if (
                    isinstance(t, str)
                    and len(t) >= SMART_EAR_VOCAB_MIN_LENGTH
                    and _IT_TERM_RE.match(t)
                )
            ]
            if clean:
                self._corrector.update_vocab(clean)
                self._filter._vocab_lower = [v.lower() for v in self._corrector.domain_vocab]
                logger.debug("SmartEar: vocab refreshed (+%d clean terms)", len(clean))
        except Exception as exc:
            logger.debug("SmartEar vocab refresh failed: %s", exc)

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process(self, item: dict) -> Optional[dict]:
        original_text = item.get("text", "")

        self._step_flow("perceive", {"text": original_text})

        # Stage 1 — Filter
        item = self._filter.process(item)
        if item is None:
            self._publish("smart_ear_rejected", {"text": original_text, "reason": "filter_stage"})
            return None

        # Stage 2 — Hypothesis
        item = self._hypothesis.process(item)
        if item is None:
            return None

        self._publish("smart_ear_candidates", {
            "original": original_text,
            "corrected": item.get("_corrected_text", original_text),
            "corrections": item.get("_phonetic_corrections", []),
            "per_word_candidates": item.get("_per_word_candidates", []),
        })

        # Stage 3 — Selection
        item = self._selection.process(item)
        if item is None:
            return None

        self._step_flow("interpret", {"text": item.get("text", "")})

        # Stage 4 — Intent extraction
        item = self._intent.process(item)
        if item is None:
            return None

        self._step_flow("intent", {"intent": item.get("_intent", {})})

        final_text = item["text"]
        source = item.get("_selection_source", "original")
        composite = item.get("_composite_confidence", 0.0)
        corrections = item.get("_phonetic_corrections", [])

        # Dataset logging — write training record when correction was attempted
        self._dataset_log.log(item)

        self._audit.log_accepted(original_text, final_text, source, composite, corrections)
        self._publish("smart_ear_selected", {
            "text": final_text,
            "composite_confidence": composite,
            "source": source,
            "corrections": corrections,
            "intent": item.get("_intent"),
        })

        # Cognitive Cycle Logger — Phase 1: start cycle
        if self._cycle_logger is not None:
            try:
                cycle_id = self._cycle_logger.start_cycle(item)
                item["_cycle_id"] = cycle_id
            except Exception as exc:
                logger.debug("CognitiveCycleLogger.start_cycle failed: %s", exc)

        return item

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info("SmartEar started (vocab=%d terms)", len(self._corrector.domain_vocab))
        self.running = True
        if self._auto_trainer is not None:
            self._auto_trainer.start()

        while self.running:
            self._maybe_refresh_vocab()

            try:
                item = self.input_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                result = self._process(item)
                if result is not None:
                    logger.info(
                        "SmartEar → AgentLoop: %r (src=%s, conf=%.3f)",
                        result["text"],
                        result.get("_selection_source", "?"),
                        result.get("_composite_confidence", 0.0),
                    )
                    try:
                        self.output_queue.put_nowait(result)
                    except queue.Full:
                        logger.warning("SmartEar: output queue full, dropping item")
            except Exception as exc:
                logger.error("SmartEar processing error: %s", exc, exc_info=True)
            finally:
                try:
                    self.input_queue.task_done()
                except Exception:
                    pass

        logger.info("SmartEar stopped")

    def stop(self) -> None:
        self.running = False
        if self._auto_trainer is not None:
            self._auto_trainer.stop()
