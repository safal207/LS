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
"""

from __future__ import annotations

import logging
import queue
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .phonetic import PhoneticCorrector, STATIC_IT_VOCAB

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Composite confidence weights
# ---------------------------------------------------------------------------
W_ASR     = 0.50   # Raw Whisper score (dominant signal)
W_CONTEXT = 0.25   # overlap with recent CausalMemory context
W_VOCAB   = 0.25   # fraction of words found in domain_vocab

# Minimum composite confidence to pass FilterStage
DEFAULT_THRESHOLD = 0.25

# Low per-word probability threshold: words below this are phonetic candidates
LOW_WORD_PROB = 0.50


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

    Context match (CausalMemory) is computed here so ContextStage is not
    needed as a separate class.
    """

    def __init__(
        self,
        amygdala=None,
        causal_memory=None,
        phonetic_corrector: PhoneticCorrector | None = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self.amygdala = amygdala
        self.causal_memory = causal_memory
        self._corrector = phonetic_corrector
        self.threshold = threshold

    # ------------------------------------------------------------------
    # Helpers
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

    def _context_match(self, text: str, context: str) -> float:
        if not context:
            return 0.0
        ctx_words = set(context.lower().split())
        txt_words = set(text.lower().split())
        overlap = ctx_words & txt_words
        return min(1.0, len(overlap) / max(len(txt_words), 1))

    def _vocab_match(self, text: str) -> float:
        vocab_set = {w.lower() for w in (
            self._corrector.domain_vocab if self._corrector else STATIC_IT_VOCAB
        )}
        words = text.lower().split()
        return sum(1 for w in words if w in vocab_set) / max(len(words), 1)

    def compute_composite(self, text: str, asr_confidence: float, context: str) -> float:
        ctx = self._context_match(text, context)
        vocab = self._vocab_match(text)
        return W_ASR * asr_confidence + W_CONTEXT * ctx + W_VOCAB * vocab

    # ------------------------------------------------------------------
    # Amygdala stress boost
    # ------------------------------------------------------------------

    def _amygdala_threshold_boost(self) -> float:
        """If Amygdala reports high stress, tighten the threshold."""
        if self.amygdala is None:
            return 0.0
        try:
            # amygdala.state is a float [0,1]; higher = more stressed
            state = float(getattr(self.amygdala, "state", 0.0))
            if state > 0.8:
                return 0.15  # tighten by 15 pp under heavy load
            if state > 0.6:
                return 0.07
        except Exception:
            pass
        return 0.0

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def process(self, item: dict) -> Optional[dict]:
        text: str = item.get("text", "")
        words = text.split()

        # Hard reject: too short (noise)
        if len(words) < 2:
            logger.debug("FilterStage: rejected (too short): %r", text)
            return None

        asr_confidence: float = item.get("_asr_confidence", 0.0)
        context = self._get_recent_context()
        composite = self.compute_composite(text, asr_confidence, context)

        effective_threshold = self.threshold + self._amygdala_threshold_boost()

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

    Only words where ``probability < LOW_WORD_PROB`` are passed to the
    corrector; high-confidence words are kept as-is.
    """

    def __init__(self, phonetic_corrector: PhoneticCorrector) -> None:
        self.corrector = phonetic_corrector

    def process(self, item: dict) -> Optional[dict]:
        text: str = item.get("text", "")
        words_with_prob: List[dict] = item.get("_words", [])

        if words_with_prob:
            # Targeted correction via PhoneticCorrector.correct_words_with_prob():
            # only uncertain words (probability < LOW_WORD_PROB) are touched.
            corrected_words, corrections = self.corrector.correct_words_with_prob(
                words_with_prob, low_prob_threshold=LOW_WORD_PROB
            )
            corrected_text = " ".join(corrected_words)
        else:
            # Fallback: no per-word probability — correct all words heuristically
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
    """Choose between original and phonetically corrected text."""

    def __init__(self, phonetic_corrector: PhoneticCorrector) -> None:
        self.corrector = phonetic_corrector

    def process(self, item: dict) -> Optional[dict]:
        original_text: str = item.get("text", "")
        corrected_text: str = item.get("_corrected_text", original_text)
        context: str = item.get("_recent_context", "")

        selected = original_text
        source = "original"

        if corrected_text != original_text:
            vocab_set = {w.lower() for w in self.corrector.domain_vocab}
            ctx_words = set(context.lower().split())

            orig_words = set(original_text.lower().split())
            corr_words = set(corrected_text.lower().split())

            # Accept correction when it has better domain/context coverage
            orig_score = len(orig_words & vocab_set) + len(orig_words & ctx_words)
            corr_score = len(corr_words & vocab_set) + len(corr_words & ctx_words)

            if corr_score >= orig_score:
                selected = corrected_text
                source = "phonetic"

        item["text"] = selected
        item["_selection_source"] = source
        item["type"] = "question"
        return item


# ---------------------------------------------------------------------------
# SmartEar — orchestrator
# ---------------------------------------------------------------------------

class SmartEar:
    """Cognitive interpretation layer between SpeechToText and AgentLoop.

    Processes each STT item through:
        FilterStage → HypothesisStage → SelectionStage

    Stateless by design (no internal partial buffer): sentence buffering is
    already handled upstream by SpeechToText.  This keeps latency minimal.
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
        confidence_threshold: float = DEFAULT_THRESHOLD,
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

        # Stages (3 instead of 4 — ContextStage merged into FilterStage)
        self._filter = FilterStage(
            amygdala=amygdala,
            causal_memory=causal_memory,
            phonetic_corrector=self._corrector,
            threshold=confidence_threshold,
        )
        self._hypothesis = HypothesisStage(self._corrector)
        self._selection = SelectionStage(self._corrector)

        # Dynamic vocab refresh counter
        self._vocab_refresh_counter = 0
        self._vocab_refresh_every = 60
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
    # Dynamic vocab
    # ------------------------------------------------------------------

    def _maybe_refresh_vocab(self) -> None:
        self._vocab_refresh_counter += 1
        if self._vocab_refresh_counter % self._vocab_refresh_every != 0:
            return
        if self._causal_memory is None:
            return
        try:
            if hasattr(self._causal_memory, "get_frequent_terms"):
                terms = self._causal_memory.get_frequent_terms(top_k=50)
                if terms:
                    self._corrector.update_vocab(terms)
                    logger.debug("SmartEar: refreshed vocab (+%d terms)", len(terms))
        except Exception as exc:
            logger.debug("SmartEar vocab refresh failed: %s", exc)

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process(self, item: dict) -> Optional[dict]:
        """Run item through Filter → Hypothesis → Selection. Returns enriched item or None."""
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

        # Stage 2 — Hypothesis (phonetic correction)
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
                    logger.info("SmartEar → AgentLoop: %r (source=%s)",
                                result["text"], result.get("_selection_source", "?"))
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
