from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass
class AdaptiveGovernor:
    alpha_min: float = 0.2
    alpha_max: float = 0.5
    volatility_window: int = 100
    _window: Deque[float] = field(default_factory=deque, init=False)
    _alpha: float = field(default=0.3, init=False)
    _count: int = field(default=0, init=False)
    _mean: float = field(default=0.0, init=False)
    _m2: float = field(default=0.0, init=False)

    def compute_adaptive_alpha(self, current_throughput: float) -> float:
        self._count += 1
        delta = current_throughput - self._mean
        self._mean += delta / self._count
        delta2 = current_throughput - self._mean
        self._m2 += delta * delta2

        self._window.append(current_throughput)
        if len(self._window) > self.volatility_window:
            self._window.popleft()

        if self._count < 10:
            self._alpha = 0.3
            return self._alpha

        variance = max(0.0, self._m2 / self._count)
        volatility = math.sqrt(variance) / max(0.001, abs(self._mean))

        target_alpha = self.alpha_max - (volatility * (self.alpha_max - self.alpha_min))
        self._alpha = min(self.alpha_max, max(self.alpha_min, target_alpha))
        return self._alpha

    @property
    def alpha(self) -> float:
        return self._alpha
