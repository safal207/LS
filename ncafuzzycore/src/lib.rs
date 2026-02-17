#![allow(non_local_definitions)]

use pyo3::prelude::*;

#[inline]
fn clamp(value: f32, low: f32, high: f32) -> f32 {
    value.max(low).min(high)
}

#[inline]
fn ramp_up(value: f32, start: f32, end: f32) -> f32 {
    if value <= start {
        return 0.0;
    }
    if value >= end {
        return 1.0;
    }
    (value - start) / (end - start)
}

#[inline]
fn ramp_down(value: f32, start: f32, end: f32) -> f32 {
    if value <= start {
        return 1.0;
    }
    if value >= end {
        return 0.0;
    }
    1.0 - ((value - start) / (end - start))
}

#[inline]
fn triangular(value: f32, left: f32, peak: f32, right: f32) -> f32 {
    if value <= left || value >= right {
        return 0.0;
    }
    if (value - peak).abs() <= f32::EPSILON {
        return 1.0;
    }
    if value < peak {
        return (value - left) / (peak - left);
    }
    (right - value) / (right - peak)
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct PySignalMetrics {
    #[pyo3(get, set)]
    pub queue_size: u32,
    #[pyo3(get, set)]
    pub avg_batch_size: f32,
    #[pyo3(get, set)]
    pub queue_peak_per_tick: u32,
    #[pyo3(get, set)]
    pub total_dropped: u64,
    #[pyo3(get, set)]
    pub total_emitted: u64,
}

#[pymethods]
impl PySignalMetrics {
    #[new]
    #[pyo3(signature = (queue_size, avg_batch_size, queue_peak_per_tick, total_dropped, total_emitted))]
    pub fn new(
        queue_size: u32,
        avg_batch_size: f32,
        queue_peak_per_tick: u32,
        total_dropped: u64,
        total_emitted: u64,
    ) -> Self {
        Self {
            queue_size,
            avg_batch_size,
            queue_peak_per_tick,
            total_dropped,
            total_emitted,
        }
    }
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct PyBusConfig {
    #[pyo3(get, set)]
    pub max_signals_per_tick: u32,
    #[pyo3(get, set)]
    pub max_queue_size: u32,
    #[pyo3(get, set)]
    pub priority_boost: f32,
}

#[pymethods]
impl PyBusConfig {
    #[new]
    #[pyo3(signature = (max_signals_per_tick, max_queue_size, priority_boost))]
    pub fn new(max_signals_per_tick: u32, max_queue_size: u32, priority_boost: f32) -> Self {
        Self {
            max_signals_per_tick,
            max_queue_size,
            priority_boost,
        }
    }
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct PyAdjustments {
    #[pyo3(get)]
    pub max_signals_per_tick: u32,
    #[pyo3(get)]
    pub max_queue_size: u32,
    #[pyo3(get)]
    pub priority_boost: f32,
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct PySignal {
    #[pyo3(get, set)]
    pub signal_type: String,
    #[pyo3(get, set)]
    pub priority: f32,
    #[pyo3(get, set)]
    pub payload_size: u32,
}

#[pymethods]
impl PySignal {
    #[new]
    #[pyo3(signature = (signal_type, priority, payload_size))]
    pub fn new(signal_type: String, priority: f32, payload_size: u32) -> Self {
        Self {
            signal_type,
            priority,
            payload_size,
        }
    }
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct PyBatchResult {
    #[pyo3(get)]
    pub processed_indices: Vec<usize>,
    #[pyo3(get)]
    pub dropped_count: usize,
    #[pyo3(get)]
    pub effective_batch_size: usize,
}

#[pyfunction]
pub fn compute_adjustments(metrics: PySignalMetrics, config: PyBusConfig) -> PyAdjustments {
    let queue_load = clamp(metrics.queue_size as f32 / config.max_queue_size.max(1) as f32, 0.0, 1.0);
    let batch_efficiency = clamp(
        metrics.avg_batch_size / config.max_signals_per_tick.max(1) as f32,
        0.0,
        1.0,
    );
    let burst_pressure =
        clamp(metrics.queue_peak_per_tick as f32 / config.max_queue_size.max(1) as f32, 0.0, 1.0);
    let drop_rate = clamp(
        metrics.total_dropped as f32 / metrics.total_emitted.max(1) as f32,
        0.0,
        1.0,
    );

    let queue_low = ramp_down(queue_load, 0.0, 0.3);
    let queue_high = ramp_up(queue_load, 0.6, 1.0);
    let batch_underutilized = ramp_down(batch_efficiency, 0.0, 0.4);
    let batch_optimal = triangular(batch_efficiency, 0.3, 0.55, 0.8);
    let burst_storm = ramp_up(burst_pressure, 0.6, 1.0);
    let burst_calm = ramp_down(burst_pressure, 0.0, 0.2);
    let drop_low = ramp_down(drop_rate, 0.0, 0.05);
    let drop_critical = ramp_up(drop_rate, 0.05, 1.0);

    let throughput_increase = queue_high.min(batch_optimal);
    let throughput_decrease = queue_low.min(batch_underutilized);

    let mut throughput_factor = 1.0_f32;
    throughput_factor += 0.35 * throughput_increase;
    throughput_factor -= 0.15 * throughput_decrease;
    throughput_factor -= 0.60 * drop_critical;
    throughput_factor = clamp(throughput_factor, 0.4, 1.6);

    let mut queue_factor = 1.0_f32;
    queue_factor += 0.25 * burst_storm.min(drop_low);
    queue_factor -= 0.10 * queue_low.min(burst_calm);
    queue_factor = clamp(queue_factor, 0.7, 1.4);

    let mut priority_boost = 0.1_f32;
    priority_boost += 0.20 * burst_storm.min(queue_high);
    priority_boost -= 0.10 * queue_low;
    priority_boost = clamp(priority_boost, 0.0, 0.3);

    let new_signals = ((config.max_signals_per_tick as f32) * throughput_factor).round() as u32;
    let new_queue = ((config.max_queue_size as f32) * queue_factor).round() as u32;

    PyAdjustments {
        max_signals_per_tick: new_signals.clamp(1_000, 100_000),
        max_queue_size: new_queue.clamp(10_000, 1_000_000),
        priority_boost,
    }
}

#[pyfunction]
pub fn process_batch(signals: Vec<PySignal>, config: PyBusConfig) -> PyBatchResult {
    let mut indexed: Vec<(usize, f32)> = signals
        .iter()
        .enumerate()
        .map(|(idx, signal)| (idx, signal.priority + config.priority_boost))
        .collect();
    indexed.sort_by(|a, b| b.1.total_cmp(&a.1));

    let limit = config.max_signals_per_tick as usize;
    let take_count = limit.min(indexed.len());

    PyBatchResult {
        processed_indices: indexed.iter().take(take_count).map(|(idx, _)| *idx).collect(),
        dropped_count: indexed.len().saturating_sub(take_count),
        effective_batch_size: take_count,
    }
}

#[pymodule]
fn ncafuzzycore(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PySignalMetrics>()?;
    m.add_class::<PyBusConfig>()?;
    m.add_class::<PyAdjustments>()?;
    m.add_class::<PySignal>()?;
    m.add_class::<PyBatchResult>()?;
    m.add_function(wrap_pyfunction!(compute_adjustments, m)?)?;
    m.add_function(wrap_pyfunction!(process_batch, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    #[test]
    fn high_load_increases_throughput() {
        let metrics = PySignalMetrics::new(9_000, 5_500.0, 9_500, 0, 1_000);
        let config = PyBusConfig::new(10_000, 10_000, 0.1);
        let out = compute_adjustments(metrics, config);
        assert!(out.max_signals_per_tick > 10_000);
    }

    #[test]
    fn critical_drop_reduces_throughput() {
        let metrics = PySignalMetrics::new(8_000, 7_000.0, 8_500, 300, 1_000);
        let config = PyBusConfig::new(10_000, 10_000, 0.1);
        let out = compute_adjustments(metrics, config);
        assert!(out.max_signals_per_tick < 10_000);
    }

    proptest! {
        #[test]
        fn higher_queue_load_not_lower_throughput(
            low_q in 1_000_u32..4_000_u32,
            high_q in 7_000_u32..10_000_u32,
        ) {
            let cfg = PyBusConfig::new(10_000, 10_000, 0.1);
            let low = compute_adjustments(PySignalMetrics::new(low_q, 5_500.0, low_q, 0, 1_000), cfg.clone());
            let high = compute_adjustments(PySignalMetrics::new(high_q, 5_500.0, high_q, 0, 1_000), cfg);
            prop_assert!(high.max_signals_per_tick >= low.max_signals_per_tick);
        }
    }
}
