#!/usr/bin/env python3
"""CLI test: compare heuristic vs learned decision model on dataset examples.

Usage::

    python scripts/test_decision_model.py
    python scripts/test_decision_model.py --n 20
    python scripts/test_decision_model.py --dataset data/smart_ear_dataset.jsonl
    python scripts/test_decision_model.py --model models/smart_ear_model.pkl

Output::

    10 examples from the dataset, side-by-side comparison:
    heuristic decision  vs  model decision  vs  ground truth (chosen)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

# ── path bootstrap ────────────────────────────────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
_MODULES   = os.path.join(_REPO_ROOT, "python", "modules")
sys.path.insert(0, _MODULES)

from smart_ear.features import extract_features, FEATURE_NAMES   # noqa: E402
from smart_ear.decision_model import SmartEarDecisionModel        # noqa: E402

# Default paths
DEFAULT_DATASET = os.path.join(_REPO_ROOT, "data", "smart_ear_dataset.jsonl")
DEFAULT_MODEL   = os.path.join(_REPO_ROOT, "models", "smart_ear_model.pkl")
DEFAULT_N       = 10
DEFAULT_MARGIN  = 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_records(path: str, n: int) -> list[dict]:
    if not os.path.exists(path):
        print(f"[ERROR] Dataset not found: {path}")
        print("        Run SmartEar with dataset_log_path set to collect data.")
        sys.exit(1)

    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not records:
        print("[ERROR] Dataset is empty.")
        sys.exit(1)

    # Pick a random sample (or all if dataset smaller)
    sample = random.sample(records, min(n, len(records)))
    return sample


def _heuristic_decision(record: dict, margin: float) -> str:
    orig = float(record.get("vocab_score_original", 0.0))
    corr = float(record.get("vocab_score_corrected", 0.0))
    return "corrected" if corr >= orig + margin else "original"


def _record_to_item(record: dict) -> dict:
    """Convert a JSONL record back to a SmartEar item dict for feature extraction."""
    return {
        "_asr_confidence":        record.get("asr_confidence", 0.0),
        "_composite_confidence":  record.get("composite_confidence", 0.0),
        "_phonetic_corrections":  [{}] * int(record.get("num_corrections", 0)),
        "_words":                 [],
        "_original_text":         record.get("original_text", ""),
        "text":                   record.get("original_text", ""),
        "_vocab_score_original":  record.get("vocab_score_original", 0.0),
        "_vocab_score_corrected": record.get("vocab_score_corrected", 0.0),
        "_context_overlap":       record.get("context_overlap", 0.0),
        "_selection_source":      record.get("chosen", "original"),
        "_model_confidence":      record.get("model_confidence", 0.0),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare heuristic vs model decisions on SmartEar dataset examples"
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--model",   default=DEFAULT_MODEL)
    parser.add_argument("--n",       type=int, default=DEFAULT_N,
                        help="Number of examples to test (default 10)")
    parser.add_argument("--margin",  type=float, default=DEFAULT_MARGIN,
                        help="Heuristic margin (default 1.0)")
    parser.add_argument("--seed",    type=int, default=None,
                        help="Random seed for reproducible sampling")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # Load model
    model = SmartEarDecisionModel(model_path=args.model, heuristic_margin=args.margin)
    model_loaded = model.load_model()

    print(f"\n{'═'*80}")
    print(f"  SmartEar Decision Model — Test ({args.n} examples)")
    print(f"  Dataset : {args.dataset}")
    print(f"  Model   : {args.model}  ({'LOADED' if model_loaded else 'NOT FOUND — heuristic only'})")
    print(f"{'═'*80}\n")

    records = _load_records(args.dataset, args.n)

    heuristic_correct = 0
    model_correct     = 0

    for i, record in enumerate(records, 1):
        ground_truth = record.get("chosen", "original")
        heuristic    = _heuristic_decision(record, args.margin)

        item = _record_to_item(record)
        features = extract_features(item)
        model_prob = model.predict_proba(features)
        model_decision = "corrected" if model_prob > model.threshold else "original"
        model_conf = f"{model_prob:.3f}"

        h_ok = heuristic == ground_truth
        m_ok = model_decision == ground_truth

        if h_ok:
            heuristic_correct += 1
        if m_ok:
            model_correct += 1

        h_mark = "✓" if h_ok else "✗"
        m_mark = "✓" if m_ok else "✗"

        print(f"  [{i:02d}] original  : {record.get('original_text', '')!r}")
        print(f"       corrected : {record.get('corrected_text', '')!r}")
        print(f"       truth     : {ground_truth:<12}  "
              f"heuristic: {heuristic:<12} {h_mark}  "
              f"model({model_conf}): {model_decision:<12} {m_mark}")
        print()

    total = len(records)
    h_acc = heuristic_correct / total if total else 0.0
    m_acc = model_correct / total if total else 0.0

    print(f"{'─'*80}")
    print(f"  Heuristic accuracy : {h_acc:.1%}  ({heuristic_correct}/{total})")
    if model_loaded:
        delta = m_acc - h_acc
        sign  = "+" if delta >= 0 else ""
        print(f"  Model accuracy     : {m_acc:.1%}  ({model_correct}/{total})  "
              f"[{sign}{delta:.1%} vs heuristic]")
    else:
        print("  Model              : not available — run train_model.py first")
    print(f"{'═'*80}\n")


if __name__ == "__main__":
    main()
