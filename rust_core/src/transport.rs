use pyo3::exceptions::PyNotImplementedError;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::collections::VecDeque;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

#[pyclass]
#[derive(Clone)]
pub struct TransportConfig {
    #[pyo3(get, set)]
    pub heartbeat_ms: u64,
    #[pyo3(get, set)]
    pub max_channels: u64,
}

#[pymethods]
impl TransportConfig {
    #[new]
    fn new(heartbeat_ms: Option<u64>, max_channels: Option<u64>) -> Self {
        Self {
            heartbeat_ms: heartbeat_ms.unwrap_or(5_000),
            max_channels: max_channels.unwrap_or(64),
        }
    }
}

#[derive(Clone, Copy, Debug)]
enum ChannelKind {
    State,
    Knowledge,
    Control,
}

impl ChannelKind {
    fn from_str(kind: &str) -> Option<Self> {
        match kind {
            "state" => Some(Self::State),
            "knowledge" => Some(Self::Knowledge),
            "control" => Some(Self::Control),
            _ => None,
        }
    }
}

#[pyclass]
pub struct TransportHandle {
    config: TransportConfig,
    next_id: AtomicU64,
    channels: Mutex<HashMap<u64, ChannelKind>>,
    queues: Mutex<HashMap<u64, VecDeque<Vec<u8>>>>,
    sessions: Mutex<HashMap<u64, PeerSession>>,
}

struct PeerSession {
    peer_id: String,
    created_at: Instant,
    last_heartbeat: Instant,
}

#[pymethods]
impl TransportHandle {
    #[new]
    fn new(config: TransportConfig) -> Self {
        Self {
            config,
            next_id: AtomicU64::new(1),
            channels: Mutex::new(HashMap::new()),
            queues: Mutex::new(HashMap::new()),
            sessions: Mutex::new(HashMap::new()),
        }
    }

    #[getter]
    fn heartbeat_ms(&self) -> u64 {
        self.config.heartbeat_ms
    }

    #[getter]
    fn max_channels(&self) -> u64 {
        self.config.max_channels
    }

    fn open_channel(&self, kind: &str) -> PyResult<u64> {
        let channel_kind = ChannelKind::from_str(kind)
            .ok_or_else(|| PyNotImplementedError::new_err("unknown channel kind"))?;
        let channel_id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let mut channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        if channels.len() as u64 >= self.config.max_channels {
            return Err(PyNotImplementedError::new_err("max channels exceeded"));
        }
        channels.insert(channel_id, channel_kind);
        let mut queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        queues.insert(channel_id, VecDeque::new());
        Ok(channel_id)
    }

    fn create_session(&self, peer_id: &str) -> PyResult<u64> {
        let session_id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let now = Instant::now();
        let mut sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        sessions.insert(
            session_id,
            PeerSession {
                peer_id: peer_id.to_string(),
                created_at: now,
                last_heartbeat: now,
            },
        );
        Ok(session_id)
    }

    fn handshake(&self, session_id: u64, challenge: &[u8]) -> PyResult<Vec<u8>> {
        let mut sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        let session = sessions
            .get_mut(&session_id)
            .ok_or_else(|| PyValueError::new_err("unknown session"))?;
        session.last_heartbeat = Instant::now();
        Ok(challenge.to_vec())
    }

    fn heartbeat(&self, session_id: u64) -> PyResult<bool> {
        let mut sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        let session = sessions
            .get_mut(&session_id)
            .ok_or_else(|| PyValueError::new_err("unknown session"))?;
        let now = Instant::now();
        let timeout = Duration::from_millis(self.config.heartbeat_ms);
        let alive = now.duration_since(session.last_heartbeat) <= timeout * 2;
        session.last_heartbeat = now;
        Ok(alive)
    }

    fn send(&self, channel: u64, payload: &[u8]) -> PyResult<()> {
        let channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        if !channels.contains_key(&channel) {
            return Err(PyValueError::new_err("unknown channel"));
        }
        drop(channels);
        let mut queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        if let Some(queue) = queues.get_mut(&channel) {
            queue.push_back(payload.to_vec());
            Ok(())
        } else {
            Err(PyValueError::new_err("channel queue missing"))
        }
    }

    fn receive(&self, channel: u64) -> PyResult<Vec<u8>> {
        let channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        if !channels.contains_key(&channel) {
            return Err(PyValueError::new_err("unknown channel"));
        }
        drop(channels);
        let mut queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        if let Some(queue) = queues.get_mut(&channel) {
            Ok(queue.pop_front().unwrap_or_default())
        } else {
            Err(PyValueError::new_err("channel queue missing"))
        }
    }

    fn close_channel(&self, channel: u64) -> PyResult<()> {
        let mut channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        channels.remove(&channel);
        let mut queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        queues.remove(&channel);
        Ok(())
    }

    fn close_session(&self, session_id: u64) -> PyResult<()> {
        let mut sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        sessions.remove(&session_id);
        Ok(())
    }
}
