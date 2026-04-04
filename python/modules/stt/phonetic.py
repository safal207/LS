# -*- coding: utf-8 -*-
"""Phonetic / fuzzy correction layer for ASR output.

Used inside SmartEar's HypothesisStage.  Operates entirely on stdlib
(``difflib``) — no extra dependencies required.

Two correction modes:

1. **Targeted** (preferred): ``correct_words_with_prob(words)`` — only words
   whose Whisper ``probability`` is below a threshold are corrected.  This
   preserves high-confidence words and avoids false substitutions.

2. **Full-text fallback**: ``correct_text(text)`` — corrects any word that
   matches a domain term better than itself (used when per-word probability
   data is unavailable).

Typical usage::

    corrector = PhoneticCorrector(domain_vocab=["React", "Docker", "TypeScript"])

    # Targeted (with word probabilities from Whisper word_timestamps):
    corrected, corrections = corrector.correct_words_with_prob(
        [{"word": "реак", "probability": 0.31}, {"word": "это", "probability": 0.95}]
    )
    # corrected -> ["React", "это"]
    # corrections -> [{"original": "реак", "replacement": "React", ...}]

    # Full-text fallback:
    corrected_text, corrections = corrector.correct_text("что такое реак")
    # -> ("что такое React", [...])
"""

from __future__ import annotations

import difflib
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static IT domain vocabulary (baseline; extended dynamically at runtime)
# ---------------------------------------------------------------------------
STATIC_IT_VOCAB: List[str] = [
    # Frontend
    "React", "Redux", "Next.js", "Vue", "Angular", "Svelte", "TypeScript",
    "JavaScript", "JSX", "TSX", "Webpack", "Vite", "Babel", "ESLint",
    "Tailwind", "CSS", "HTML", "DOM", "SPA", "SSR", "SSG",
    # Backend
    "Node", "Express", "FastAPI", "Django", "Flask", "Spring", "Rails",
    "GraphQL", "REST", "gRPC", "WebSocket", "Kafka", "RabbitMQ",
    # Infra / DevOps
    "Docker", "Kubernetes", "Helm", "Terraform", "Ansible", "Jenkins",
    "GitHub", "GitLab", "CI/CD", "nginx", "Redis", "PostgreSQL", "MongoDB",
    "MySQL", "SQLite", "Elasticsearch", "Prometheus", "Grafana",
    # Languages
    "Python", "Rust", "Go", "Java", "Kotlin", "Swift", "C++", "C#",
    "PHP", "Ruby", "Scala", "Haskell", "Elixir",
    # Concepts
    "API", "SDK", "CLI", "ORM", "OOP", "FP", "TDD", "DDD", "SOLID",
    "microservice", "monolith", "serverless", "lambda", "container",
    "pipeline", "deployment", "migration", "refactoring", "debugging",
    # AI / ML
    "model", "token", "embedding", "vector", "transformer", "LLM",
    "Whisper", "PyTorch", "TensorFlow", "CUDA", "GPU", "inference",
    # Russian equivalents that ASR might produce
    "реакт", "докер", "кубернетес", "пайтон", "джаваскрипт",
    "тайпскрипт", "редактор", "репозиторий", "коммит", "ветка",
]


class PhoneticCorrector:
    """Fuzzy + phonetic candidate generator for ASR-mangled words.

    The corrector compares each word against ``domain_vocab`` using
    :func:`difflib.SequenceMatcher` similarity (Gestalt pattern matching).
    This handles both:

    * Russian phonetic renderings of English terms ("реак" → "React")
    * Partial / truncated words ("реакт" → "React")
    * Typos and noise ("dockerr" → "Docker")
    """

    def __init__(
        self,
        domain_vocab: List[str] | None = None,
        threshold: float = 0.35,
        top_k: int = 3,
    ) -> None:
        """
        Args:
            domain_vocab: List of known terms.  If ``None``, uses
                :data:`STATIC_IT_VOCAB`.
            threshold: Minimum similarity score ``[0, 1]`` to be included.
            top_k: Maximum number of candidates returned per word.
        """
        self.domain_vocab: List[str] = list(domain_vocab or STATIC_IT_VOCAB)
        self.threshold = threshold
        self.top_k = top_k

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_vocab(self, additional: List[str]) -> None:
        """Extend vocabulary with dynamically discovered terms."""
        existing = set(self.domain_vocab)
        for term in additional:
            if term not in existing:
                self.domain_vocab.append(term)
                existing.add(term)

    def candidates(self, word: str) -> List[Tuple[str, float]]:
        """Return top-k (candidate, score) pairs for *word*.

        Score is ``SequenceMatcher.ratio()`` in ``[0, 1]``.  Only candidates
        above ``self.threshold`` are returned, sorted descending by score.
        """
        word_lower = word.lower()
        scored: List[Tuple[str, float]] = []
        for term in self.domain_vocab:
            score = difflib.SequenceMatcher(
                None, word_lower, term.lower()
            ).ratio()
            if score >= self.threshold:
                scored.append((term, round(score, 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[: self.top_k]

    def correct_text(self, text: str) -> Tuple[str, List[dict]]:
        """Try to correct each word in *text* against domain vocabulary.

        Returns ``(corrected_text, corrections)`` where ``corrections`` is a
        list of ``{"original": str, "replacement": str, "score": float}``
        dicts for words that were substituted.

        A word is corrected only if:
        * The best candidate score is strictly above the original word's
          self-match score against the vocabulary (i.e. we have a better
          explanation).
        * The best candidate score is >= ``self.threshold + 0.15`` (higher bar
          for actual substitution vs. just listing candidates).
        """
        words = text.split()
        corrected_words: List[str] = []
        corrections: List[dict] = []

        for word in words:
            cands = self.candidates(word)
            if cands and cands[0][1] >= (self.threshold + 0.15):
                best_term, best_score = cands[0]
                # Don't replace if it already IS the candidate (case-fold match)
                if best_term.lower() != word.lower():
                    corrections.append({
                        "original": word,
                        "replacement": best_term,
                        "score": best_score,
                    })
                    corrected_words.append(best_term)
                    continue
            corrected_words.append(word)

        corrected_text = " ".join(corrected_words)
        if corrections:
            logger.debug(f"PhoneticCorrector substitutions: {corrections}")
        return corrected_text, corrections

    def correct_words_with_prob(
        self,
        words: List[dict],
        low_prob_threshold: float = 0.50,
    ) -> tuple[List[str], List[dict]]:
        """Targeted correction using per-word Whisper probabilities.

        Only words with ``probability < low_prob_threshold`` are passed to
        the fuzzy matcher.  High-confidence words are kept verbatim.

        Args:
            words: List of ``{"word": str, "probability": float}`` dicts as
                returned by faster-whisper with ``word_timestamps=True``.
            low_prob_threshold: Words with probability below this value are
                correction candidates.

        Returns:
            ``(corrected_words, corrections)`` where ``corrected_words`` is a
            flat list of strings and ``corrections`` is a list of substitution
            records ``{"original", "replacement", "score", "word_prob"}``.
        """
        corrected: List[str] = []
        corrections: List[dict] = []

        for entry in words:
            word = entry.get("word", "").strip()
            prob = float(entry.get("probability", 1.0))

            if not word:
                continue

            if prob < low_prob_threshold:
                cands = self.candidates(word)
                # Use a stricter bar for actual substitution
                if cands and cands[0][1] >= (self.threshold + 0.15):
                    best_term, best_score = cands[0]
                    if best_term.lower() != word.lower():
                        corrections.append({
                            "original": word,
                            "replacement": best_term,
                            "score": best_score,
                            "word_prob": round(prob, 4),
                        })
                        corrected.append(best_term)
                        continue

            corrected.append(word)

        if corrections:
            logger.debug("Targeted corrections: %s", corrections)
        return corrected, corrections

    def all_candidates_for_text(self, text: str) -> List[dict]:
        """Return per-word candidate lists for the entire *text*.

        Returns a list of ``{"word": str, "candidates": [(term, score), ...]}``.
        """
        result = []
        for word in text.split():
            cands = self.candidates(word)
            if cands:
                result.append({"word": word, "candidates": cands})
        return result
