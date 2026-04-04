"""Offline training script for the SmartEar decision model.

Reads ``data/smart_ear_dataset.jsonl``, trains a LightGBM classifier
(with XGBoost fallback, then LogisticRegression as last resort), calibrates
the probability output with :class:`~smart_ear.calibration.ProbabilityCalibrator`,
and saves the model bundle to ``models/smart_ear_model.pkl``.

Model bundle format (saved as pickle)::

    {
        "model":      <fitted LGBMClassifier / XGBClassifier / Pipeline>,
        "calibrator": <ProbabilityCalibrator>,
        "version":    "v20260320_143022",
        "accuracy":   0.934,
        "features":   [...FEATURE_NAMES...],
    }

Usage::

    cd /path/to/repo
    python -m smart_ear.train_model
    # or
    python python/modules/smart_ear/train_model.py

Outputs::

    models/smart_ear_model.pkl           — latest model bundle
    models/smart_ear_model_v{ts}.pkl     — versioned copy

Minimum dataset size: 200 samples (configurable via --min-samples).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── path bootstrap (allow running as __main__ from any cwd) ──────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "python", "modules"))

from smart_ear.features import FEATURE_NAMES, features_to_vector  # noqa: E402
from smart_ear.calibration import ProbabilityCalibrator           # noqa: E402


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_DATASET     = os.path.join(_REPO_ROOT, "data", "smart_ear_dataset.jsonl")
DEFAULT_MODEL       = os.path.join(_REPO_ROOT, "models", "smart_ear_model.pkl")
DEFAULT_TEST_FRAC   = 0.20
DEFAULT_MIN_SAMPLES = 200


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_dataset(path: str) -> Tuple[List[List[float]], List[int]]:
    """Read JSONL dataset and return (X, y).

    y = 1  if chosen == "corrected"  (binary training label)
    y = 0  otherwise (original kept)

    New optional fields (avg_candidate_score, max_candidate_score, entropy_word_probs,
    correction_ratio) are read when present; older records without them fall back to 0.
    """
    X: List[List[float]] = []
    y: List[int] = []
    skipped = 0

    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Line %d: JSON parse error (%s) — skipped", lineno, exc)
                skipped += 1
                continue

            original_text: str = record.get("original_text", "")
            text_length = max(len(original_text.split()), 1)
            num_corrections = int(record.get("num_corrections", 0))

            features = {
                "asr_confidence":        float(record.get("asr_confidence", 0.0)),
                "composite_confidence":  float(record.get("composite_confidence", 0.0)),
                "num_corrections":       float(num_corrections),
                "avg_word_probability":  float(record.get("avg_word_prob", record.get("asr_confidence", 0.0))),
                "text_length":           float(text_length),
                "vocab_score_original":  float(record.get("vocab_score_original", 0.0)),
                "vocab_score_corrected": float(record.get("vocab_score_corrected", 0.0)),
                "context_overlap":       float(record.get("context_overlap", 0.0)),
                "model_confidence":      0.0,
                # New features (may not be in older records → default 0)
                "correction_ratio":      float(record.get("correction_ratio", num_corrections / text_length)),
                "avg_candidate_score":   float(record.get("avg_candidate_score", 0.0)),
                "max_candidate_score":   float(record.get("max_candidate_score", 0.0)),
                "entropy_word_probs":    float(record.get("entropy_word_probs", 0.0)),
            }

            label = 1 if record.get("chosen", "original") == "corrected" else 0
            X.append(features_to_vector(features))
            y.append(label)

    logger.info("Dataset: %d samples loaded, %d skipped", len(X), skipped)
    return X, y


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def _build_model() -> Tuple[Any, str]:
    """Return (model, name_str) trying LightGBM → XGBoost → LogisticRegression."""
    # 1. LightGBM (preferred)
    try:
        import lightgbm as lgb
        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            class_weight="balanced",
            random_state=42,
            verbose=-1,
        )
        return model, "LightGBM"
    except ImportError:
        pass

    # 2. XGBoost fallback
    try:
        import xgboost as xgb
        model = xgb.XGBClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            eval_metric="logloss",
            random_state=42,
        )
        return model, "XGBoost"
    except ImportError:
        pass

    # 3. LogisticRegression last resort (sklearn always present)
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
            )),
        ])
        return model, "LogisticRegression"
    except ImportError:
        pass

    raise RuntimeError(
        "No ML library available. Install: pip install lightgbm  OR  xgboost  OR  scikit-learn"
    )


# ---------------------------------------------------------------------------
# Feature importance
# ---------------------------------------------------------------------------

def _log_feature_importance(model: Any, model_name: str, top_n: int = 5) -> None:
    """Log top-N feature importances if the model supports it."""
    try:
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "named_steps"):
            # sklearn Pipeline — check clf step
            clf = model.named_steps.get("clf")
            if clf is None or not hasattr(clf, "coef_"):
                return
            importances = [abs(c) for c in clf.coef_[0]]
        else:
            return

        pairs = sorted(
            zip(FEATURE_NAMES, importances),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        print(f"\n── Feature Importance ({model_name}) — Top {top_n} ──────────────")
        for name, imp in pairs[:top_n]:
            bar = "█" * min(int(abs(imp) / max(abs(pairs[0][1]), 1e-9) * 20), 20)
            print(f"  {name:<26} {imp:8.4f}  {bar}")
        print("────────────────────────────────────────────────────────────────\n")
        logger.info(
            "Top features: %s",
            ", ".join(f"{n}={v:.4f}" for n, v in pairs[:top_n]),
        )
    except Exception as exc:
        logger.debug("Feature importance logging failed: %s", exc)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    dataset_path: str,
    model_path: str,
    test_frac: float = DEFAULT_TEST_FRAC,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    previous_accuracy: Optional[float] = None,
) -> Optional[float]:
    """Train and save the model.

    Parameters
    ----------
    dataset_path:
        Path to JSONL dataset.
    model_path:
        Output path for the ``smart_ear_model.pkl`` bundle.
    test_frac:
        Fraction of data to hold out for evaluation (default 0.20).
    min_samples:
        Minimum number of samples required; training skipped if fewer (default 200).
    previous_accuracy:
        If provided, the new model must exceed this accuracy to be saved
        (validation gate).  Pass ``None`` to skip the gate.

    Returns
    -------
    Accuracy on the test split, or ``None`` if training was skipped / rejected.
    """
    try:
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score
    except ImportError:
        logger.error("scikit-learn is not installed.  Run: pip install scikit-learn")
        sys.exit(1)

    if not os.path.exists(dataset_path):
        logger.error("Dataset not found: %s", dataset_path)
        logger.error("Run SmartEar with audit enabled to collect training data first.")
        sys.exit(1)

    X, y = load_dataset(dataset_path)

    # ── Minimum dataset gate ─────────────────────────────────────────────
    if len(X) < min_samples:
        logger.warning(
            "Dataset too small (%d samples) — need at least %d to train. Skipping.",
            len(X), min_samples,
        )
        return None

    # Class distribution
    n_corrected = sum(y)
    n_original  = len(y) - n_corrected
    logger.info("Class distribution: corrected=%d  original=%d", n_corrected, n_original)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_frac,
        random_state=42,
        stratify=y if min(n_corrected, n_original) >= 2 else None,
    )

    model, model_name = _build_model()
    logger.info("Training %s on %d samples…", model_name, len(X_train))
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_pred_proba = [p[1] if hasattr(p, "__len__") and len(p) > 1 else float(p)
                    for p in model.predict_proba(X_test)]

    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec  = recall_score(y_test, y_pred, zero_division=0)

    print("\n── SmartEar Decision Model — Training Results ──────────────────")
    print(f"  Model         : {model_name}")
    print(f"  Samples       : {len(X)} total  ({len(X_train)} train / {len(X_test)} test)")
    print(f"  Features      : {len(FEATURE_NAMES)} features")
    print(f"  Accuracy      : {acc:.4f}")
    print(f"  Precision     : {prec:.4f}   (of all 'corrected' predictions, how many right)")
    print(f"  Recall        : {rec:.4f}   (of all real 'corrected', how many caught)")
    print("────────────────────────────────────────────────────────────────\n")

    # ── Validation gate ──────────────────────────────────────────────────
    if previous_accuracy is not None and acc < previous_accuracy:
        logger.warning(
            "Validation gate: new model accuracy %.4f < old %.4f — REJECTING",
            acc, previous_accuracy,
        )
        return None

    # ── Feature importance ───────────────────────────────────────────────
    _log_feature_importance(model, model_name, top_n=5)

    # ── Probability calibration ──────────────────────────────────────────
    calibrator = ProbabilityCalibrator(method="auto")
    calibrator.fit(y_test, y_pred_proba)

    # ── Version stamp ────────────────────────────────────────────────────
    version = "v" + datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Save model bundle ────────────────────────────────────────────────
    bundle: Dict[str, Any] = {
        "model":      model,
        "calibrator": calibrator,
        "version":    version,
        "accuracy":   acc,
        "features":   FEATURE_NAMES,
        "model_name": model_name,
    }

    model_dir = os.path.dirname(model_path)
    if model_dir:
        os.makedirs(model_dir, exist_ok=True)

    # Primary path (hot-swap target)
    with open(model_path, "wb") as fh:
        pickle.dump(bundle, fh)
    # Emit structured marker so auto_trainer can parse accuracy reliably
    print(f"METRIC:accuracy={acc:.4f}")
    logger.info("Model saved → %s  (version=%s, acc=%.4f)", model_path, version, acc)

    # Versioned copy
    base, ext = os.path.splitext(model_path)
    versioned_path = f"{base}_{version}{ext}"
    with open(versioned_path, "wb") as fh:
        pickle.dump(bundle, fh)
    logger.info("Versioned copy → %s", versioned_path)

    return acc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train SmartEar decision model")
    parser.add_argument("--dataset", default=DEFAULT_DATASET,
                        help=f"Path to JSONL dataset (default: {DEFAULT_DATASET})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Output model path (default: {DEFAULT_MODEL})")
    parser.add_argument("--test-frac", type=float, default=DEFAULT_TEST_FRAC,
                        help=f"Test split fraction (default: {DEFAULT_TEST_FRAC})")
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES,
                        help=f"Minimum dataset size (default: {DEFAULT_MIN_SAMPLES})")
    parser.add_argument("--previous-accuracy", type=float, default=None,
                        help="Reject new model if accuracy is lower than this value")
    args = parser.parse_args()

    result = train(
        args.dataset,
        args.model,
        args.test_frac,
        args.min_samples,
        args.previous_accuracy,
    )
    if result is None:
        sys.exit(1)  # signal failure to auto_trainer subprocess check


if __name__ == "__main__":
    main()
