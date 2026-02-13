use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::thread;
use std::time::{Duration, Instant};

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
    enqueued: usize,
    dropped_oldest: usize,
    dropped_newest: usize,
    blocked: usize,
    errors: usize,
    overflow_events: usize,
    max_queue_len: usize,
}

#[pyclass]
pub struct Web4RttBinding {
    connected: bool,
    queue: Vec<String>,
    max_queue: usize,
    policy: BackpressurePolicy,
    block_timeout_ms: u64,
    stats: RttStats,
}

#[pymethods]
impl Web4RttBinding {
    #[new]
    #[pyo3(signature = (max_queue, backpressure_policy=None, block_timeout_ms=100))]
    fn new(
        max_queue: usize,
        backpressure_policy: Option<&str>,
        block_timeout_ms: u64,
    ) -> PyResult<Self> {
        Ok(Self {
            connected: true,
            queue: Vec::new(),
            max_queue: max_queue.max(1),
            policy: BackpressurePolicy::parse(backpressure_policy)?,
            block_timeout_ms,
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
            self.stats.overflow_events += 1;
            match self.policy {
                BackpressurePolicy::DropOldest => {
                    self.queue.remove(0);
                    self.queue.push(message);
                    self.stats.enqueued += 1;
                    self.stats.dropped_oldest += 1;
                    self.update_max_queue_len();
                    return Ok(());
                }
                BackpressurePolicy::DropNewest => {
                    self.stats.dropped_newest += 1;
                    return Ok(());
                }
                BackpressurePolicy::Block => {
                    self.stats.blocked += 1;
                    let deadline = Instant::now() + Duration::from_millis(self.block_timeout_ms);
                    while self.queue.len() >= self.max_queue && self.connected {
                        if Instant::now() >= deadline {
                            self.stats.errors += 1;
                            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                                "RTT binding backpressure: block timeout",
                            ));
                        }
                        thread::sleep(Duration::from_millis(1));
                    }
                    if !self.connected {
                        self.stats.errors += 1;
                        return Err(pyo3::exceptions::PyRuntimeError::new_err(
                            "RTT binding disconnected",
                        ));
                    }
                    self.queue.push(message);
                    self.stats.enqueued += 1;
                    self.update_max_queue_len();
                    return Ok(());
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
        self.stats.enqueued += 1;
        self.update_max_queue_len();
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
        let _ = stats.set_item("enqueued", self.stats.enqueued);
        let _ = stats.set_item("accepted", self.stats.enqueued);
        let _ = stats.set_item("dropped_oldest", self.stats.dropped_oldest);
        let _ = stats.set_item("dropped_newest", self.stats.dropped_newest);
        let _ = stats.set_item("dropped", self.stats.dropped_oldest + self.stats.dropped_newest);
        let _ = stats.set_item("blocked", self.stats.blocked);
        let _ = stats.set_item("errors", self.stats.errors);
        let _ = stats.set_item("overflow_events", self.stats.overflow_events);
        let _ = stats.set_item("max_queue_len", self.stats.max_queue_len);
        stats
    }
}

impl Web4RttBinding {
    fn update_max_queue_len(&mut self) {
        self.stats.max_queue_len = self.stats.max_queue_len.max(self.queue.len());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn qos_dropoldest() {
        let mut rtt = Web4RttBinding::new(2, Some("dropoldest"), 10).unwrap();
        rtt.send("a".into()).unwrap();
        rtt.send("b".into()).unwrap();
        rtt.send("c".into()).unwrap();

        assert_eq!(rtt.receive().as_deref(), Some("b"));
        assert_eq!(rtt.receive().as_deref(), Some("c"));
        assert_eq!(rtt.stats.dropped_oldest, 1);
        assert_eq!(rtt.stats.overflow_events, 1);
    }

    #[test]
    fn qos_dropnewest() {
        let mut rtt = Web4RttBinding::new(1, Some("dropnewest"), 10).unwrap();
        rtt.send("a".into()).unwrap();
        rtt.send("b".into()).unwrap();

        assert_eq!(rtt.receive().as_deref(), Some("a"));
        assert_eq!(rtt.receive(), None);
        assert_eq!(rtt.stats.dropped_newest, 1);
    }

    #[test]
    fn qos_block_and_stats() {
        let mut rtt = Web4RttBinding::new(1, Some("block"), 5).unwrap();
        rtt.send("a".into()).unwrap();
        let err = rtt.send("b".into()).err();

        assert!(err.is_some());
        assert_eq!(rtt.stats.blocked, 1);
        assert_eq!(rtt.stats.errors, 1);
        assert_eq!(rtt.stats.overflow_events, 1);
        assert!(rtt.stats.max_queue_len >= 1);
    }
}
