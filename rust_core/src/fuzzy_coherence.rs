use pyo3::prelude::*;

#[inline]
fn clamp(value: f64, low: f64, high: f64) -> f64 {
    value.max(low).min(high)
}

#[inline]
fn ramp_up(value: f64, start: f64, end: f64) -> f64 {
    if value <= start {
        return 0.0;
    }
    if value >= end {
        return 1.0;
    }
    (value - start) / (end - start)
}

#[inline]
fn ramp_down(value: f64, start: f64, end: f64) -> f64 {
    if value <= start {
        return 1.0;
    }
    if value >= end {
        return 0.0;
    }
    1.0 - ((value - start) / (end - start))
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct FuzzyCoherenceConfig {
    #[pyo3(get, set)]
    pub min_coherence: f64,
    #[pyo3(get, set)]
    pub max_coherence: f64,
    #[pyo3(get, set)]
    pub drift_threshold: f64,
    #[pyo3(get, set)]
    pub noise_threshold: f64,
    #[pyo3(get, set)]
    pub smoothing_gain: f64,
}

impl Default for FuzzyCoherenceConfig {
    fn default() -> Self {
        Self {
            min_coherence: 0.0,
            max_coherence: 1.0,
            drift_threshold: 0.30,
            noise_threshold: 0.08,
            smoothing_gain: 0.12,
        }
    }
}

#[pymethods]
impl FuzzyCoherenceConfig {
    #[new]
    #[pyo3(signature=(min_coherence=0.0, max_coherence=1.0, drift_threshold=0.30, noise_threshold=0.08, smoothing_gain=0.12))]
    fn new(
        min_coherence: f64,
        max_coherence: f64,
        drift_threshold: f64,
        noise_threshold: f64,
        smoothing_gain: f64,
    ) -> Self {
        Self {
            min_coherence,
            max_coherence,
            drift_threshold,
            noise_threshold,
            smoothing_gain,
        }
    }
}

#[pyfunction]
#[pyo3(signature = (prev_coherence, measured_coherence, drift, noise, config=None))]
pub fn smooth_coherence(
    prev_coherence: f64,
    measured_coherence: f64,
    drift: f64,
    noise: f64,
    config: Option<FuzzyCoherenceConfig>,
) -> f64 {
    let cfg = config.unwrap_or_default();
    let prev = clamp(prev_coherence, cfg.min_coherence, cfg.max_coherence);
    let measured = clamp(measured_coherence, cfg.min_coherence, cfg.max_coherence);

    let drift_level = ramp_up(drift.abs(), cfg.drift_threshold * 0.5, cfg.drift_threshold);
    let noise_level = ramp_up(noise.abs(), cfg.noise_threshold * 0.5, cfg.noise_threshold);
    let stable = ramp_down((drift.abs() + noise.abs()) * 0.5, 0.0, cfg.noise_threshold.max(0.01));

    let adaptive_gain = clamp(
        cfg.smoothing_gain + 0.35 * drift_level + 0.20 * noise_level - 0.10 * stable,
        0.02,
        0.95,
    );

    let next = prev + adaptive_gain * (measured - prev);
    clamp(next, cfg.min_coherence, cfg.max_coherence)
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct FuzzyBackpressureConfig {
    #[pyo3(get, set)]
    pub min_factor: f64,
    #[pyo3(get, set)]
    pub max_factor: f64,
    #[pyo3(get, set)]
    pub queue_pressure_threshold: f64,
    #[pyo3(get, set)]
    pub drop_pressure_threshold: f64,
}

impl Default for FuzzyBackpressureConfig {
    fn default() -> Self {
        Self {
            min_factor: 0.6,
            max_factor: 1.4,
            queue_pressure_threshold: 0.75,
            drop_pressure_threshold: 0.20,
        }
    }
}

#[pymethods]
impl FuzzyBackpressureConfig {
    #[new]
    #[pyo3(signature=(min_factor=0.6, max_factor=1.4, queue_pressure_threshold=0.75, drop_pressure_threshold=0.20))]
    fn new(
        min_factor: f64,
        max_factor: f64,
        queue_pressure_threshold: f64,
        drop_pressure_threshold: f64,
    ) -> Self {
        Self {
            min_factor,
            max_factor,
            queue_pressure_threshold,
            drop_pressure_threshold,
        }
    }
}

#[pyfunction]
#[pyo3(signature = (per_session_limit, total_limit, queue_pressure, drop_ratio, config=None))]
pub fn tune_backpressure_limits(
    per_session_limit: usize,
    total_limit: usize,
    queue_pressure: f64,
    drop_ratio: f64,
    config: Option<FuzzyBackpressureConfig>,
) -> (usize, usize) {
    let cfg = config.unwrap_or_default();
    let pressure = clamp(queue_pressure, 0.0, 1.0);
    let drops = clamp(drop_ratio, 0.0, 1.0);

    let high_pressure = ramp_up(pressure, cfg.queue_pressure_threshold * 0.7, cfg.queue_pressure_threshold);
    let critical_pressure = ramp_up(pressure, cfg.queue_pressure_threshold, 1.0);
    let drop_stress = ramp_up(drops, cfg.drop_pressure_threshold, 1.0);
    let stable = ramp_down(pressure, 0.0, cfg.queue_pressure_threshold * 0.5);

    let factor = clamp(
        1.0 + (0.25 * stable) - (0.35 * high_pressure) - (0.45 * critical_pressure) - (0.30 * drop_stress),
        cfg.min_factor,
        cfg.max_factor,
    );

    let next_per_session = ((per_session_limit as f64) * factor).round().max(1.0) as usize;
    let next_total = ((total_limit as f64) * factor).round().max(next_per_session as f64) as usize;
    (next_per_session, next_total)
}
