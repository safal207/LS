"""SmartEar — cognitive interpretation layer between STT and AgentLoop.

Pipeline position::

    AudioIngestion → SpeechToText → [stt_queue]
        → SmartEar (this module) → [enriched_queue]
            → AgentLoop

SmartEar processes each STT item through four explicit stages:

1. **FilterStage**    — Amygdala-gated composite confidence filter
2. **ContextStage**   — CausalMemory enrichment + dynamic vocabulary
3. **HypothesisStage**— PhoneticCorrector + CounterfactualEngine alternatives
4. **SelectionStage** — Final hypothesis selection and text commitment

It also maintains a **partial buffer** for streaming re-evaluation, allowing
the system to update earlier hypotheses as more audio arrives before committing
the final text downstream.

All significant decisions are published to EventBus for observability:
* ``voice_detected`` / ``silence_detected`` — from AudioIngestion
* ``smart_ear_candidates``  — hypothesis list after phonetic expansion
* ``smart_ear_selected``    — committed text with composite confidence
* ``smart_ear_rejected``    — dropped items with reason
* ``smart_ear_updated``     — streaming re-evaluation triggered
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .phonetic import PhoneticCorrector, STATIC_IT_VOCAB

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Composite confidence weights
# ---------------------------------------------------------------------------
W_ASR = 0.40        # Raw Whisper avg_logprob-derived score
W_CONTEXT = 0.30    # CausalMemory / recent-topic match
W_VOCAB = 0.20      # Domain vocabulary match
W_COHERENCE = 0.10  # Approximate semantic coherence (length heuristic)

# Amygdala: minimum composite confidence to pass FilterStage
AMYGDALA_COMPOSITE_THRESHOLD = 0.28

# Streaming re-evaluation window
PARTIAL_BUFFER_SIZE = 5
SILENCE_COMMIT_TIMEOUT = 1.5  # seconds of silence before committing buffer


# ---------------------------------------------------------------------------
# Tiny event wrapper (mirrors audio_module.SimpleEvent)
# ---------------------------------------------------------------------------
@dataclass
class _Event:
    type: str
    payload: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------

class FilterStage:
    """Gate noisy / low-confidence STT items using a composite confidence score.

    Uses Amygdala when available; falls back to threshold comparison.
    """

    def __init__(
        self,
        amygdala=None,
        threshold: float = AMYGDALA_COMPOSITE_THRESHOLD,
        phonetic_corrector: PhoneticCorrector | None = None,
    ) -> None:
        self.amygdala = amygdala
        self.threshold = threshold
        self._corrector = phonetic_corrector

    def compute_composite(
        self,
        text: str,
        asr_confidence: float,
        context_match: float,
        vocab_match: float,
    ) -> float:
        coherence = min(1.0, len(text.split()) / 6.0)  # ≥6 words → full score
        return (
            W_ASR * asr_confidence
            + W_CONTEXT * context_match
            + W_VOCAB * vocab_match
            + W_COHERENCE * coherence
        )

    def process(self, item: dict) -> Optional[dict]:
        """Return *item* (possibly augmented) if it passes the filter, else None."""
        hypotheses: List[dict] = item.get("hypotheses", [])
        text: str = item.get("text", "")

        # Too short — almost certainly noise
        if len(text.split()) < 2:
            logger.debug(f"FilterStage: rejected (too short): {text!r}")
            return None

        asr_confidence = (
            max(h["confidence"] for h in hypotheses) if hypotheses else 0.0
        )

        # Vocabulary match: fraction of words found in domain vocab
        vocab_set = {w.lower() for w in (self._corrector.domain_vocab if self._corrector else STATIC_IT_VOCAB)}
        words = text.lower().split()
        vocab_match = sum(1 for w in words if w in vocab_set) / max(len(words), 1)

        composite = self.compute_composite(text, asr_confidence, 0.0, vocab_match)

        # Try Amygdala — treat composite as resonance signal
        if self.amygdala is not None:
            try:
                from codex.causal_memory.amygdala import AmygdalaBlockError
                self.amygdala.allow_transition(resonance=composite)
            except AmygdalaBlockError as exc:
                logger.debug(f"FilterStage: Amygdala blocked ({exc.reason}): {text!r}")
                return None
            except Exception:
                # Amygdala unavailable — fall back to threshold
                pass

        if composite < self.threshold:
            logger.debug(
                f"FilterStage: rejected (composite={composite:.3f}<{self.threshold}): {text!r}"
            )
            return None

        item["_composite_confidence"] = round(composite, 4)
        item["_asr_confidence"] = round(asr_confidence, 4)
        item["_vocab_match"] = round(vocab_match, 4)
        return item


class ContextStage:
    """Enrich the item with CausalMemory context and dynamic vocabulary."""

    def __init__(self, causal_memory=None, phonetic_corrector: PhoneticCorrector | None = None) -> None:
        self.causal_memory = causal_memory
        self.corrector = phonetic_corrector
        self._vocab_update_counter = 0
        self._vocab_refresh_every = 60

    def _get_recent_context(self) -> str:
        """Return a short string summarising recent causal memory topics."""
        if self.causal_memory is None:
            return ""
        try:
            # CausalMemory stores recent intents in memory dict-like structure
            # Try common accessors found in the codebase
            if hasattr(self.causal_memory, "get_recent_context"):
                return str(self.causal_memory.get_recent_context())
            if hasattr(self.causal_memory, "memory") and isinstance(self.causal_memory.memory, dict):
                last_q = self.causal_memory.memory.get("last_question", "")
                return str(last_q)
        except Exception as exc:
            logger.debug(f"ContextStage: causal_memory access failed: {exc}")
        return ""

    def _maybe_refresh_vocab(self) -> None:
        """Periodically pull frequent terms from CausalMemory into phonetic vocab."""
        self._vocab_update_counter += 1
        if self._vocab_update_counter % self._vocab_refresh_every != 0:
            return
        if self.causal_memory is None or self.corrector is None:
            return
        try:
            if hasattr(self.causal_memory, "get_frequent_terms"):
                terms = self.causal_memory.get_frequent_terms(top_k=50)
                if terms:
                    self.corrector.update_vocab(terms)
                    logger.debug(f"ContextStage: updated vocab with {len(terms)} terms from CausalMemory")
        except Exception as exc:
            logger.debug(f"ContextStage: vocab refresh failed: {exc}")

    def _context_match_score(self, text: str, context: str) -> float:
        """Simple overlap score between text and recent context."""
        if not context:
            return 0.0
        ctx_words = set(context.lower().split())
        txt_words = set(text.lower().split())
        overlap = ctx_words & txt_words
        return min(1.0, len(overlap) / max(len(txt_words), 1))

    def process(self, item: dict) -> Optional[dict]:
        self._maybe_refresh_vocab()
        text = item.get("text", "")
        context = self._get_recent_context()
        context_match = self._context_match_score(text, context)

        # Update composite confidence with real context_match
        composite = item.get("_composite_confidence", 0.0)
        # Recalculate: replace the 0.0 placeholder for context
        composite = composite + W_CONTEXT * context_match
        item["_composite_confidence"] = round(min(composite, 1.0), 4)
        item["_context_match"] = round(context_match, 4)
        item["_recent_context"] = context
        return item


class HypothesisStage:
    """Expand hypotheses via PhoneticCorrector and CounterfactualEngine."""

    def __init__(
        self,
        phonetic_corrector: PhoneticCorrector,
        cognitive_state: Dict[str, Any] | None = None,
    ) -> None:
        self.corrector = phonetic_corrector
        self._cognitive_state = cognitive_state or {}

    def process(self, item: dict) -> Optional[dict]:
        text = item.get("text", "")

        # 1. Phonetic correction — get per-word candidates
        corrected_text, corrections = self.corrector.correct_text(text)
        per_word_candidates = self.corrector.all_candidates_for_text(text)

        # 2. Build alternative full-text hypotheses from corrections
        phonetic_alternatives: List[dict] = []
        if corrected_text != text:
            phonetic_alternatives.append({
                "text": corrected_text,
                "source": "phonetic",
                "corrections": corrections,
            })

        # 3. CounterfactualEngine: score each alternative
        cf_scored: List[dict] = []
        try:
            from agent.counterfactual_engine import CounterfactualEngine
            cf = CounterfactualEngine(self._cognitive_state)
            alternative_texts = [a["text"] for a in phonetic_alternatives]
            if alternative_texts:
                scores = cf.evaluate_alternatives(alternative_texts)
                for entry in scores:
                    cf_scored.append({
                        "text": entry["action"],
                        "cf_confidence": entry["confidence"],
                        "cf_outcome": entry.get("predicted_outcome"),
                    })
        except Exception as exc:
            logger.debug(f"HypothesisStage: CounterfactualEngine unavailable: {exc}")

        item["_phonetic_corrections"] = corrections
        item["_per_word_candidates"] = per_word_candidates
        item["_phonetic_alternatives"] = phonetic_alternatives
        item["_cf_scored"] = cf_scored
        item["_corrected_text"] = corrected_text
        return item


class SelectionStage:
    """Choose the best text from original + phonetic alternatives."""

    def __init__(self, phonetic_corrector: PhoneticCorrector) -> None:
        self.corrector = phonetic_corrector

    def process(self, item: dict) -> Optional[dict]:
        original_text = item.get("text", "")
        corrected_text = item.get("_corrected_text", original_text)
        context = item.get("_recent_context", "")
        cf_scored = item.get("_cf_scored", [])

        # Prefer CF winner if confidence > 0.5, else phonetic correction, else original
        selected = original_text
        source = "original"

        if cf_scored and cf_scored[0].get("cf_confidence", 0.0) > 0.5:
            selected = cf_scored[0]["text"]
            source = "counterfactual"
        elif corrected_text != original_text:
            # Verify phonetic choice against context
            vocab_set = {w.lower() for w in self.corrector.domain_vocab}
            ctx_words = set(context.lower().split())
            corrected_words = set(corrected_text.lower().split())
            # Accept correction if it has more domain/context overlap
            if (corrected_words & vocab_set) >= (set(original_text.lower().split()) & vocab_set):
                selected = corrected_text
                source = "phonetic"

        item["text"] = selected
        item["_selection_source"] = source
        item["type"] = "question"
        return item


# ---------------------------------------------------------------------------
# SmartEar — top-level orchestrator
# ---------------------------------------------------------------------------

class SmartEar:
    """Cognitive interpretation layer between SpeechToText and AgentLoop.

    Processes STT items through Filter → Context → Hypothesis → Selection stages,
    maintaining a streaming partial buffer to allow re-evaluation before commit.
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
        confidence_threshold: float = AMYGDALA_COMPOSITE_THRESHOLD,
        silence_commit_timeout: float = SILENCE_COMMIT_TIMEOUT,
    ) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.event_bus = event_bus
        self.cognitive_flow = cognitive_flow
        self.running = False

        # Build shared phonetic corrector (extended by ContextStage dynamically)
        self._corrector = PhoneticCorrector(
            domain_vocab=list(domain_vocab or STATIC_IT_VOCAB),
            threshold=0.35,
        )

        cognitive_state: Dict[str, Any] = {}
        if causal_memory is not None and hasattr(causal_memory, "memory"):
            cognitive_state = causal_memory.memory if isinstance(causal_memory.memory, dict) else {}

        # Stages
        self._filter = FilterStage(amygdala, confidence_threshold, self._corrector)
        self._context = ContextStage(causal_memory, self._corrector)
        self._hypothesis = HypothesisStage(self._corrector, cognitive_state)
        self._selection = SelectionStage(self._corrector)

        # Streaming partial buffer
        self._partial_buffer: deque[dict] = deque(maxlen=PARTIAL_BUFFER_SIZE)
        self._last_voice_ts: float = time.time()
        self._silence_commit_timeout = silence_commit_timeout
        self._buffer_lock = threading.Lock()

        # Subscribe to silence events to trigger early commit
        if self.event_bus is not None:
            try:
                self.event_bus.subscribe("silence_detected", self._on_silence)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # EventBus helpers
    # ------------------------------------------------------------------

    def _publish(self, event_type: str, payload: dict) -> None:
        if self.event_bus is None:
            return
        try:
            self.event_bus.publish_async(_Event(event_type, payload))
        except Exception as exc:
            logger.debug(f"SmartEar._publish failed: {exc}")

    def _on_silence(self, event: Any) -> None:
        """Handle silence_detected events from AudioIngestion."""
        payload = getattr(event, "payload", {}) or {}
        ts = payload.get("timestamp", time.time())
        self._last_voice_ts = ts - self._silence_commit_timeout  # force commit condition

    # ------------------------------------------------------------------
    # CognitiveFlow helpers
    # ------------------------------------------------------------------

    def _step_flow(self, event_type: str, payload: dict) -> None:
        if self.cognitive_flow is None:
            return
        try:
            self.cognitive_flow.step({"type": event_type, "payload": payload})
        except Exception as exc:
            logger.debug(f"SmartEar._step_flow failed: {exc}")

    # ------------------------------------------------------------------
    # Composite confidence helpers (public for testing)
    # ------------------------------------------------------------------

    def compute_composite_confidence(
        self,
        text: str,
        asr_confidence: float,
        context_match: float = 0.0,
        vocab_match: float | None = None,
    ) -> float:
        if vocab_match is None:
            vocab_set = {w.lower() for w in self._corrector.domain_vocab}
            words = text.lower().split()
            vocab_match = sum(1 for w in words if w in vocab_set) / max(len(words), 1)
        return self._filter.compute_composite(text, asr_confidence, context_match, vocab_match)

    # ------------------------------------------------------------------
    # Streaming buffer
    # ------------------------------------------------------------------

    def _should_commit(self) -> bool:
        """Return True if the partial buffer should be flushed downstream."""
        if not self._partial_buffer:
            return False
        elapsed = time.time() - self._last_voice_ts
        return elapsed >= self._silence_commit_timeout

    def _flush_buffer(self) -> Optional[dict]:
        """Merge partial buffer into a single item and clear it."""
        with self._buffer_lock:
            if not self._partial_buffer:
                return None
            texts = [chunk["text"] for chunk in self._partial_buffer]
            merged_text = " ".join(texts)
            # Use highest composite confidence from parts
            composite = max(
                chunk.get("_composite_confidence", 0.0) for chunk in self._partial_buffer
            )
            all_hypotheses = []
            for chunk in self._partial_buffer:
                all_hypotheses.extend(chunk.get("hypotheses", []))
            self._partial_buffer.clear()

        return {
            "type": "question",
            "text": merged_text,
            "hypotheses": all_hypotheses,
            "_composite_confidence": composite,
            "timestamp": time.time(),
            "_from_buffer": True,
        }

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process(self, item: dict) -> Optional[dict]:
        """Run item through all four stages; return enriched item or None."""
        self._step_flow("perceive", {"text": item.get("text", "")})

        # Stage 1 — Filter
        item = self._filter.process(item)
        if item is None:
            self._publish("smart_ear_rejected", {
                "text": item.get("text", "") if item else "",
                "reason": "filter_stage",
            })
            return None

        # Stage 2 — Context
        item = self._context.process(item)
        if item is None:
            return None

        # Stage 3 — Hypothesis
        item = self._hypothesis.process(item)
        if item is None:
            return None

        # Publish candidates for observability
        self._publish("smart_ear_candidates", {
            "original": item.get("text", ""),
            "phonetic_alternatives": item.get("_phonetic_alternatives", []),
            "per_word_candidates": item.get("_per_word_candidates", []),
        })

        # Stage 4 — Selection
        item = self._selection.process(item)
        if item is None:
            return None

        self._step_flow("interpret", {"text": item.get("text", "")})

        self._publish("smart_ear_selected", {
            "text": item["text"],
            "composite_confidence": item.get("_composite_confidence", 0.0),
            "source": item.get("_selection_source", "original"),
        })

        return item

    def _process_with_streaming(self, raw_item: dict) -> Optional[dict]:
        """Process raw STT item, accumulate in partial buffer, maybe commit."""
        self._last_voice_ts = time.time()

        processed = self._process(raw_item)
        if processed is None:
            return None

        # Accumulate in streaming buffer
        with self._buffer_lock:
            old_text = " ".join(c["text"] for c in self._partial_buffer)
            self._partial_buffer.append(processed)
            new_text = " ".join(c["text"] for c in self._partial_buffer)

        if old_text and new_text != old_text:
            self._publish("smart_ear_updated", {"old": old_text, "new": new_text})

        # Check if we should commit now (buffer full)
        if len(self._partial_buffer) >= PARTIAL_BUFFER_SIZE:
            return self._flush_buffer()

        return None  # not yet committed — waiting for silence or buffer fill

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main loop — consumes from input_queue, emits to output_queue."""
        logger.info("SmartEar started")
        self.running = True

        while self.running:
            # Check if silence timeout expired → commit partial buffer
            if self._should_commit():
                committed = self._flush_buffer()
                if committed is not None:
                    logger.info(f"SmartEar committed (silence timeout): {committed['text']!r}")
                    try:
                        self.output_queue.put_nowait(committed)
                    except queue.Full:
                        logger.warning("SmartEar: output queue full, dropping committed item")

            try:
                item = self.input_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                result = self._process_with_streaming(item)
                if result is not None:
                    logger.info(f"SmartEar → AgentLoop: {result['text']!r}")
                    try:
                        self.output_queue.put_nowait(result)
                    except queue.Full:
                        logger.warning("SmartEar: output queue full, dropping item")
            except Exception as exc:
                logger.error(f"SmartEar processing error: {exc}", exc_info=True)
            finally:
                try:
                    self.input_queue.task_done()
                except Exception:
                    pass

        # Flush any remaining partial buffer on shutdown
        remaining = self._flush_buffer()
        if remaining:
            try:
                self.output_queue.put_nowait(remaining)
            except queue.Full:
                pass

        logger.info("SmartEar stopped")

    def stop(self) -> None:
        self.running = False
        if self.event_bus is not None:
            try:
                self.event_bus.unsubscribe("silence_detected", self._on_silence)
            except Exception:
                pass
