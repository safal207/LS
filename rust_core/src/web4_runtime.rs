use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::cmp::{Ordering, Reverse};
use std::collections::{BinaryHeap, HashSet, VecDeque};
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant};

const PRIORITY_QUEUE_COMPACTION_RATIO: usize = 2;

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

struct Web4RttBindingInner {
    connected: bool,
    queue: VecDeque<String>,
    priority_queue: BinaryHeap<PrioritizedMessage>,
    oldest_priority_queue: BinaryHeap<Reverse<u64>>,
    live_priority_sequences: HashSet<u64>,
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

#[pyclass]
pub struct Web4RttBinding {
    inner: Arc<Mutex<Web4RttBindingInner>>,
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
            inner: Arc::new(Mutex::new(Web4RttBindingInner {
                connected: true,
                queue: VecDeque::new(),
                priority_queue: BinaryHeap::new(),
                oldest_priority_queue: BinaryHeap::new(),
                live_priority_sequences: HashSet::new(),
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
            })),
        })
    }

    fn connect(&self, py: Python<'_>) -> PyResult<()> {
        let callbacks;
        {
            let mut inner = self
                .inner
                .lock()
                .map_err(|_| PyRuntimeError::new_err("inner lock poisoned"))?;
            if inner.connected {
                return Ok(());
            }
            inner.connected = true;
            inner.last_heartbeat_at = Instant::now();
            inner.notify_block_waiters();
            callbacks = inner
                .on_session_open
                .iter()
                .map(|c| c.clone_ref(py))
                .collect::<Vec<_>>();
        }
        Web4RttBindingInner::emit(py, &callbacks, self.session_id()?)
    }

    #[pyo3(signature = (reason=None))]
    fn disconnect(&self, py: Python<'_>, reason: Option<&str>) -> PyResult<()> {
        let _ = reason;
        let callbacks;
        {
            let mut inner = self
                .inner
                .lock()
                .map_err(|_| PyRuntimeError::new_err("inner lock poisoned"))?;
            if !inner.connected {
                return Ok(());
            }
            inner.connected = false;
            inner.notify_block_waiters();
            callbacks = inner
                .on_session_close
                .iter()
                .map(|c| c.clone_ref(py))
                .collect::<Vec<_>>();
        }
        Web4RttBindingInner::emit(py, &callbacks, self.session_id()?)
    }

    #[pyo3(signature = (message, priority=None))]
    fn send(&self, py: Python<'_>, message: String, priority: Option<i32>) -> PyResult<()> {
        let mut message_slot = Some(message);
        let mut block_deadline: Option<Instant> = None;
        let mut block_counted = false;

        {
            let mut inner = self
                .inner
                .lock()
                .map_err(|_| PyRuntimeError::new_err("inner lock poisoned"))?;
            if !inner.connected {
                inner.stats.errors += 1;
                return Err(PyRuntimeError::new_err("RTT binding disconnected"));
            }
            inner.stats.attempted += 1;
        }

        loop {
            let mut inner = self
                .inner
                .lock()
                .map_err(|_| PyRuntimeError::new_err("inner lock poisoned"))?;

            if !inner.connected {
                inner.stats.errors += 1;
                return Err(PyRuntimeError::new_err("RTT binding disconnected"));
            }

            if inner.pending() < inner.max_queue {
                let msg = message_slot
                    .take()
                    .expect("message must be available until enqueue");
                inner.push_message(msg, priority);
                inner.stats.enqueued += 1;
                inner.update_max_queue_len();
                return Ok(());
            }

            inner.stats.overflow_events += 1;
            match inner.policy {
                BackpressurePolicy::DropOldest => {
                    let mut dropped = false;

                    if !inner.live_priority_sequences.is_empty() {
                        while let Some(Reverse(oldest_sequence)) = inner.oldest_priority_queue.pop()
                        {
                            if inner.live_priority_sequences.remove(&oldest_sequence) {
                                dropped = true;
                                break;
                            }
                        }

                        if dropped {
                            inner.maybe_compact_priority_structures();
                        }
                    }

                    if !dropped {
                        dropped = inner.queue.pop_front().is_some();
                    }

                    if dropped {
                        let msg = message_slot
                            .take()
                            .expect("message must be available until enqueue");
                        inner.push_message(msg, priority);
                        inner.stats.enqueued += 1;
                        inner.stats.dropped_oldest += 1;
                        inner.update_max_queue_len();
                    } else {
                        inner.stats.dropped_newest += 1;
                    }
                    return Ok(());
                }
                BackpressurePolicy::DropNewest => {
                    inner.stats.dropped_newest += 1;
                    return Ok(());
                }
                BackpressurePolicy::Block => {
                    if !block_counted {
                        inner.stats.blocked += 1;
                        block_counted = true;
                    }

                    let deadline = match block_deadline {
                        Some(existing) => existing,
                        None => {
                            let created =
                                Instant::now() + Duration::from_millis(inner.block_timeout_ms);
                            block_deadline = Some(created);
                            created
                        }
                    };

                    let now = Instant::now();
                    if now >= deadline {
                        inner.stats.errors += 1;
                        return Err(PyRuntimeError::new_err(
                            "RTT binding backpressure: block timeout",
                        ));
                    }

                    let remaining = deadline.saturating_duration_since(now);
                    let block_wait = Arc::clone(&inner.block_wait);
                    drop(inner);

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

                    if timed_out {
                        let mut inner = self
                            .inner
                            .lock()
                            .map_err(|_| PyRuntimeError::new_err("inner lock poisoned"))?;
                        if inner.pending() >= inner.max_queue {
                            inner.stats.errors += 1;
                            return Err(PyRuntimeError::new_err(
                                "RTT binding backpressure: block timeout",
                            ));
                        }
                    }
                }
                BackpressurePolicy::Error => {
                    inner.stats.errors += 1;
                    return Err(PyRuntimeError::new_err("RTT binding backpressure"));
                }
            }
        }
    }

    fn receive(&self) -> Option<String> {
        let mut inner = self.inner.lock().ok()?;
        if !inner.connected {
            return None;
        }
        let item = if !inner.priority_queue.is_empty() {
            let mut priority_item = None;
            while let Some(pm) = inner.priority_queue.pop() {
                if inner.live_priority_sequences.remove(&pm.sequence) {
                    priority_item = Some(pm.message);
                    break;
                }
            }
            if priority_item.is_some() {
                inner.maybe_compact_priority_structures();
            }
            priority_item.or_else(|| inner.queue.pop_front())
        } else {
            inner.queue.pop_front()
        };
        if item.is_some() {
            inner.notify_block_waiters();
        }
        item
    }

    fn pending(&self) -> usize {
        match self.inner.lock() {
            Ok(inner) => inner.pending(),
            Err(_) => 0,
        }
    }

    fn heartbeat(&self) {
        if let Ok(mut inner) = self.inner.lock() {
            inner.last_heartbeat_at = Instant::now();
        }
    }

    fn check_heartbeat_timeout(&self, py: Python<'_>) -> PyResult<bool> {
        let (timed_out, timeout_callbacks, close_callbacks, session_id) = {
            let mut inner = self
                .inner
                .lock()
                .map_err(|_| PyRuntimeError::new_err("inner lock poisoned"))?;
            if !inner.connected {
                return Ok(false);
            }
            if inner.last_heartbeat_at.elapsed() < Duration::from_millis(inner.heartbeat_timeout_ms)
            {
                return Ok(false);
            }
            let timeout_callbacks = inner
                .on_heartbeat_timeout
                .iter()
                .map(|c| c.clone_ref(py))
                .collect::<Vec<_>>();
            inner.connected = false;
            inner.notify_block_waiters();
            let close_callbacks = inner
                .on_session_close
                .iter()
                .map(|c| c.clone_ref(py))
                .collect::<Vec<_>>();
            (true, timeout_callbacks, close_callbacks, inner.session_id)
        };
        if timed_out {
            Web4RttBindingInner::emit(py, &timeout_callbacks, session_id)?;
            Web4RttBindingInner::emit(py, &close_callbacks, session_id)?;
            return Ok(true);
        }
        Ok(false)
    }

    fn register_on_session_open(&self, py: Python<'_>, callback: PyObject) -> PyResult<()> {
        let call_now;
        let session_id;
        {
            let mut inner = self
                .inner
                .lock()
                .map_err(|_| PyRuntimeError::new_err("inner lock poisoned"))?;
            inner.on_session_open.push(callback.clone_ref(py));
            call_now = inner.connected;
            session_id = inner.session_id;
        }
        if call_now {
            callback.call1(py, (session_id,))?;
        }
        Ok(())
    }

    fn unregister_on_session_open(&self, py: Python<'_>, callback: PyObject) {
        if let Ok(mut inner) = self.inner.lock() {
            Web4RttBindingInner::remove_callback(py, &mut inner.on_session_open, &callback);
        }
    }

    fn register_on_session_close(&self, py: Python<'_>, callback: PyObject) {
        if let Ok(mut inner) = self.inner.lock() {
            inner.on_session_close.push(callback.clone_ref(py));
        }
    }

    fn unregister_on_session_close(&self, py: Python<'_>, callback: PyObject) {
        if let Ok(mut inner) = self.inner.lock() {
            Web4RttBindingInner::remove_callback(py, &mut inner.on_session_close, &callback);
        }
    }

    fn register_on_heartbeat_timeout(&self, py: Python<'_>, callback: PyObject) {
        if let Ok(mut inner) = self.inner.lock() {
            inner.on_heartbeat_timeout.push(callback.clone_ref(py));
        }
    }

    fn unregister_on_heartbeat_timeout(&self, py: Python<'_>, callback: PyObject) {
        if let Ok(mut inner) = self.inner.lock() {
            Web4RttBindingInner::remove_callback(py, &mut inner.on_heartbeat_timeout, &callback);
        }
    }

    fn clear_session_hooks(&self) {
        if let Ok(mut inner) = self.inner.lock() {
            inner.on_session_open.clear();
            inner.on_session_close.clear();
            inner.on_heartbeat_timeout.clear();
        }
    }

    fn stats<'py>(&self, py: Python<'py>) -> &'py PyDict {
        let stats = PyDict::new(py);
        if let Ok(inner) = self.inner.lock() {
            let _ = stats.set_item("attempted", inner.stats.attempted);
            let _ = stats.set_item("enqueued", inner.stats.enqueued);
            let _ = stats.set_item("accepted", inner.stats.enqueued);
            let _ = stats.set_item("dropped_oldest", inner.stats.dropped_oldest);
            let _ = stats.set_item("dropped_newest", inner.stats.dropped_newest);
            let _ = stats.set_item(
                "dropped",
                inner.stats.dropped_oldest + inner.stats.dropped_newest,
            );
            let _ = stats.set_item("blocked", inner.stats.blocked);
            let _ = stats.set_item("errors", inner.stats.errors);
            let _ = stats.set_item("overflow_events", inner.stats.overflow_events);
            let _ = stats.set_item("max_queue_len", inner.stats.max_queue_len);
        }
        stats
    }
}

impl Web4RttBinding {
    fn session_id(&self) -> PyResult<u64> {
        let inner = self
            .inner
            .lock()
            .map_err(|_| PyRuntimeError::new_err("inner lock poisoned"))?;
        Ok(inner.session_id)
    }
}

impl Web4RttBindingInner {
    fn pending(&self) -> usize {
        self.queue.len() + self.live_priority_sequences.len()
    }

    fn update_max_queue_len(&mut self) {
        self.stats.max_queue_len = self
            .stats
            .max_queue_len
            .max(self.queue.len() + self.live_priority_sequences.len());
    }

    fn push_message(&mut self, message: String, priority: Option<i32>) {
        if let Some(priority_value) = priority {
            self.next_sequence = self.next_sequence.wrapping_add(1);
            let sequence = self.next_sequence;
            self.priority_queue.push(PrioritizedMessage {
                priority: priority_value,
                sequence,
                message,
            });
            self.oldest_priority_queue.push(Reverse(sequence));
            self.live_priority_sequences.insert(sequence);
            return;
        }
        self.queue.push_back(message);
    }

    fn maybe_compact_priority_structures(&mut self) {
        self.maybe_compact_priority_queue();
        self.maybe_compact_oldest_priority_queue();
    }

    fn maybe_compact_priority_queue(&mut self) {
        if self.priority_queue.is_empty() {
            return;
        }
        let live = self.live_priority_sequences.len();
        let stale = self.priority_queue.len().saturating_sub(live);
        if stale <= live.saturating_mul(PRIORITY_QUEUE_COMPACTION_RATIO) {
            return;
        }

        let mut rebuilt = BinaryHeap::new();
        while let Some(item) = self.priority_queue.pop() {
            if self.live_priority_sequences.contains(&item.sequence) {
                rebuilt.push(item);
            }
        }
        self.priority_queue = rebuilt;
    }

    fn maybe_compact_oldest_priority_queue(&mut self) {
        if self.oldest_priority_queue.is_empty() {
            return;
        }
        let live = self.live_priority_sequences.len();
        let stale = self.oldest_priority_queue.len().saturating_sub(live);
        if stale <= live.saturating_mul(PRIORITY_QUEUE_COMPACTION_RATIO) {
            return;
        }

        self.oldest_priority_queue = self
            .live_priority_sequences
            .iter()
            .copied()
            .map(Reverse)
            .collect();
    }

    fn emit(py: Python<'_>, callbacks: &[PyObject], session_id: u64) -> PyResult<()> {
        for callback in callbacks {
            callback.call1(py, (session_id,))?;
        }
        Ok(())
    }

    fn notify_block_waiters(&self) {
        let (_lock, cvar) = &*self.block_wait;
        cvar.notify_all();
    }

    fn remove_callback(py: Python<'_>, callbacks: &mut Vec<PyObject>, callback: &PyObject) {
        if let Some(index) = callbacks
            .iter()
            .position(|existing| existing.as_ref(py).is(callback.as_ref(py)))
        {
            callbacks.remove(index);
        }
    }
}
