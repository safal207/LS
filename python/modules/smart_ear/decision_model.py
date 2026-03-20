"""SmartEar learned decision model — load / predict wrapper.

Replaces the hand-crafted heuristic::

    if corr_score >= orig_score + margin:
        selected = corrected_text

with a model-driven decision::

    score = decision_model.predict(features)
    if score > 0.5:
        selected = corrected_text

Fallback behaviour:
    When the model file does not exist (e.g. first run before any training),
    the class transparently falls back to the original heuristic using the
    ``vocab_score_original``, ``vocab_score_corrected``, and a configurable
    ``margin`` parameter.

Thread safety:
    ``predict()`` is read-only after ``load_model()`` — safe to call from
    multiple threads without locking.

Usage::

    from smart_ear.decision_model import SmartEarDecisionModel

    model = SmartEarDecisionModel()
    model.load_model()  # no-op if model file missing

    features = extract_features(item)
    prob = model.predict(features)   # float in [0, 1]
    confidence = model.predict_proba(features)  # same as predict for sklearn
"""

from __future__ import annotations

import logging
import os
import pickle
from typing import Any, Optional

from .features import features_to_vector

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "models", "smart_ear_model.pkl"
)


class SmartEarDecisionModel:
    """Wrapper around a trained sklearn classifier for SmartEar selection.

    Parameters
    ----------
    model_path:
        Path to the ``.pkl`` file produced by ``train_model.py``.
        Defaults to ``models/smart_ear_model.pkl`` relative to the repo root.
    heuristic_margin:
        Fallback margin used when the model is unavailable.
        ``corrected`` wins if ``vocab_score_corrected >= vocab_score_original
        + heuristic_margin``.
    threshold:
        Decision threshold applied to the predicted probability.
        Corrected text is chosen when ``predict() > threshold``.
    low_threshold:
        Below this confidence → keep original (zone: "original").
        Default 0.30.
    high_threshold:
        Above this confidence → use corrected (zone: "corrected").
        Default 0.70.
        Values between ``low_threshold`` and ``high_threshold`` enter the
        "uncertain" zone where the heuristic fallback is used instead.

    3-zone routing
    --------------
    When both ``low_threshold`` and ``high_threshold`` are set the model
    operates in three zones::

        prob < low_threshold   → "original"   (confident keep)
        low_threshold ≤ prob ≤ high_threshold → "uncertain" (heuristic)
        prob > high_threshold  → "corrected"  (confident use)

    Set ``low_threshold = 0`` and ``high_threshold = threshold`` to disable
    the uncertain zone and use classic binary thresholding.
    """

    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        heuristic_margin: float = 1.0,
        threshold: float = 0.5,
        low_threshold: float = 0.30,
        high_threshold: float = 0.70,
    ) -> None:
        self.model_path = os.path.abspath(model_path)
        self.heuristic_margin = heuristic_margin
        self.threshold = threshold
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self._model: Optional[Any] = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_model(self) -> bool:
        """Load the model from disk.

        Returns:
            ``True`` if a model was loaded, ``False`` if file not found.
            Falls back to heuristic transparently — never raises.
        """
        if not os.path.exists(self.model_path):
            logger.info(
                "SmartEarDecisionModel: model not found at %s — using heuristic fallback",
                self.model_path,
            )
            return False

        try:
            with open(self.model_path, "rb") as fh:
                self._model = pickle.load(fh)
            self._loaded = True
            logger.info(
                "SmartEarDecisionModel: loaded %s from %s",
                type(self._model).__name__,
                self.model_path,
            )
            return True
        except Exception as exc:
            logger.warning("SmartEarDecisionModel: load failed (%s) — using heuristic", exc)
            return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Predict
    # ------------------------------------------------------------------

    def predict(self, features: dict) -> float:
        """Return probability that corrected text is the better choice.

        Returns a float in ``[0, 1]``.  Values > ``self.threshold`` mean
        "choose corrected"; values <= ``self.threshold`` mean "keep original".

        Falls back to heuristic score (0.0 or 1.0) when model is unavailable.
        """
        if self._loaded and self._model is not None:
            return self._predict_model(features)
        return self._predict_heuristic(features)

    def predict_proba(self, features: dict) -> float:
        """Alias for :meth:`predict` — returns probability in ``[0, 1]``."""
        return self.predict(features)

    def zone(self, features: dict) -> str:
        """Return routing zone: ``"original"``, ``"uncertain"``, or ``"corrected"``.

        * ``"original"``  — model confident: keep original text.
        * ``"corrected"`` — model confident: use corrected text.
        * ``"uncertain"`` — model is in the grey zone; use heuristic fallback.

        When the model is not loaded, always returns ``"uncertain"`` so the
        heuristic takes over.
        """
        if not (self._loaded and self._model is not None):
            return "uncertain"

        prob = self._predict_model(features)
        if prob < self.low_threshold:
            return "original"
        if prob > self.high_threshold:
            return "corrected"
        return "uncertain"

    def _predict_model(self, features: dict) -> float:
        vector = features_to_vector(features)
        try:
            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba([vector])[0]
                # class 1 = "corrected" chosen
                classes = list(self._model.classes_)
                idx = classes.index(1) if 1 in classes else -1
                return float(proba[idx]) if idx >= 0 else float(proba[-1])
            # Fallback for models without predict_proba
            return float(self._model.predict([vector])[0])
        except Exception as exc:
            logger.debug("SmartEarDecisionModel: predict failed (%s) — using heuristic", exc)
            return self._predict_heuristic(features)

    def _predict_heuristic(self, features: dict) -> float:
        """Original heuristic expressed as probability (0.0 or 1.0)."""
        orig = features.get("vocab_score_original", 0.0)
        corr = features.get("vocab_score_corrected", 0.0)
        if corr >= orig + self.heuristic_margin:
            return 1.0
        return 0.0
