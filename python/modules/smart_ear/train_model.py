"""Offline training script for the SmartEar decision model.

Reads ``data/smart_ear_dataset.jsonl``, trains a LogisticRegression
classifier, and saves the model to ``models/smart_ear_model.pkl``.

Usage::

    cd /path/to/repo
    python -m smart_ear.train_model
    # or
    python python/modules/smart_ear/train_model.py

Outputs::

    models/smart_ear_model.pkl   — trained model
    Accuracy  / Precision / Recall printed to stdout
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
from typing import List, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── path bootstrap (allow running as __main__ from any cwd) ──────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "python", "modules"))

from smart_ear.features import FEATURE_NAMES, features_to_vector  # noqa: E402


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_DATASET = os.path.join(_REPO_ROOT, "data", "smart_ear_dataset.jsonl")
DEFAULT_MODEL   = os.path.join(_REPO_ROOT, "models", "smart_ear_model.pkl")
DEFAULT_TEST_FRAC = 0.20


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_dataset(path: str) -> Tuple[List[List[float]], List[int]]:
    """Read JSONL dataset and return (X, y).

    y = 1  if chosen == "corrected"
    y = 0  otherwise (original / fallback)
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

            # Build a synthetic item dict from the JSONL record fields
            item = {
                "_asr_confidence":       record.get("asr_confidence", 0.0),
                "_composite_confidence": record.get("composite_confidence", 0.0),
                "_phonetic_corrections": [{}] * int(record.get("num_corrections", 0)),
                "_words":                [],  # avg_word_prob already in record
                "text":                  record.get("original_text", ""),
                "_original_text":        record.get("original_text", ""),
                "_vocab_score_original": record.get("vocab_score_original", 0.0),
                "_vocab_score_corrected":record.get("vocab_score_corrected", 0.0),
                "_context_overlap":      record.get("context_overlap", 0.0),
                "_selection_source":     record.get("chosen", "original"),
            }

            features = {
                "asr_confidence":        item["_asr_confidence"],
                "composite_confidence":  item["_composite_confidence"],
                "num_corrections":       float(int(record.get("num_corrections", 0))),
                "avg_word_probability":  float(record.get("avg_word_prob", item["_asr_confidence"])),
                "text_length":           float(len(item["_original_text"].split())),
                "vocab_score_original":  item["_vocab_score_original"],
                "vocab_score_corrected": item["_vocab_score_corrected"],
                "context_overlap":       item["_context_overlap"],
                "model_confidence":      0.0,
            }

            label = 1 if record.get("chosen", "original") == "corrected" else 0
            X.append(features_to_vector(features))
            y.append(label)

    logger.info("Dataset: %d samples loaded, %d skipped", len(X), skipped)
    return X, y


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(dataset_path: str, model_path: str, test_frac: float = DEFAULT_TEST_FRAC) -> None:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
    except ImportError:
        logger.error(
            "scikit-learn is not installed.  Run: pip install scikit-learn"
        )
        sys.exit(1)

    if not os.path.exists(dataset_path):
        logger.error("Dataset not found: %s", dataset_path)
        logger.error("Run SmartEar with audit enabled to collect training data first.")
        sys.exit(1)

    X, y = load_dataset(dataset_path)

    if len(X) < 10:
        logger.error(
            "Too few samples (%d).  Need at least 10 to train.  "
            "Keep running SmartEar to collect more data.",
            len(X),
        )
        sys.exit(1)

    # Class distribution
    n_corrected = sum(y)
    n_original  = len(y) - n_corrected
    logger.info("Class distribution: corrected=%d  original=%d", n_corrected, n_original)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_frac, random_state=42, stratify=y if min(n_corrected, n_original) >= 2 else None
    )

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",  # handles imbalanced datasets
            random_state=42,
        )),
    ])
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec  = recall_score(y_test, y_pred, zero_division=0)

    print("\n── SmartEar Decision Model — Training Results ──────────────────")
    print(f"  Samples       : {len(X)} total  ({len(X_train)} train / {len(X_test)} test)")
    print(f"  Features      : {FEATURE_NAMES}")
    print(f"  Accuracy      : {acc:.4f}")
    print(f"  Precision     : {prec:.4f}   (of all 'corrected' predictions, how many right)")
    print(f"  Recall        : {rec:.4f}   (of all real 'corrected', how many caught)")
    print("────────────────────────────────────────────────────────────────\n")

    # Coefficients (interpretability)
    clf = model.named_steps["clf"]
    coef_pairs = sorted(
        zip(FEATURE_NAMES, clf.coef_[0]),
        key=lambda x: abs(x[1]),
        reverse=True,
    )
    print("Feature weights (sorted by importance):")
    for name, coef in coef_pairs:
        bar = "+" * int(abs(coef) * 10) if coef > 0 else "-" * int(abs(coef) * 10)
        print(f"  {name:<26} {coef:+.4f}  {bar}")
    print()

    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "wb") as fh:
        pickle.dump(model, fh)
    logger.info("Model saved → %s", model_path)


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
    args = parser.parse_args()

    train(args.dataset, args.model, args.test_frac)


if __name__ == "__main__":
    main()
