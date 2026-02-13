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
    session_id: u64,
    heartbeat_timeout_ms: u64,
    last_heartbeat_at: Instant,
    on_session_open: Vec<PyObject>,
    on_session_close: Vec<PyObject>,
    on_heartbeat_timeout: Vec<PyObject>,
    stats: RttStats,
}

#[pymethods]
impl Web4RttBinding {
    #[new]
    #[pyo3(signature = (max_queue, backpressure_policy=None, block_timeout_ms=100, session_id=0, heartbeat_timeout_ms=1000))]
    fn new(
        max_queue: usize,
        backpressure_policy: Option<&str>,
        block_timeout_ms: u64,
        session_id: u64,
        heartbeat_timeout_ms: u64,
    ) -> PyResult<Self> {
        Ok(Self {
            connected: true,
            queue: Vec::new(),
            max_queue: max_queue.max(1),
            policy: BackpressurePolicy::parse(backpressure_policy)?,
            block_timeout_ms,
            session_id,
            heartbeat_timeout_ms,
            last_heartbeat_at: Instant::now(),
            on_session_open: Vec::new(),
            on_session_close: Vec::new(),
            on_heartbeat_timeout: Vec::new(),
            stats: RttStats::default(),
        })
    }

    fn connect(&mut self, py: Python<'_>) -> PyResult<()> {
        if self.connected {
            return Ok(());
        }
        self.connected = true;
        self.last_heartbeat_at = Instant::now();
        self.emit(py, "session_open", &self.on_session_open, None)?;
        Ok(())
    }

    #[pyo3(signature = (reason=None))]
    fn disconnect(&mut self, py: Python<'_>, reason: Option<&str>) -> PyResult<()> {
        if !self.connected {
            return Ok(());
        }
        self.connected = false;
        self.emit(py, "session_close", &self.on_session_close, reason)?;
        Ok(())
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

    fn heartbeat(&mut self) {
        self.last_heartbeat_at = Instant::now();
    }

    fn check_heartbeat_timeout(&mut self, py: Python<'_>) -> PyResult<bool> {
        if !self.connected {
            return Ok(false);
        }
        if self.last_heartbeat_at.elapsed() < Duration::from_millis(self.heartbeat_timeout_ms) {
            return Ok(false);
        }
        self.emit(py, "heartbeat_timeout", &self.on_heartbeat_timeout, None)?;
        self.connected = false;
        self.emit(py, "session_close", &self.on_session_close, Some("heartbeat_timeout"))?;
        Ok(true)
    }

    fn register_on_session_open(&mut self, py: Python<'_>, callback: PyObject) -> PyResult<()> {
        self.on_session_open.push(callback.clone_ref(py));
        if self.connected {
            callback.call1(py, (self.session_id,))?;
        }
        Ok(())
    }

    fn register_on_session_close(&mut self, py: Python<'_>, callback: PyObject) {
        self.on_session_close.push(callback.clone_ref(py));
    }

    fn register_on_heartbeat_timeout(&mut self, py: Python<'_>, callback: PyObject) {
        self.on_heartbeat_timeout.push(callback.clone_ref(py));
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

    fn emit(
        &self,
        py: Python<'_>,
        _event_name: &str,
        callbacks: &[PyObject],
        _reason: Option<&str>,
    ) -> PyResult<()> {
        for callback in callbacks {
            callback.call1(py, (self.session_id,))?;
        }
        Ok(())
    }
}
