from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


class PriceEngineError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PriceInput:
    base_price_ct: Decimal
    reputation_score: float
    demand_index: float
    confidence_calibrated: float
    risk_discount: float = 1.0


@dataclass(frozen=True)
class PriceQuote:
    price_ct: Decimal
    suggested_resonance_band_min: Decimal
    suggested_resonance_band_max: Decimal


class PriceEngine:
    """Sprint 5 baseline price engine from docs formula."""

    def __init__(self, alpha: float = 0.4, beta: float = 0.2, gamma: float = 0.3, band_pct: float = 0.15) -> None:
        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma
        self._band_pct = band_pct

    def quote(self, inp: PriceInput) -> PriceQuote:
        if inp.base_price_ct <= 0:
            raise PriceEngineError("INVALID_BASE_PRICE", "base_price_ct must be > 0")
        if not 0 <= inp.reputation_score <= 1:
            raise PriceEngineError("INVALID_REPUTATION", "reputation_score must be in [0,1]")
        if inp.demand_index < 0:
            raise PriceEngineError("INVALID_DEMAND", "demand_index must be >= 0")
        if not 0 <= inp.confidence_calibrated <= 1:
            raise PriceEngineError("INVALID_CONFIDENCE", "confidence_calibrated must be in [0,1]")
        if inp.risk_discount <= 0:
            raise PriceEngineError("INVALID_RISK_DISCOUNT", "risk_discount must be > 0")

        factor = Decimal("1")
        factor *= Decimal(str(1 + self._alpha * inp.reputation_score))
        factor *= Decimal(str(1 + self._beta * inp.demand_index))
        factor *= Decimal(str(1 + self._gamma * inp.confidence_calibrated))
        factor *= Decimal(str(inp.risk_discount))

        price = (inp.base_price_ct * factor).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        band_min = (price * Decimal(str(1 - self._band_pct))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        band_max = (price * Decimal(str(1 + self._band_pct))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        return PriceQuote(price_ct=price, suggested_resonance_band_min=band_min, suggested_resonance_band_max=band_max)
