"""smart_ear ML sub-package.

Provides a learned decision layer that replaces the hand-crafted heuristic
in SmartEar's SelectionStage.

Sub-modules:
* ``features``        — pure feature extractor (no side-effects)
* ``decision_model``  — load/predict wrapper with heuristic fallback
* ``train_model``     — offline training script (run as __main__)
"""
