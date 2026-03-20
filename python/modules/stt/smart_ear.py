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
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .phonetic import PhoneticCorrector, STATIC_IT_VOCAB

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

    Corrected text wins only if its score exceeds original by
    ``SMART_EAR_SELECTION_MARGIN`` — equal scores keep original.
    """

    def __init__(self, phonetic_corrector: PhoneticCorrector) -> None:
        self.corrector = phonetic_corrector

    def process(self, item: dict) -> Optional[dict]:
        original_text: str = item.get("text", "")
        corrected_text: str = item.get("_corrected_text", original_text)
        context: str = item.get("_recent_context", "")
        composite: float = item.get("_composite_confidence", 0.0)

        selected = original_text
        source = "original"

        if corrected_text != original_text:
            vocab_set = {w.lower() for w in self.corrector.domain_vocab}
            ctx_words = set(context.lower().split())

            orig_words = set(original_text.lower().split())
            corr_words = set(corrected_text.lower().split())

            orig_score = len(orig_words & vocab_set) + len(orig_words & ctx_words)
            corr_score = len(corr_words & vocab_set) + len(corr_words & ctx_words)

            if corr_score >= orig_score + SMART_EAR_SELECTION_MARGIN:
                selected = corrected_text
                source = "phonetic"

        item["text"] = selected
        item["_selection_source"] = source
        item["_final_composite"] = composite
        item["type"] = "question"
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

        self._filter = FilterStage(
            amygdala=amygdala,
            causal_memory=causal_memory,
            phonetic_corrector=self._corrector,
            threshold=confidence_threshold,
            audit_log=self._audit,
        )
        self._hypothesis = HypothesisStage(self._corrector, audit_log=self._audit)
        self._selection = SelectionStage(self._corrector)

        self._vocab_refresh_counter = 0
        self._causal_memory = causal_memory

    # ------------------------------------------------------------------
    # Public: feedback loop
    # ------------------------------------------------------------------

    def user_feedback(self, original_text: str, correct_text: str) -> None:
        """Tell SmartEar what you actually meant.

        New terms extracted from *correct_text* are added to the domain vocab
        immediately so the next utterance benefits from the correction.

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

        self._audit.log_feedback(original_text, correct_text, new_terms)
        self._publish("smart_ear_feedback", {
            "original": original_text,
            "correct": correct_text,
            "new_terms": new_terms,
        })

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

        final_text = item["text"]
        source = item.get("_selection_source", "original")
        composite = item.get("_composite_confidence", 0.0)
        corrections = item.get("_phonetic_corrections", [])

        self._audit.log_accepted(original_text, final_text, source, composite, corrections)
        self._publish("smart_ear_selected", {
            "text": final_text,
            "composite_confidence": composite,
            "source": source,
            "corrections": corrections,
        })

        return item

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info("SmartEar started (vocab=%d terms)", len(self._corrector.domain_vocab))
        self.running = True

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
