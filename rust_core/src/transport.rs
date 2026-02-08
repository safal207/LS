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
    #[pyo3(get, set)]
    pub max_queue_depth: usize,
    #[pyo3(get, set)]
    pub max_payload_bytes: usize,
}

#[pymethods]
impl TransportConfig {
    #[new]
    fn new(
        heartbeat_ms: Option<u64>,
        max_channels: Option<u64>,
        max_queue_depth: Option<usize>,
        max_payload_bytes: Option<usize>,
    ) -> Self {
        Self {
            heartbeat_ms: heartbeat_ms.unwrap_or(5_000),
            max_channels: max_channels.unwrap_or(64),
            max_queue_depth: max_queue_depth.unwrap_or(1_024),
            max_payload_bytes: max_payload_bytes.unwrap_or(256 * 1024),
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

    fn as_str(&self) -> &'static str {
        match self {
            Self::State => "state",
            Self::Knowledge => "knowledge",
            Self::Control => "control",
        }
    }
}

#[pyclass]
pub struct TransportHandle {
    config: TransportConfig,
    next_id: AtomicU64,
    channels: Mutex<HashMap<u64, ChannelInfo>>,
    queues: Mutex<HashMap<u64, VecDeque<Vec<u8>>>>,
    sessions: Mutex<HashMap<u64, PeerSession>>,
}

#[derive(Clone, Debug)]
struct ChannelInfo {
    kind: ChannelKind,
    session_id: Option<u64>,
    sent_count: u64,
    recv_count: u64,
    sent_bytes: u64,
    recv_bytes: u64,
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

    #[getter]
    fn max_queue_depth(&self) -> usize {
        self.config.max_queue_depth
    }

    #[getter]
    fn max_payload_bytes(&self) -> usize {
        self.config.max_payload_bytes
    }

    fn open_channel(&self, kind: &str, session_id: Option<u64>) -> PyResult<u64> {
        let channel_kind = ChannelKind::from_str(kind)
            .ok_or_else(|| PyNotImplementedError::new_err("unknown channel kind"))?;
        if let Some(session_id) = session_id {
            let sessions = self
                .sessions
                .lock()
                .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
            if !sessions.contains_key(&session_id) {
                return Err(PyValueError::new_err("unknown session"));
            }
        }
        let channel_id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let mut channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        if channels.len() as u64 >= self.config.max_channels {
            return Err(PyNotImplementedError::new_err("max channels exceeded"));
        }
        channels.insert(
            channel_id,
            ChannelInfo {
                kind: channel_kind,
                session_id,
                sent_count: 0,
                recv_count: 0,
                sent_bytes: 0,
                recv_bytes: 0,
            },
        );
        let mut queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        queues.insert(channel_id, VecDeque::new());
        Ok(channel_id)
    }

    fn bind_channel(&self, channel: u64, session_id: u64) -> PyResult<()> {
        let sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        if !sessions.contains_key(&session_id) {
            return Err(PyValueError::new_err("unknown session"));
        }
        drop(sessions);
        let mut channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        let entry = channels
            .get_mut(&channel)
            .ok_or_else(|| PyValueError::new_err("unknown channel"))?;
        entry.session_id = Some(session_id);
        Ok(())
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

    fn session_info(&self, session_id: u64) -> PyResult<(String, u128, u128)> {
        let sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        let session = sessions
            .get(&session_id)
            .ok_or_else(|| PyValueError::new_err("unknown session"))?;
        let now = Instant::now();
        let age_ms = now.duration_since(session.created_at).as_millis();
        let heartbeat_ms = now.duration_since(session.last_heartbeat).as_millis();
        Ok((session.peer_id.clone(), age_ms, heartbeat_ms))
    }

    fn list_sessions(&self) -> PyResult<Vec<(u64, String, u128, u128)>> {
        let sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        let now = Instant::now();
        let mut snapshot = Vec::with_capacity(sessions.len());
        for (session_id, session) in sessions.iter() {
            let age_ms = now.duration_since(session.created_at).as_millis();
            let heartbeat_ms = now.duration_since(session.last_heartbeat).as_millis();
            snapshot.push((*session_id, session.peer_id.clone(), age_ms, heartbeat_ms));
        }
        Ok(snapshot)
    }

    fn prune_sessions(&self) -> PyResult<usize> {
        let mut sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        let now = Instant::now();
        let timeout = Duration::from_millis(self.config.heartbeat_ms * 2);
        let before = sessions.len();
        sessions.retain(|_, session| now.duration_since(session.last_heartbeat) <= timeout);
        Ok(before.saturating_sub(sessions.len()))
    }

    fn send(&self, channel: u64, payload: &[u8]) -> PyResult<()> {
        if payload.len() > self.config.max_payload_bytes {
            return Err(PyValueError::new_err("payload exceeds max_payload_bytes"));
        }
        let channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        let channel_info = channels
            .get(&channel)
            .ok_or_else(|| PyValueError::new_err("unknown channel"))?;
        if let Some(session_id) = channel_info.session_id {
            let sessions = self
                .sessions
                .lock()
                .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
            if !sessions.contains_key(&session_id) {
                return Err(PyValueError::new_err("channel session closed"));
            }
        }
        if !channels.contains_key(&channel) {
            return Err(PyValueError::new_err("unknown channel"));
        }
        drop(channels);
        let mut queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        if let Some(queue) = queues.get_mut(&channel) {
            if queue.len() >= self.config.max_queue_depth {
                return Err(PyValueError::new_err("channel queue full"));
            }
            queue.push_back(payload.to_vec());
            let mut channels = self
                .channels
                .lock()
                .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
            if let Some(info) = channels.get_mut(&channel) {
                info.sent_count = info.sent_count.saturating_add(1);
                info.sent_bytes = info.sent_bytes.saturating_add(payload.len() as u64);
            }
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
        let channel_info = channels
            .get(&channel)
            .ok_or_else(|| PyValueError::new_err("unknown channel"))?;
        if let Some(session_id) = channel_info.session_id {
            let sessions = self
                .sessions
                .lock()
                .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
            if !sessions.contains_key(&session_id) {
                return Err(PyValueError::new_err("channel session closed"));
            }
        }
        if !channels.contains_key(&channel) {
            return Err(PyValueError::new_err("unknown channel"));
        }
        drop(channels);
        let mut queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        if let Some(queue) = queues.get_mut(&channel) {
            let payload = queue.pop_front().unwrap_or_default();
            if !payload.is_empty() {
                let mut channels = self
                    .channels
                    .lock()
                    .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
                if let Some(info) = channels.get_mut(&channel) {
                    info.recv_count = info.recv_count.saturating_add(1);
                    info.recv_bytes = info.recv_bytes.saturating_add(payload.len() as u64);
                }
            }
            Ok(payload)
        } else {
            Err(PyValueError::new_err("channel queue missing"))
        }
    }

    fn queue_len(&self, channel: u64) -> PyResult<usize> {
        let channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        if !channels.contains_key(&channel) {
            return Err(PyValueError::new_err("unknown channel"));
        }
        drop(channels);
        let queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        queues
            .get(&channel)
            .map(|queue| queue.len())
            .ok_or_else(|| PyValueError::new_err("channel queue missing"))
    }

    fn drain(&self, channel: u64, max_items: Option<usize>) -> PyResult<Vec<Vec<u8>>> {
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
        let queue = queues
            .get_mut(&channel)
            .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
        let limit = max_items.unwrap_or(queue.len());
        let mut drained = Vec::with_capacity(limit.min(queue.len()));
        for _ in 0..limit.min(queue.len()) {
            if let Some(payload) = queue.pop_front() {
                drained.push(payload);
            }
        }
        Ok(drained)
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

    fn clear_channel(&self, channel: u64) -> PyResult<usize> {
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
        let queue = queues
            .get_mut(&channel)
            .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
        let cleared = queue.len();
        queue.clear();
        Ok(cleared)
    }

    fn channel_info(&self, channel: u64) -> PyResult<(String, Option<u64>)> {
        let channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        let info = channels
            .get(&channel)
            .ok_or_else(|| PyValueError::new_err("unknown channel"))?;
        Ok((info.kind.as_str().to_string(), info.session_id))
    }

    fn channel_stats(
        &self,
        channel: u64,
    ) -> PyResult<(String, Option<u64>, usize, u64, u64, u64, u64)> {
        let channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        let info = channels
            .get(&channel)
            .ok_or_else(|| PyValueError::new_err("unknown channel"))?;
        let kind = info.kind.as_str().to_string();
        let session_id = info.session_id;
        let sent_count = info.sent_count;
        let recv_count = info.recv_count;
        let sent_bytes = info.sent_bytes;
        let recv_bytes = info.recv_bytes;
        drop(channels);
        let queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        let queue_len = queues
            .get(&channel)
            .map(|queue| queue.len())
            .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
        Ok((
            kind,
            session_id,
            queue_len,
            sent_count,
            recv_count,
            sent_bytes,
            recv_bytes,
        ))
    }

    fn list_channels(&self) -> PyResult<Vec<(u64, String, Option<u64>)>> {
        let channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        let mut snapshot = Vec::with_capacity(channels.len());
        for (channel_id, info) in channels.iter() {
            snapshot.push((*channel_id, info.kind.as_str().to_string(), info.session_id));
        }
        Ok(snapshot)
    }

    fn list_channel_stats(&self) -> PyResult<Vec<(u64, String, Option<u64>, usize, u64, u64, u64, u64)>> {
        let channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        let queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        let mut snapshot = Vec::with_capacity(channels.len());
        for (channel_id, info) in channels.iter() {
            let queue_len = queues.get(channel_id).map(|queue| queue.len()).unwrap_or(0);
            snapshot.push((
                *channel_id,
                info.kind.as_str().to_string(),
                info.session_id,
                queue_len,
                info.sent_count,
                info.recv_count,
                info.sent_bytes,
                info.recv_bytes,
            ));
        }
        Ok(snapshot)
    }

    fn close_session(&self, session_id: u64) -> PyResult<()> {
        let mut sessions = self
            .sessions
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("session registry poisoned"))?;
        sessions.remove(&session_id);
        drop(sessions);
        let mut channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        let mut queues = self
            .queues
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("queue registry poisoned"))?;
        let to_remove: Vec<u64> = channels
            .iter()
            .filter_map(|(channel_id, info)| {
                if info.session_id == Some(session_id) {
                    Some(*channel_id)
                } else {
                    None
                }
            })
            .collect();
        for channel_id in to_remove {
            channels.remove(&channel_id);
            queues.remove(&channel_id);
        }
        Ok(())
    }
}
