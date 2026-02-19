from __future__ import annotations

from dataclasses import dataclass

try:
    import ghostgpt_core  # type: ignore
except (ImportError, ModuleNotFoundError):  # pragma: no cover - optional Rust extension
    ghostgpt_core = None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ramp_up(value: float, start: float, end: float) -> float:
    if value <= start:
        return 0.0
    if value >= end:
        return 1.0
    return (value - start) / (end - start)


def _ramp_down(value: float, start: float, end: float) -> float:
    if value <= start:
        return 1.0
    if value >= end:
        return 0.0
    return 1.0 - ((value - start) / (end - start))


@dataclass(slots=True)
class FuzzyCoherenceConfig:
    min_coherence: float = 0.0
    max_coherence: float = 1.0
    drift_threshold: float = 0.30
    noise_threshold: float = 0.08
    smoothing_gain: float = 0.12


@dataclass(slots=True)
class FuzzyBackpressureConfig:
    min_factor: float = 0.6
    max_factor: float = 1.4
    queue_pressure_threshold: float = 0.75
    drop_pressure_threshold: float = 0.20
    hysteresis_ratio: float = 0.05


def smooth_coherence(prev_coherence: float, measured_coherence: float, drift: float, noise: float, config: FuzzyCoherenceConfig | None = None) -> float:
    cfg = config or FuzzyCoherenceConfig()
    if ghostgpt_core is not None and hasattr(ghostgpt_core, "smooth_coherence"):
        rust_cfg = None
        if hasattr(ghostgpt_core, "FuzzyCoherenceConfig"):
            rust_cfg = ghostgpt_core.FuzzyCoherenceConfig(
                cfg.min_coherence,
                cfg.max_coherence,
                cfg.drift_threshold,
                cfg.noise_threshold,
                cfg.smoothing_gain,
            )
        return float(ghostgpt_core.smooth_coherence(prev_coherence, measured_coherence, drift, noise, rust_cfg))

    prev = _clamp(prev_coherence, cfg.min_coherence, cfg.max_coherence)
    measured = _clamp(measured_coherence, cfg.min_coherence, cfg.max_coherence)
    drift_level = _ramp_up(abs(drift), cfg.drift_threshold * 0.5, cfg.drift_threshold)
    noise_level = _ramp_up(abs(noise), cfg.noise_threshold * 0.5, cfg.noise_threshold)
    stable = _ramp_down((abs(drift) + abs(noise)) * 0.5, 0.0, max(cfg.noise_threshold, 0.01))
    adaptive_gain = _clamp(cfg.smoothing_gain + (0.35 * drift_level) + (0.20 * noise_level) - (0.10 * stable), 0.02, 0.95)
    return _clamp(prev + adaptive_gain * (measured - prev), cfg.min_coherence, cfg.max_coherence)


def tune_backpressure_limits(
    per_session_limit: int,
    total_limit: int,
    queue_pressure: float,
    drop_ratio: float,
    config: FuzzyBackpressureConfig | None = None,
) -> tuple[int, int]:
    cfg = config or FuzzyBackpressureConfig()
    if ghostgpt_core is not None and hasattr(ghostgpt_core, "tune_backpressure_limits"):
        rust_cfg = None
        if hasattr(ghostgpt_core, "FuzzyBackpressureConfig"):
            try:
                rust_cfg = ghostgpt_core.FuzzyBackpressureConfig(
                    cfg.min_factor,
                    cfg.max_factor,
                    cfg.queue_pressure_threshold,
                    cfg.drop_pressure_threshold,
                    cfg.hysteresis_ratio,
                )
            except TypeError:
                rust_cfg = ghostgpt_core.FuzzyBackpressureConfig(
                    cfg.min_factor,
                    cfg.max_factor,
                    cfg.queue_pressure_threshold,
                    cfg.drop_pressure_threshold,
                )
        tuned = ghostgpt_core.tune_backpressure_limits(per_session_limit, total_limit, queue_pressure, drop_ratio, rust_cfg)
        return int(tuned[0]), int(tuned[1])

    pressure = _clamp(queue_pressure, 0.0, 1.0)
    drops = _clamp(drop_ratio, 0.0, 1.0)
    high_pressure = _ramp_up(pressure, cfg.queue_pressure_threshold * 0.7, cfg.queue_pressure_threshold)
    critical_pressure = _ramp_up(pressure, cfg.queue_pressure_threshold, 1.0)
    drop_stress = _ramp_up(drops, cfg.drop_pressure_threshold, 1.0)
    stable = _ramp_down(pressure, 0.0, cfg.queue_pressure_threshold * 0.5)
    factor = _clamp(1.0 + (0.25 * stable) - (0.35 * high_pressure) - (0.45 * critical_pressure) - (0.30 * drop_stress), cfg.min_factor, cfg.max_factor)
    if abs(factor - 1.0) < max(0.0, cfg.hysteresis_ratio):
        factor = 1.0
    next_per_session = max(1, round(per_session_limit * factor))
    next_total = max(next_per_session, round(total_limit * factor))
    return next_per_session, next_total
