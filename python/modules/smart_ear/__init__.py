"""smart_ear ML sub-package.

Provides a learned decision layer that replaces the hand-crafted heuristic
in SmartEar's SelectionStage.

Sub-modules:
* ``features``        — pure feature extractor (no side-effects)
* ``decision_model``  — load/predict/zone wrapper with heuristic fallback
* ``train_model``     — offline training script (run as __main__)
* ``auto_trainer``    — background watchdog: watches dataset, retrains on growth
* ``metrics``         — rolling metrics tracker + drift detection
"""
