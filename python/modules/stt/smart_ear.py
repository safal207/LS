"""SmartEar — cognitive interpretation layer between STT and AgentLoop.

Pipeline position::

    AudioIngestion → SpeechToText → [stt_queue]
        → SmartEar (this module) → [enriched_queue]
            → AgentLoop

SmartEar processes each STT item through three explicit stages:

1. **FilterStage**    — composite confidence gate (Amygdala-aware)
2. **HypothesisStage**— PhoneticCorrector: low-confidence words → domain candidates
3. **SelectionStage** — pick original or corrected text; add context boost

Context enrichment (CausalMemory) is folded into FilterStage to avoid an
extra dict-passing hop.

All significant decisions are published to EventBus for observability:
* ``smart_ear_candidates``  — phonetic expansion results
* ``smart_ear_selected``    — committed text with composite confidence
* ``smart_ear_rejected``    — dropped items with reason

Configuration via ``config.py`` (``[smart_ear]`` section):
* ``weights.asr``            — ASR confidence weight (default 0.50)
* ``weights.context``        — CausalMemory context match weight (default 0.25)
* ``weights.vocab``          — Domain vocab match weight (default 0.25)
* ``threshold``              — Minimum composite to pass FilterStage (default 0.25)
* ``low_word_prob``          — Per-word probability below which phonetic correction
                               is attempted (default 0.50)
* ``vocab_similarity``       — Similarity threshold for fuzzy vocab match (default 0.60)
* ``selection_margin``       — Score advantage corrected must have over original (default 1)
* ``vocab_min_length``       — Minimum term length for dynamic vocab (default 3)
* ``vocab_refresh_every``    — Refresh dynamic vocab every N items (default 60)
"""

from __future__ import annotations

import difflib
import logging
import queue
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .phonetic import PhoneticCorrector, STATIC_IT_VOCAB
from shared.utils import is_question

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load weights from config (with graceful fallback to defaults)
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
    )
except ImportError:
    SMART_EAR_W_ASR              = 0.50
    SMART_EAR_W_CONTEXT          = 0.25
    SMART_EAR_W_VOCAB            = 0.25
    SMART_EAR_THRESHOLD          = 0.25
    SMART_EAR_LOW_WORD_PROB      = 0.50
    SMART_EAR_VOCAB_SIMILARITY   = 0.60
    SMART_EAR_SELECTION_MARGIN   = 1
    SMART_EAR_VOCAB_MIN_LENGTH   = 3
    SMART_EAR_VOCAB_REFRESH_EVERY = 60

# Regex: term looks like an IT/Latin identifier (used when filtering dynamic vocab)
_IT_TERM_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_./-]{1,}$')


# ---------------------------------------------------------------------------
# Tiny event wrapper (mirrors audio_module.SimpleEvent)
# ---------------------------------------------------------------------------
@dataclass
class _Event:
    type: str
    payload: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 1: FilterStage
# ---------------------------------------------------------------------------

class FilterStage:
    """Gate noisy / low-confidence STT items using a composite score.

    Key design decisions:
    * Single-word items are still allowed if ``is_question()`` returns True
      (e.g. "Docker?" is a valid question).
    * Vocab match uses fuzzy similarity (not binary membership) so partial
      matches and morphological variants contribute a non-zero score.
    * Amygdala.state is read as a stress signal to tighten the threshold
      under high cognitive load — no Amygdala API calls that could break.
    """

    def __init__(
        self,
        amygdala=None,
        causal_memory=None,
        phonetic_corrector: PhoneticCorrector | None = None,
        threshold: float = SMART_EAR_THRESHOLD,
    ) -> None:
        self.amygdala = amygdala
        self.causal_memory = causal_memory
        self._corrector = phonetic_corrector
        self.threshold = threshold
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
        """Fuzzy vocab match: each word gets similarity score against vocab.

        Uses SequenceMatcher to handle morphological variants and partial matches.
        Score ≥ SMART_EAR_VOCAB_SIMILARITY contributes 1.0; below that → raw score.
        """
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
        """Tighten threshold when Amygdala is under stress."""
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

        # Hard reject: empty
        if not words:
            logger.debug("FilterStage: rejected (empty)")
            return None

        # Single-word: only pass if it looks like a question ("Docker?", "Почему?")
        if len(words) == 1 and not is_question(text):
            logger.debug("FilterStage: rejected (single non-question word): %r", text)
            return None

        asr_confidence: float = item.get("_asr_confidence", 0.0)
        context = self._get_recent_context()
        composite = self.compute_composite(text, asr_confidence, context)

        effective_threshold = self.threshold + self._threshold_boost()

        if composite < effective_threshold:
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

    When per-word probability data is available (``_words`` key from STT),
    only words with ``probability < SMART_EAR_LOW_WORD_PROB`` are candidates.
    Otherwise falls back to full-text correction.
    """

    def __init__(self, phonetic_corrector: PhoneticCorrector) -> None:
        self.corrector = phonetic_corrector

    def process(self, item: dict) -> Optional[dict]:
        text: str = item.get("text", "")
        words_with_prob: List[dict] = item.get("_words", [])

        if words_with_prob:
            corrected_words, corrections = self.corrector.correct_words_with_prob(
                words_with_prob, low_prob_threshold=SMART_EAR_LOW_WORD_PROB
            )
            corrected_text = " ".join(corrected_words)
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

    Corrected text is preferred only when its domain+context score exceeds
    the original by at least SMART_EAR_SELECTION_MARGIN.  This prevents
    spurious substitutions when scores are equal.
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

            # Require corrected to be strictly better by SELECTION_MARGIN
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

    Stateless by design: sentence buffering is handled upstream by STT.
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
        confidence_threshold: float = SMART_EAR_THRESHOLD,
    ) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.event_bus = event_bus
        self.cognitive_flow = cognitive_flow
        self.running = False

        self._corrector = PhoneticCorrector(
            domain_vocab=list(domain_vocab or STATIC_IT_VOCAB),
            threshold=0.35,
        )

        self._filter = FilterStage(
            amygdala=amygdala,
            causal_memory=causal_memory,
            phonetic_corrector=self._corrector,
            threshold=confidence_threshold,
        )
        self._hypothesis = HypothesisStage(self._corrector)
        self._selection = SelectionStage(self._corrector)

        self._vocab_refresh_counter = 0
        self._causal_memory = causal_memory

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

            # Filter: only accept IT-like terms (Latin, min length, no numbers-only)
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
                # Rebuild vocab_lower in FilterStage
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
            self._publish("smart_ear_rejected", {
                "text": original_text,
                "reason": "filter_stage",
            })
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

        self._publish("smart_ear_selected", {
            "text": item["text"],
            "composite_confidence": item.get("_composite_confidence", 0.0),
            "source": item.get("_selection_source", "original"),
            "corrections": item.get("_phonetic_corrections", []),
        })

        return item

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info("SmartEar started")
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
