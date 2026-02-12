use pyo3::prelude::*;
use pyo3::types::PyDict;

#[derive(Clone, Copy)]
enum BackpressurePolicy {
    DropOldest,
    DropNewest,
    Block,
    Error,
}

impl BackpressurePolicy {
    fn parse(value: Option<&str>) -> PyResult<Self> {
        match value.unwrap_or("error").to_ascii_lowercase().as_str() {
            "dropoldest" => Ok(Self::DropOldest),
            "dropnewest" => Ok(Self::DropNewest),
            "block" => Ok(Self::Block),
            "error" => Ok(Self::Error),
            other => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown backpressure policy: {other}"
            ))),
        }
    }
}

#[derive(Default)]
struct RttStats {
    attempted: usize,
    accepted: usize,
    dropped_oldest: usize,
    dropped_newest: usize,
    blocked: usize,
    errors: usize,
}

#[pyclass]
pub struct Web4RttBinding {
    connected: bool,
    queue: Vec<String>,
    max_queue: usize,
    policy: BackpressurePolicy,
    stats: RttStats,
}

#[pymethods]
impl Web4RttBinding {
    #[new]
    #[pyo3(signature = (max_queue, backpressure_policy=None))]
    fn new(max_queue: usize, backpressure_policy: Option<&str>) -> PyResult<Self> {
        Ok(Self {
            connected: true,
            queue: Vec::new(),
            max_queue: max_queue.max(1),
            policy: BackpressurePolicy::parse(backpressure_policy)?,
            stats: RttStats::default(),
        })
    }

    fn connect(&mut self) {
        self.connected = true;
    }

    fn disconnect(&mut self) {
        self.connected = false;
    }

    fn send(&mut self, message: String) -> PyResult<()> {
        if !self.connected {
            self.stats.errors += 1;
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "RTT binding disconnected",
            ));
        }
        self.stats.attempted += 1;

        if self.queue.len() >= self.max_queue {
            match self.policy {
                BackpressurePolicy::DropOldest => {
                    self.queue.remove(0);
                    self.queue.push(message);
                    self.stats.accepted += 1;
                    self.stats.dropped_oldest += 1;
                    return Ok(());
                }
                BackpressurePolicy::DropNewest => {
                    self.stats.dropped_newest += 1;
                    return Ok(());
                }
                BackpressurePolicy::Block => {
                    self.stats.blocked += 1;
                    self.stats.errors += 1;
                    return Err(pyo3::exceptions::PyRuntimeError::new_err(
                        "RTT binding backpressure: would block",
                    ));
                }
                BackpressurePolicy::Error => {
                    self.stats.errors += 1;
                    return Err(pyo3::exceptions::PyRuntimeError::new_err(
                        "RTT binding backpressure",
                    ));
                }
            }
        }

        self.queue.push(message);
        self.stats.accepted += 1;
        Ok(())
    }

    fn receive(&mut self) -> Option<String> {
        if !self.connected {
            return None;
        }
        if self.queue.is_empty() {
            return None;
        }
        Some(self.queue.remove(0))
    }

    fn pending(&self) -> usize {
        self.queue.len()
    }

    fn stats<'py>(&self, py: Python<'py>) -> &'py PyDict {
        let stats = PyDict::new(py);
        let _ = stats.set_item("attempted", self.stats.attempted);
        let _ = stats.set_item("accepted", self.stats.accepted);
        let _ = stats.set_item("dropped_oldest", self.stats.dropped_oldest);
        let _ = stats.set_item("dropped_newest", self.stats.dropped_newest);
        let _ = stats.set_item("blocked", self.stats.blocked);
        let _ = stats.set_item("errors", self.stats.errors);
        stats
    }
}
