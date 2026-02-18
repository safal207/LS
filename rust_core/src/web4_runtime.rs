use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::cmp::Ordering;
use std::collections::{BinaryHeap, VecDeque};
use std::sync::{Arc, Condvar, Mutex};
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

#[derive(Eq, PartialEq)]
struct PrioritizedMessage {
    priority: i32,
    sequence: u64,
    message: String,
}

impl Ord for PrioritizedMessage {
    fn cmp(&self, other: &Self) -> Ordering {
        self.priority
            .cmp(&other.priority)
            .then_with(|| other.sequence.cmp(&self.sequence))
    }
}

impl PartialOrd for PrioritizedMessage {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[pyclass]
pub struct Web4RttBinding {
    connected: bool,
    queue: VecDeque<String>,
    priority_queue: BinaryHeap<PrioritizedMessage>,
    next_sequence: u64,
    max_queue: usize,
    policy: BackpressurePolicy,
    block_timeout_ms: u64,
    session_id: u64,
    heartbeat_timeout_ms: u64,
    last_heartbeat_at: Instant,
    on_session_open: Vec<PyObject>,
    on_session_close: Vec<PyObject>,
    on_heartbeat_timeout: Vec<PyObject>,
    block_wait: Arc<(Mutex<()>, Condvar)>,
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
        if max_queue < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "RttConfig.max_queue must be >= 1, got {}",
                max_queue
            )));
        }
        Ok(Self {
            connected: true,
            queue: VecDeque::new(),
            priority_queue: BinaryHeap::new(),
            next_sequence: 0,
            max_queue,
            policy: BackpressurePolicy::parse(backpressure_policy)?,
            block_timeout_ms,
            session_id,
            heartbeat_timeout_ms,
            last_heartbeat_at: Instant::now(),
            on_session_open: Vec::new(),
            on_session_close: Vec::new(),
            on_heartbeat_timeout: Vec::new(),
            block_wait: Arc::new((Mutex::new(()), Condvar::new())),
            stats: RttStats::default(),
        })
    }

    fn connect(&mut self, py: Python<'_>) -> PyResult<()> {
        if self.connected {
            return Ok(());
        }
        self.connected = true;
        self.last_heartbeat_at = Instant::now();
        self.notify_block_waiters();
        self.emit(py, &self.on_session_open)?;
        Ok(())
    }

    #[pyo3(signature = (reason=None))]
    fn disconnect(&mut self, py: Python<'_>, reason: Option<&str>) -> PyResult<()> {
        if !self.connected {
            return Ok(());
        }
        self.connected = false;
        let _ = reason;
        self.notify_block_waiters();
        self.emit(py, &self.on_session_close)?;
        Ok(())
    }

    #[pyo3(signature = (message, priority=None))]
    fn send(&mut self, py: Python<'_>, message: String, priority: Option<i32>) -> PyResult<()> {
        if !self.connected {
            self.stats.errors += 1;
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "RTT binding disconnected",
            ));
        }
        self.stats.attempted += 1;

        if self.pending() >= self.max_queue {
            self.stats.overflow_events += 1;
            match self.policy {
                BackpressurePolicy::DropOldest => {
                    if !self.priority_queue.is_empty() {
                        // TODO(14.7): Replace full-heap rebuild with lazy deletion + auxiliary
                        // min-sequence structure for O(log n) dropoldest parity.
                        if let Some(oldest_sequence) =
                            self.priority_queue.iter().map(|pm| pm.sequence).min()
                        {
                            self.priority_queue = self
                                .priority_queue
                                .drain()
                                .filter(|pm| pm.sequence != oldest_sequence)
                                .collect();
                        }
                    } else {
                        let _ = self.queue.pop_front();
                    }
                    self.push_message(message, priority);
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
                    while self.pending() >= self.max_queue && self.connected {
                        let now = Instant::now();
                        if now >= deadline {
                            self.stats.errors += 1;
                            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                                "RTT binding backpressure: block timeout",
                            ));
                        }
                        let remaining = deadline.saturating_duration_since(now);
                        let block_wait = Arc::clone(&self.block_wait);
                        let timed_out = py.allow_threads(move || {
                            let (lock, cvar) = &*block_wait;
                            let guard = match lock.lock() {
                                Ok(guard) => guard,
                                Err(poisoned) => poisoned.into_inner(),
                            };
                            let (_guard, wait_state) = match cvar.wait_timeout(guard, remaining) {
                                Ok(result) => result,
                                Err(poisoned) => poisoned.into_inner(),
                            };
                            wait_state.timed_out()
                        });
                        if timed_out && self.pending() >= self.max_queue {
                            self.stats.errors += 1;
                            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                                "RTT binding backpressure: block timeout",
                            ));
                        }
                    }
                    if !self.connected {
                        self.stats.errors += 1;
                        return Err(pyo3::exceptions::PyRuntimeError::new_err(
                            "RTT binding disconnected",
                        ));
                    }
                    self.push_message(message, priority);
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

        self.push_message(message, priority);
        self.stats.enqueued += 1;
        self.update_max_queue_len();
        Ok(())
    }

    fn receive(&mut self) -> Option<String> {
        if !self.connected {
            return None;
        }
        let item = if !self.priority_queue.is_empty() {
            self.priority_queue.pop().map(|pm| pm.message)
        } else {
            self.queue.pop_front()
        };
        if item.is_some() {
            self.notify_block_waiters();
        }
        item
    }

    fn pending(&self) -> usize {
        self.queue.len() + self.priority_queue.len()
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
        self.emit(py, &self.on_heartbeat_timeout)?;
        self.connected = false;
        self.notify_block_waiters();
        self.emit(py, &self.on_session_close)?;
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
        let _ = stats.set_item(
            "dropped",
            self.stats.dropped_oldest + self.stats.dropped_newest,
        );
        let _ = stats.set_item("blocked", self.stats.blocked);
        let _ = stats.set_item("errors", self.stats.errors);
        let _ = stats.set_item("overflow_events", self.stats.overflow_events);
        let _ = stats.set_item("max_queue_len", self.stats.max_queue_len);
        stats
    }
}

impl Web4RttBinding {
    fn update_max_queue_len(&mut self) {
        self.stats.max_queue_len = self
            .stats
            .max_queue_len
            .max(self.queue.len() + self.priority_queue.len());
    }

    fn push_message(&mut self, message: String, priority: Option<i32>) {
        if let Some(priority_value) = priority {
            self.next_sequence = self.next_sequence.wrapping_add(1);
            self.priority_queue.push(PrioritizedMessage {
                priority: priority_value,
                sequence: self.next_sequence,
                message,
            });
            return;
        }
        self.queue.push_back(message);
    }

    fn emit(&self, py: Python<'_>, callbacks: &[PyObject]) -> PyResult<()> {
        let callbacks: Vec<PyObject> = callbacks.iter().map(|c| c.clone_ref(py)).collect();
        for callback in callbacks {
            callback.call1(py, (self.session_id,))?;
        }
        Ok(())
    }

    fn notify_block_waiters(&self) {
        let (_lock, cvar) = &*self.block_wait;
        cvar.notify_all();
    }
}
