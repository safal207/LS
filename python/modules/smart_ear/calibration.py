"""Probability calibration for SmartEar ML decisions.

Wraps sklearn's IsotonicRegression (preferred when data ≥ 50 samples)
with a Platt-scaling fallback (logistic regression on raw probabilities),
so raw model output is converted into well-calibrated probability estimates.

Why calibration matters:
    A model that outputs 0.82 should be correct ~82 % of the time.
    Without calibration, tree-based models (LightGBM, XGBoost) tend to be
    over-confident, pushing probabilities toward 0 or 1.

Usage::

    from smart_ear.calibration import ProbabilityCalibrator

    cal = ProbabilityCalibrator()
    cal.fit(y_true, y_pred_proba)        # train on held-out data
    calibrated = cal.transform(0.82)     # scalar → scalar
    calibrated = cal.transform([0.3, 0.82, 0.55])  # list → list

Persistence::

    import pickle
    with open("calibrator.pkl", "wb") as f:
        pickle.dump(cal, f)
"""

from __future__ import annotations

import logging
from typing import List, Sequence, Union

logger = logging.getLogger(__name__)

# Minimum samples to use IsotonicRegression; below this use Platt scaling.
_ISO_MIN_SAMPLES = 50

# Type alias
_NumericInput = Union[float, Sequence[float]]


class ProbabilityCalibrator:
    """Calibrate raw model probabilities to empirical ones.

    Parameters
    ----------
    method:
        ``"auto"`` (default) — IsotonicRegression when ≥ 50 samples, else Platt.
        ``"isotonic"`` — always use IsotonicRegression.
        ``"platt"`` — always use Platt scaling (logistic regression).

    Attributes
    ----------
    is_fitted:
        True after :meth:`fit` has been called successfully.
    method_used:
        The calibration method actually used (set after fit).
    """

    def __init__(self, method: str = "auto") -> None:
        if method not in ("auto", "isotonic", "platt"):
            raise ValueError(f"method must be 'auto', 'isotonic', or 'platt'; got {method!r}")
        self.method = method
        self._calibrator = None
        self.is_fitted = False
        self.method_used: str = "none"

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(
        self,
        y_true: Sequence[int],
        y_pred_proba: Sequence[float],
    ) -> "ProbabilityCalibrator":
        """Fit the calibrator on held-out (validation) predictions.

        Parameters
        ----------
        y_true:
            Ground-truth binary labels (0 or 1).
        y_pred_proba:
            Raw model probabilities for class 1 (shape: [n_samples]).

        Returns
        -------
        self — for chaining.
        """
        try:
            from sklearn.isotonic import IsotonicRegression
            from sklearn.linear_model import LogisticRegression
        except ImportError:
            logger.warning(
                "ProbabilityCalibrator: scikit-learn not installed — calibration disabled"
            )
            return self

        y_true_arr = list(y_true)
        y_proba_arr = list(y_pred_proba)
        n = len(y_true_arr)

        if n < 5:
            logger.warning(
                "ProbabilityCalibrator: only %d samples — cannot fit calibrator (need ≥ 5)", n
            )
            return self

        use_isotonic = (
            self.method == "isotonic"
            or (self.method == "auto" and n >= _ISO_MIN_SAMPLES)
        )

        if use_isotonic:
            try:
                iso = IsotonicRegression(out_of_bounds="clip")
                iso.fit(y_proba_arr, y_true_arr)
                self._calibrator = iso
                self.method_used = "isotonic"
                logger.info(
                    "ProbabilityCalibrator: fitted IsotonicRegression on %d samples", n
                )
            except Exception as exc:
                logger.warning(
                    "ProbabilityCalibrator: IsotonicRegression failed (%s) — falling back to Platt",
                    exc,
                )
                use_isotonic = False

        if not use_isotonic:
            # Platt scaling: fit a logistic regression on raw probas
            try:
                X_platt = [[p] for p in y_proba_arr]
                lr = LogisticRegression(max_iter=1000, random_state=42)
                lr.fit(X_platt, y_true_arr)
                self._calibrator = lr
                self.method_used = "platt"
                logger.info(
                    "ProbabilityCalibrator: fitted Platt scaling on %d samples", n
                )
            except Exception as exc:
                logger.warning(
                    "ProbabilityCalibrator: Platt scaling also failed (%s) — passthrough only", exc
                )
                return self

        self.is_fitted = True
        return self

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    def transform(self, proba: _NumericInput) -> _NumericInput:
        """Map raw probability/ies to calibrated probability/ies.

        Parameters
        ----------
        proba:
            A single float or a list/sequence of floats.

        Returns
        -------
        Calibrated probability (same type as input — scalar in, scalar out).
        """
        if not self.is_fitted or self._calibrator is None:
            # Passthrough — no calibration available
            return proba

        scalar_input = isinstance(proba, (int, float))
        values: List[float] = [float(proba)] if scalar_input else [float(p) for p in proba]

        try:
            if self.method_used == "isotonic":
                calibrated = list(self._calibrator.predict(values))
            else:
                # Platt: predict_proba returns [[p0, p1], ...]
                X = [[v] for v in values]
                calibrated = [row[1] for row in self._calibrator.predict_proba(X)]

            # Clip to [0, 1] for safety
            calibrated = [max(0.0, min(1.0, c)) for c in calibrated]

        except Exception as exc:
            logger.debug("ProbabilityCalibrator.transform failed (%s) — passthrough", exc)
            return proba

        return float(calibrated[0]) if scalar_input else calibrated

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        status = f"method={self.method_used}" if self.is_fitted else "unfitted"
        return f"ProbabilityCalibrator({status})"
