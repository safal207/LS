# -*- coding: utf-8 -*-
"""Background resonance admission policy for the omni worker.

Controls *when* a background ResonanceKnowledgeUnit is allowed to be
persisted to the memory store.  The gate is the single place that answers
the question: "is this insight worth keeping?".

Rules applied in order (first rejection wins):

1. **Resonance threshold** — provider-aware: fallback observations need a
   stricter bar than realtime/dashscope insights.
2. **Alignment threshold** — global floor for alignment_score.
3. **Rate cap** — at most N writes per rolling time window; prevents the
   background loop from flooding the store with low-value repetition.

Usage::

    from omni.admission import ResonanceAdmissionPolicy, ResonanceAdmissionGate

    gate = ResonanceAdmissionGate(ResonanceAdmissionPolicy(
        min_resonance_score=0.3,
        fallback_min_resonance_score=0.5,
        max_writes_per_window=8,
        window_seconds=60.0,
    ))

    decision = gate.admit(unit)
    if decision.allowed:
        store.store_resonance_unit(unit)
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any

# Avoid a hard import of ResonanceKnowledgeUnit to keep admission.py usable
# with any duck-typed unit object.  The only attributes accessed are:
#   unit.resonance_score   float
#   unit.alignment_score   float
#   unit.metadata          dict  (optional — may be absent)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

_FALLBACK_PROVIDERS: frozenset[str] = frozenset({"fallback", "mvp_fallback"})
_TRUSTED_PROVIDERS: frozenset[str] = frozenset({"dashscope", "dashscope_realtime"})


@dataclass
class ResonanceAdmissionPolicy:
    """Configurable admission rules for background resonance units.

    Attributes:
        min_resonance_score:
            Minimum resonance_score for units from *trusted* providers
            (dashscope / dashscope_realtime).  Default: 0.3.
        fallback_min_resonance_score:
            Stricter threshold applied when the unit originated from the
            fallback (screen-unavailable / no-realtime) provider.
            Default: 0.5 — fallback observations are noisy.
        min_alignment_score:
            Global minimum alignment_score.  0.0 disables this check.
            Default: 0.0.
        max_writes_per_window:
            Maximum number of units that may be stored within
            ``window_seconds``.  Prevents store flooding during long idle
            sessions.  Default: 10.
        window_seconds:
            Rolling time window (in seconds) used for the rate cap.
            Default: 60.0.
        trusted_providers:
            Provider strings considered high-quality.  Units from these
            sources use ``min_resonance_score``.
        fallback_providers:
            Provider strings considered noisy.  Units from these sources
            use ``fallback_min_resonance_score``.
    """

    min_resonance_score: float = 0.3
    fallback_min_resonance_score: float = 0.5
    min_alignment_score: float = 0.0
    max_writes_per_window: int = 10
    window_seconds: float = 60.0
    trusted_providers: frozenset[str] = field(default_factory=lambda: frozenset(_TRUSTED_PROVIDERS))
    fallback_providers: frozenset[str] = field(default_factory=lambda: frozenset(_FALLBACK_PROVIDERS))

    def effective_resonance_threshold(self, provider: str) -> float:
        """Return the resonance threshold appropriate for *provider*."""
        if provider in self.fallback_providers:
            return self.fallback_min_resonance_score
        return self.min_resonance_score


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdmissionDecision:
    """Outcome of a single gate check."""

    allowed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.allowed


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


class ResonanceAdmissionGate:
    """Thread-safe admission gate that applies a :class:`ResonanceAdmissionPolicy`.

    The gate is stateful: it tracks the timestamps of recent writes so it can
    enforce the rolling rate cap.  A single gate instance should be shared
    across all threads that write to the same store.

    ``admit(unit)`` both checks **and** records the write atomically under a
    lock — callers do not need a separate "record" step.
    """

    def __init__(self, policy: ResonanceAdmissionPolicy | None = None) -> None:
        self._policy = policy or ResonanceAdmissionPolicy()
        self._lock = threading.Lock()
        # Rolling deque of write timestamps (float seconds since epoch).
        self._write_times: deque[float] = deque()

    @property
    def policy(self) -> ResonanceAdmissionPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def admit(self, unit: Any) -> AdmissionDecision:
        """Check *unit* against the policy and record the write if allowed.

        This method is thread-safe.  If the decision is ``allowed=True`` the
        write timestamp is registered atomically so the rate window is always
        accurate.

        Args:
            unit: Any object with ``resonance_score``, ``alignment_score``
                  and optionally ``metadata`` attributes.

        Returns:
            An :class:`AdmissionDecision`.
        """
        import time

        resonance = float(getattr(unit, "resonance_score", 0.0) or 0.0)
        alignment = float(getattr(unit, "alignment_score", 0.0) or 0.0)
        metadata: dict[str, Any] = dict(getattr(unit, "metadata", None) or {})
        provider = str(metadata.get("provider", "") or "")

        with self._lock:
            now = time.monotonic()
            self._evict_expired(now)

            # --- resonance check ---
            threshold = self._policy.effective_resonance_threshold(provider)
            if resonance < threshold:
                return AdmissionDecision(
                    allowed=False,
                    reason=(
                        f"resonance {resonance:.3f} < threshold {threshold:.3f}"
                        f" (provider={provider!r})"
                    ),
                )

            # --- alignment check ---
            if self._policy.min_alignment_score > 0.0 and alignment < self._policy.min_alignment_score:
                return AdmissionDecision(
                    allowed=False,
                    reason=(
                        f"alignment {alignment:.3f} < min_alignment_score"
                        f" {self._policy.min_alignment_score:.3f}"
                    ),
                )

            # --- rate cap check ---
            if len(self._write_times) >= self._policy.max_writes_per_window:
                return AdmissionDecision(
                    allowed=False,
                    reason=(
                        f"rate cap: {len(self._write_times)} writes already"
                        f" in the last {self._policy.window_seconds:.0f}s window"
                    ),
                )

            # All checks passed — record the write.
            self._write_times.append(now)
            return AdmissionDecision(allowed=True, reason="ok")

    def pending_writes_in_window(self) -> int:
        """Return the number of writes recorded in the current window.

        Thread-safe snapshot — useful for observability / tests.
        """
        import time

        with self._lock:
            self._evict_expired(time.monotonic())
            return len(self._write_times)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_expired(self, now: float) -> None:
        """Remove timestamps older than the rolling window.

        Must be called with ``self._lock`` held.
        """
        cutoff = now - self._policy.window_seconds
        while self._write_times and self._write_times[0] <= cutoff:
            self._write_times.popleft()
