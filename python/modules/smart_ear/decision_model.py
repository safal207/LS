"""SmartEar learned decision model — load / predict wrapper.

Replaces the hand-crafted heuristic::

    if corr_score >= orig_score + margin:
        selected = corrected_text

with a model-driven decision::

    score = decision_model.predict(features)
    if score > 0.5:
        selected = corrected_text

Model support:
    LightGBM (preferred) → XGBoost → sklearn Pipeline (legacy)
    The model is loaded from a ``.pkl`` file produced by ``train_model.py``.

Calibration:
    An optional :class:`~smart_ear.calibration.ProbabilityCalibrator` can be
    attached (``model.calibrator = cal``) to post-process raw probabilities.

Fallback behaviour:
    When the model file does not exist (e.g. first run before any training),
    the class transparently falls back to the original heuristic using the
    ``vocab_score_original``, ``vocab_score_corrected``, and a configurable
    ``margin`` parameter.

Thread safety:
    ``predict()`` is read-only after ``load_model()`` — safe to call from
    multiple threads without locking.

3-zone routing (production-grade):
    prob < 0.25   → "ml_strong_original"  (confident — keep original)
    prob > 0.75   → "ml_strong_correct"   (confident — use corrected)
    0.25–0.75     → "uncertain"           (fallback to heuristic)

Usage::

    from smart_ear.decision_model import SmartEarDecisionModel

    model = SmartEarDecisionModel()
    model.load_model()  # no-op if model file missing

    features = extract_features(item)
    result = model.decide(features)
    # result["decision_zone"], result["calibrated_proba"], ...
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from typing import Any, Dict, Optional

from .features import features_to_vector

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "models", "smart_ear_model.pkl"
)

# Zone thresholds (production-grade, tighter than old 0.30/0.70)
_STRONG_ORIGINAL_THRESHOLD = 0.25   # below → ml_strong_original
_STRONG_CORRECT_THRESHOLD  = 0.75   # above → ml_strong_correct


class SmartEarDecisionModel:
    """Wrapper around a trained classifier for SmartEar selection.

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
        Below this confidence → zone "ml_strong_original" (default 0.25).
    high_threshold:
        Above this confidence → zone "ml_strong_correct" (default 0.75).
        Values between low and high → "uncertain" zone → heuristic fallback.
    calibrator:
        Optional :class:`~smart_ear.calibration.ProbabilityCalibrator`.
        Can be set after construction: ``model.calibrator = cal``.
    model_version:
        Version tag used in audit logs (e.g. "v20260320").
    """

    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        heuristic_margin: float = 1.0,
        threshold: float = 0.5,
        low_threshold: float = _STRONG_ORIGINAL_THRESHOLD,
        high_threshold: float = _STRONG_CORRECT_THRESHOLD,
        calibrator=None,
        model_version: str = "unknown",
    ) -> None:
        self.model_path = os.path.abspath(model_path)
        self.heuristic_margin = heuristic_margin
        self.threshold = threshold
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.calibrator = calibrator
        self.model_version = model_version
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
                payload = pickle.load(fh)

            # Support versioned payloads: dict with 'model' and 'version' keys
            if isinstance(payload, dict) and "model" in payload:
                candidate = payload["model"]
                self.model_version = payload.get("version", self.model_version)
                # Load calibrator from payload if present and not already set
                if self.calibrator is None and "calibrator" in payload:
                    self.calibrator = payload["calibrator"]
            else:
                candidate = payload

            if not hasattr(candidate, "predict_proba"):
                raise ValueError(
                    f"Model object {type(candidate)} missing predict_proba — "
                    "expected a fitted classifier"
                )
            self._model = candidate
            self._loaded = True
            logger.info(
                "SmartEarDecisionModel: loaded %s (version=%s) from %s",
                type(self._model).__name__,
                self.model_version,
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

    def zone_from_prob(self, prob: float) -> str:
        """Map an already-computed probability to a routing zone.

        Zones:
        * ``"ml_strong_original"`` — prob < ``low_threshold`` (confident: keep)
        * ``"ml_strong_correct"``  — prob > ``high_threshold`` (confident: use)
        * ``"uncertain"``          — in between; use heuristic fallback

        When the model is not loaded, always returns ``"uncertain"``.
        """
        if not (self._loaded and self._model is not None):
            return "uncertain"
        if prob < self.low_threshold:
            return "ml_strong_original"
        if prob > self.high_threshold:
            return "ml_strong_correct"
        return "uncertain"

    def zone(self, features: dict) -> str:
        """Return routing zone from raw features (runs one inference).

        Prefer :meth:`zone_from_prob` when you have already called
        :meth:`predict_proba` to avoid a redundant model call.
        """
        return self.zone_from_prob(self.predict_proba(features))

    def decide(self, features: dict) -> Dict[str, Any]:
        """Full decision with ML internals — for use in SelectionStage.

        Returns a dict containing all fields needed for audit logging and
        routing decisions::

            {
                "ml_proba":         float,   # raw model probability
                "calibrated_proba": float,   # after calibration (or same as ml_proba)
                "decision_zone":    str,     # "ml_strong_original" / "ml_strong_correct" / "uncertain"
                "fallback_used":    bool,    # True when heuristic overrides ML
                "model_version":    str,
                "feature_extraction_time": float,  # seconds
                "model_inference_time":    float,  # seconds
                "total_decision_time":     float,  # seconds
            }

        The caller uses ``decision_zone`` to route:
            * "ml_strong_correct"  → use corrected text
            * "ml_strong_original" → keep original text
            * "uncertain"          → apply heuristic (``_predict_heuristic``)
        """
        t_start = time.perf_counter()

        # Feature extraction is already done by the caller, so we only
        # measure inference time here. We track a zero feature_extraction_time
        # to keep the audit schema consistent; callers that time extraction
        # separately may pass it in via features["_feature_extraction_time"].
        feature_extraction_time = float(features.get("_feature_extraction_time", 0.0))

        t_infer_start = time.perf_counter()
        ml_proba = self.predict(features)
        t_infer_end = time.perf_counter()
        model_inference_time = t_infer_end - t_infer_start

        # Calibration
        calibrated_proba = ml_proba
        if self.calibrator is not None and getattr(self.calibrator, "is_fitted", False):
            try:
                calibrated_proba = float(self.calibrator.transform(ml_proba))
            except Exception as exc:
                logger.debug("Calibration transform failed (%s) — using raw proba", exc)

        decision_zone = self.zone_from_prob(calibrated_proba)
        fallback_used = decision_zone == "uncertain"

        t_end = time.perf_counter()
        total_decision_time = t_end - t_start

        return {
            "ml_proba":                ml_proba,
            "calibrated_proba":        calibrated_proba,
            "decision_zone":           decision_zone,
            "fallback_used":           fallback_used,
            "model_version":           self.model_version,
            "feature_extraction_time": feature_extraction_time,
            "model_inference_time":    model_inference_time,
            "total_decision_time":     total_decision_time,
        }

    def _predict_model(self, features: dict) -> float:
        vector = features_to_vector(features)
        try:
            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba([vector])[0]
                # For sklearn pipelines: find class 1 index
                if hasattr(self._model, "classes_"):
                    classes = list(self._model.classes_)
                    idx = classes.index(1) if 1 in classes else -1
                    return float(proba[idx]) if idx >= 0 else float(proba[-1])
                # LightGBM / XGBoost: predict_proba returns [[p0, p1]]
                return float(proba[1]) if len(proba) > 1 else float(proba[0])
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
