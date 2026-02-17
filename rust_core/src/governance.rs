use pyo3::prelude::*;
use std::collections::VecDeque;

#[pyclass]
pub struct AdaptiveGovernor {
    alpha_min: f64,
    alpha_max: f64,
    throughput_history: VecDeque<f64>,
    volatility_window: usize,
    prev_alpha: f64,
}

#[pymethods]
impl AdaptiveGovernor {
    #[new]
    #[pyo3(signature = (alpha_min=0.2, alpha_max=0.5, volatility_window=100))]
    fn new(alpha_min: f64, alpha_max: f64, volatility_window: usize) -> Self {
        Self {
            alpha_min,
            alpha_max,
            throughput_history: VecDeque::with_capacity(volatility_window),
            volatility_window,
            prev_alpha: 0.3,
        }
    }

    fn compute_adaptive_alpha(&mut self, current_throughput: f64) -> f64 {
        self.throughput_history.push_back(current_throughput);
        while self.throughput_history.len() > self.volatility_window {
            self.throughput_history.pop_front();
        }

        if self.throughput_history.len() < 10 {
            return 0.3;
        }

        let mean: f64 = self.throughput_history.iter().sum::<f64>() / self.throughput_history.len() as f64;
        let variance: f64 = self
            .throughput_history
            .iter()
            .map(|x| (x - mean).powi(2))
            .sum::<f64>()
            / self.throughput_history.len() as f64;
        let volatility = variance.sqrt() / mean.max(0.001);

        let alpha = if volatility > 0.5 {
            self.alpha_max
        } else if volatility < 0.2 {
            self.alpha_min
        } else {
            self.alpha_min + (volatility - 0.2) * (self.alpha_max - self.alpha_min) / 0.3
        };

        self.prev_alpha = alpha;
        alpha
    }

    fn get_volatility(&self) -> f64 {
        if self.throughput_history.len() < 10 {
            return 0.0;
        }
        let mean: f64 = self.throughput_history.iter().sum::<f64>() / self.throughput_history.len() as f64;
        let variance: f64 = self
            .throughput_history
            .iter()
            .map(|x| (x - mean).powi(2))
            .sum::<f64>()
            / self.throughput_history.len() as f64;
        variance.sqrt() / mean.max(0.001)
    }
}
