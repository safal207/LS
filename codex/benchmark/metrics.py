from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Dict, Iterable


def stability_score(samples: Iterable[float]) -> float:
    values = [value for value in samples if value >= 0]
    if not values:
        return 0.0
    if len(values) == 1:
        return 1.0
    mean = fmean(values)
    if mean == 0:
        return 0.0
    spread = pstdev(values)
    score = max(0.0, 1.0 - (spread / mean))
    return round(score, 4)


@dataclass(frozen=True)
class LLMMetrics:
    loadtimems: float
    firsttokenlatency_ms: float
    tokenspersecond: float
    peakrammb: float
    peakvrammb: float
    stability_score: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "loadtimems": self.loadtimems,
            "firsttokenlatency_ms": self.firsttokenlatency_ms,
            "tokenspersecond": self.tokenspersecond,
            "peakrammb": self.peakrammb,
            "peakvrammb": self.peakvrammb,
            "stability_score": self.stability_score,
        }


@dataclass(frozen=True)
class STTMetrics:
    loadtimems: float
    transcriptionlatencyms: float
    realtimefactor: float
    peakrammb: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "loadtimems": self.loadtimems,
            "transcriptionlatencyms": self.transcriptionlatencyms,
            "realtimefactor": self.realtimefactor,
            "peakrammb": self.peakrammb,
        }


@dataclass(frozen=True)
class VADMetrics:
    loadtimems: float
    processinglatencyms: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "loadtimems": self.loadtimems,
            "processinglatencyms": self.processinglatencyms,
        }
