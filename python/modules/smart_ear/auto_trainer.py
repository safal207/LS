"""SmartEarAutoTrainer — background watchdog that retrains the model
when the dataset grows and hot-swaps the running instance.

Design:
* Runs as a daemon thread (stops when main process exits).
* Polls ``dataset_path`` every ``poll_interval`` seconds.
* Retrains when ``(current_line_count - last_trained_count) >= retrain_every``.
* Loads the new ``.pkl`` into the live ``SmartEarDecisionModel`` instance
  via ``model.load_model()`` — no restart required.
* All heavy sklearn work happens in a subprocess via ``subprocess.run`` to
  keep the main process responsive and avoid GIL contention.

Usage::

    from smart_ear.auto_trainer import SmartEarAutoTrainer

    trainer = SmartEarAutoTrainer(
        dataset_path="data/smart_ear_dataset.jsonl",
        model_path="models/smart_ear_model.pkl",
        decision_model=decision_model_instance,   # live model to hot-swap
        retrain_every=50,     # retrain after every 50 new samples
        poll_interval=30.0,   # check dataset every 30 s
    )
    trainer.start()   # non-blocking
    # ... later ...
    trainer.stop()
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_TRAIN_SCRIPT = os.path.join(os.path.dirname(__file__), "train_model.py")


def _count_lines(path: str) -> int:
    """Count non-empty lines in a file without loading it all into memory."""
    try:
        with open(path, "rb") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return 0


class SmartEarAutoTrainer:
    """Background daemon that watches the dataset and retrains the model.

    Parameters
    ----------
    dataset_path:
        Path to ``smart_ear_dataset.jsonl``.
    model_path:
        Where the trained ``.pkl`` should be saved / loaded from.
    decision_model:
        The live :class:`~smart_ear.decision_model.SmartEarDecisionModel`
        instance.  After retraining, ``load_model()`` is called on it to
        hot-swap the classifier without restarting.
    retrain_every:
        Number of *new* samples required to trigger a retrain (default 50).
    poll_interval:
        Seconds between dataset size checks (default 30).
    min_samples:
        Minimum total samples required before the first training run (default 20).
    """

    def __init__(
        self,
        dataset_path: str,
        model_path: str,
        decision_model,
        retrain_every: int = 50,
        poll_interval: float = 30.0,
        min_samples: int = 20,
    ) -> None:
        self.dataset_path = dataset_path
        self.model_path = model_path
        self._model = decision_model
        self.retrain_every = retrain_every
        self.poll_interval = poll_interval
        self.min_samples = min_samples

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_trained_count: int = 0
        self._total_retrains: int = 0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background watcher thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="SmartEarAutoTrainer",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "SmartEarAutoTrainer started (retrain_every=%d, poll=%.0fs)",
            self.retrain_every,
            self.poll_interval,
        )

    def stop(self) -> None:
        """Signal the watcher to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def total_retrains(self) -> int:
        return self._total_retrains

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_and_retrain()
            except Exception as exc:
                logger.error("SmartEarAutoTrainer error: %s", exc, exc_info=True)
            self._stop_event.wait(timeout=self.poll_interval)

    def _check_and_retrain(self) -> None:
        if not os.path.exists(self.dataset_path):
            return

        current = _count_lines(self.dataset_path)
        if current < self.min_samples:
            logger.debug(
                "AutoTrainer: dataset too small (%d < %d min), skipping",
                current, self.min_samples,
            )
            return

        new_samples = current - self._last_trained_count
        if new_samples < self.retrain_every and self._last_trained_count > 0:
            logger.debug(
                "AutoTrainer: only %d new samples (need %d), skipping",
                new_samples, self.retrain_every,
            )
            return

        logger.info(
            "AutoTrainer: %d new samples → starting retrain (total=%d)",
            new_samples, current,
        )
        success = self._run_training()
        if success:
            self._last_trained_count = current
            self._total_retrains += 1
            self._hot_swap()

    def _run_training(self) -> bool:
        """Run train_model.py in a subprocess. Returns True on success."""
        cmd = [
            sys.executable,
            _TRAIN_SCRIPT,
            "--dataset", self.dataset_path,
            "--model",   self.model_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("AutoTrainer: training succeeded\n%s", result.stdout.strip())
                return True
            else:
                logger.warning(
                    "AutoTrainer: training failed (exit %d)\n%s",
                    result.returncode, result.stderr.strip(),
                )
                return False
        except subprocess.TimeoutExpired:
            logger.warning("AutoTrainer: training timed out (>120s)")
            return False
        except Exception as exc:
            logger.warning("AutoTrainer: training subprocess error: %s", exc)
            return False

    def _hot_swap(self) -> None:
        """Reload the freshly trained model into the live decision instance."""
        try:
            loaded = self._model.load_model()
            if loaded:
                logger.info(
                    "AutoTrainer: hot-swapped model (retrain #%d)",
                    self._total_retrains,
                )
            else:
                logger.warning("AutoTrainer: hot-swap failed — model file not found after training")
        except Exception as exc:
            logger.warning("AutoTrainer: hot-swap error: %s", exc)
