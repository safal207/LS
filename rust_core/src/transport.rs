use pyo3::exceptions::PyNotImplementedError;
use pyo3::exceptions::PyRuntimeError;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::collections::VecDeque;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, RwLock};
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

/// Transport handle with reduced lock contention:
/// - `channels`: `RwLock` — reads dominate (stats, routing lookups)
/// - `state_queues` / `knowledge_queues` / `control_queues`: separate `Mutex` per kind —
///   prevents cross-kind contention when State, Knowledge, and Control channels are
///   operating concurrently.
/// - `sessions`: `Mutex` — session lifecycle is infrequent, single lock is sufficient.
#[pyclass]
pub struct TransportHandle {
    config: TransportConfig,
    next_id: AtomicU64,
    channels: RwLock<HashMap<u64, ChannelInfo>>,
    state_queues: Mutex<HashMap<u64, VecDeque<Vec<u8>>>>,
    knowledge_queues: Mutex<HashMap<u64, VecDeque<Vec<u8>>>>,
    control_queues: Mutex<HashMap<u64, VecDeque<Vec<u8>>>>,
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

type ChannelStats = (String, Option<u64>, usize, u64, u64, u64, u64);
type ChannelStatsEntry = (u64, String, Option<u64>, usize, u64, u64, u64, u64);

impl TransportHandle {
    /// Returns the queue length for a channel from the appropriate per-kind queue.
    fn queue_len_for(&self, channel: u64, kind: ChannelKind) -> PyResult<usize> {
        match kind {
            ChannelKind::State => {
                let q = self.state_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("state queue lock poisoned"))?;
                Ok(q.get(&channel).map(|v| v.len()).unwrap_or(0))
            }
            ChannelKind::Knowledge => {
                let q = self.knowledge_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("knowledge queue lock poisoned"))?;
                Ok(q.get(&channel).map(|v| v.len()).unwrap_or(0))
            }
            ChannelKind::Control => {
                let q = self.control_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("control queue lock poisoned"))?;
                Ok(q.get(&channel).map(|v| v.len()).unwrap_or(0))
            }
        }
    }
}

#[pymethods]
impl TransportHandle {
    #[new]
    fn new(config: TransportConfig) -> Self {
        Self {
            config,
            next_id: AtomicU64::new(1),
            channels: RwLock::new(HashMap::new()),
            state_queues: Mutex::new(HashMap::new()),
            knowledge_queues: Mutex::new(HashMap::new()),
            control_queues: Mutex::new(HashMap::new()),
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
                .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
            if !sessions.contains_key(&session_id) {
                return Err(PyValueError::new_err("unknown session"));
            }
        }
        let channel_id = self.next_id.fetch_add(1, Ordering::SeqCst);
        {
            let mut channels = self
                .channels
                .write()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
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
        }
        match channel_kind {
            ChannelKind::State => {
                self.state_queues
                    .lock()
                    .map_err(|_| PyRuntimeError::new_err("state queue lock poisoned"))?
                    .insert(channel_id, VecDeque::new());
            }
            ChannelKind::Knowledge => {
                self.knowledge_queues
                    .lock()
                    .map_err(|_| PyRuntimeError::new_err("knowledge queue lock poisoned"))?
                    .insert(channel_id, VecDeque::new());
            }
            ChannelKind::Control => {
                self.control_queues
                    .lock()
                    .map_err(|_| PyRuntimeError::new_err("control queue lock poisoned"))?
                    .insert(channel_id, VecDeque::new());
            }
        }
        Ok(channel_id)
    }

    fn bind_channel(&self, channel: u64, session_id: u64) -> PyResult<()> {
        let sessions = self
            .sessions
            .lock()
            .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
        if !sessions.contains_key(&session_id) {
            return Err(PyValueError::new_err("unknown session"));
        }
        drop(sessions);
        let mut channels = self
            .channels
            .write()
            .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
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
            .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
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
            .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
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
            .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
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
            .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
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
            .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
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
            .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
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
        let channel_info = {
            let channels = self
                .channels
                .read()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            channels
                .get(&channel)
                .cloned()
                .ok_or_else(|| PyValueError::new_err("unknown channel"))?
        };

        if let Some(session_id) = channel_info.session_id {
            let sessions = self
                .sessions
                .lock()
                .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
            if !sessions.contains_key(&session_id) {
                return Err(PyValueError::new_err("channel session closed"));
            }
        }

        match channel_info.kind {
            ChannelKind::State => {
                let mut q = self.state_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("state queue lock poisoned"))?;
                let queue = q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
                if queue.len() >= self.config.max_queue_depth {
                    return Err(PyValueError::new_err("channel queue full"));
                }
                queue.push_back(payload.to_vec());
            }
            ChannelKind::Knowledge => {
                let mut q = self.knowledge_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("knowledge queue lock poisoned"))?;
                let queue = q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
                if queue.len() >= self.config.max_queue_depth {
                    return Err(PyValueError::new_err("channel queue full"));
                }
                queue.push_back(payload.to_vec());
            }
            ChannelKind::Control => {
                let mut q = self.control_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("control queue lock poisoned"))?;
                let queue = q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
                if queue.len() >= self.config.max_queue_depth {
                    return Err(PyValueError::new_err("channel queue full"));
                }
                queue.push_back(payload.to_vec());
            }
        }

        {
            let mut channels = self
                .channels
                .write()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            if let Some(info) = channels.get_mut(&channel) {
                info.sent_count = info.sent_count.saturating_add(1);
                info.sent_bytes = info.sent_bytes.saturating_add(payload.len() as u64);
            }
        }
        Ok(())
    }

    fn receive(&self, channel: u64) -> PyResult<Vec<u8>> {
        let channel_info = {
            let channels = self
                .channels
                .read()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            channels
                .get(&channel)
                .cloned()
                .ok_or_else(|| PyValueError::new_err("unknown channel"))?
        };

        if let Some(session_id) = channel_info.session_id {
            let sessions = self
                .sessions
                .lock()
                .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
            if !sessions.contains_key(&session_id) {
                return Err(PyValueError::new_err("channel session closed"));
            }
        }

        let payload = match channel_info.kind {
            ChannelKind::State => {
                let mut q = self.state_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("state queue lock poisoned"))?;
                q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?
                    .pop_front()
                    .unwrap_or_default()
            }
            ChannelKind::Knowledge => {
                let mut q = self.knowledge_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("knowledge queue lock poisoned"))?;
                q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?
                    .pop_front()
                    .unwrap_or_default()
            }
            ChannelKind::Control => {
                let mut q = self.control_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("control queue lock poisoned"))?;
                q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?
                    .pop_front()
                    .unwrap_or_default()
            }
        };

        if !payload.is_empty() {
            let mut channels = self
                .channels
                .write()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            if let Some(info) = channels.get_mut(&channel) {
                info.recv_count = info.recv_count.saturating_add(1);
                info.recv_bytes = info.recv_bytes.saturating_add(payload.len() as u64);
            }
        }
        Ok(payload)
    }

    fn queue_len(&self, channel: u64) -> PyResult<usize> {
        let kind = {
            let channels = self
                .channels
                .read()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            channels
                .get(&channel)
                .map(|info| info.kind)
                .ok_or_else(|| PyValueError::new_err("unknown channel"))?
        };
        self.queue_len_for(channel, kind)
    }

    fn drain(&self, channel: u64, max_items: Option<usize>) -> PyResult<Vec<Vec<u8>>> {
        let kind = {
            let channels = self
                .channels
                .read()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            channels
                .get(&channel)
                .map(|info| info.kind)
                .ok_or_else(|| PyValueError::new_err("unknown channel"))?
        };

        macro_rules! drain_queue {
            ($queue_map:expr, $err:literal) => {{
                let mut q = $queue_map
                    .lock()
                    .map_err(|_| PyRuntimeError::new_err($err))?;
                let queue = q
                    .get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
                let limit = max_items.unwrap_or(queue.len());
                let mut drained = Vec::with_capacity(limit.min(queue.len()));
                for _ in 0..limit.min(queue.len()) {
                    if let Some(payload) = queue.pop_front() {
                        drained.push(payload);
                    }
                }
                drained
            }};
        }

        let result = match kind {
            ChannelKind::State => drain_queue!(self.state_queues, "state queue lock poisoned"),
            ChannelKind::Knowledge => drain_queue!(self.knowledge_queues, "knowledge queue lock poisoned"),
            ChannelKind::Control => drain_queue!(self.control_queues, "control queue lock poisoned"),
        };
        Ok(result)
    }

    fn close_channel(&self, channel: u64) -> PyResult<()> {
        let kind = {
            let mut channels = self
                .channels
                .write()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            let kind = channels.get(&channel).map(|info| info.kind);
            channels.remove(&channel);
            kind
        };
        if let Some(kind) = kind {
            match kind {
                ChannelKind::State => {
                    self.state_queues.lock()
                        .map_err(|_| PyRuntimeError::new_err("state queue lock poisoned"))?
                        .remove(&channel);
                }
                ChannelKind::Knowledge => {
                    self.knowledge_queues.lock()
                        .map_err(|_| PyRuntimeError::new_err("knowledge queue lock poisoned"))?
                        .remove(&channel);
                }
                ChannelKind::Control => {
                    self.control_queues.lock()
                        .map_err(|_| PyRuntimeError::new_err("control queue lock poisoned"))?
                        .remove(&channel);
                }
            }
        }
        Ok(())
    }

    fn clear_channel(&self, channel: u64) -> PyResult<usize> {
        let kind = {
            let channels = self
                .channels
                .read()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            channels
                .get(&channel)
                .map(|info| info.kind)
                .ok_or_else(|| PyValueError::new_err("unknown channel"))?
        };
        match kind {
            ChannelKind::State => {
                let mut q = self.state_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("state queue lock poisoned"))?;
                let queue = q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
                let cleared = queue.len();
                queue.clear();
                Ok(cleared)
            }
            ChannelKind::Knowledge => {
                let mut q = self.knowledge_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("knowledge queue lock poisoned"))?;
                let queue = q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
                let cleared = queue.len();
                queue.clear();
                Ok(cleared)
            }
            ChannelKind::Control => {
                let mut q = self.control_queues.lock()
                    .map_err(|_| PyRuntimeError::new_err("control queue lock poisoned"))?;
                let queue = q.get_mut(&channel)
                    .ok_or_else(|| PyValueError::new_err("channel queue missing"))?;
                let cleared = queue.len();
                queue.clear();
                Ok(cleared)
            }
        }
    }

    fn channel_info(&self, channel: u64) -> PyResult<(String, Option<u64>)> {
        let channels = self
            .channels
            .read()
            .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
        let info = channels
            .get(&channel)
            .ok_or_else(|| PyValueError::new_err("unknown channel"))?;
        Ok((info.kind.as_str().to_string(), info.session_id))
    }

    fn channel_stats(&self, channel: u64) -> PyResult<ChannelStats> {
        let (kind, session_id, sent_count, recv_count, sent_bytes, recv_bytes) = {
            let channels = self
                .channels
                .read()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            let info = channels
                .get(&channel)
                .ok_or_else(|| PyValueError::new_err("unknown channel"))?;
            (info.kind, info.session_id, info.sent_count, info.recv_count, info.sent_bytes, info.recv_bytes)
        };
        let queue_len = self.queue_len_for(channel, kind)?;
        Ok((
            kind.as_str().to_string(),
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
            .read()
            .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
        let mut snapshot = Vec::with_capacity(channels.len());
        for (channel_id, info) in channels.iter() {
            snapshot.push((*channel_id, info.kind.as_str().to_string(), info.session_id));
        }
        Ok(snapshot)
    }

    fn list_channel_stats(&self) -> PyResult<Vec<ChannelStatsEntry>> {
        // Snapshot channel metadata under read lock — no queue locks held simultaneously.
        let channel_snapshot: Vec<(u64, ChannelInfo)> = {
            let channels = self
                .channels
                .read()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            channels.iter().map(|(id, info)| (*id, info.clone())).collect()
        };

        // Collect per-kind channel IDs to minimize queue lock acquisitions.
        let mut state_ids: Vec<u64> = Vec::new();
        let mut knowledge_ids: Vec<u64> = Vec::new();
        let mut control_ids: Vec<u64> = Vec::new();
        for (id, info) in &channel_snapshot {
            match info.kind {
                ChannelKind::State => state_ids.push(*id),
                ChannelKind::Knowledge => knowledge_ids.push(*id),
                ChannelKind::Control => control_ids.push(*id),
            }
        }

        let mut queue_lens: HashMap<u64, usize> = HashMap::with_capacity(channel_snapshot.len());
        {
            let q = self.state_queues.lock()
                .map_err(|_| PyRuntimeError::new_err("state queue lock poisoned"))?;
            for id in &state_ids {
                queue_lens.insert(*id, q.get(id).map(|v| v.len()).unwrap_or(0));
            }
        }
        {
            let q = self.knowledge_queues.lock()
                .map_err(|_| PyRuntimeError::new_err("knowledge queue lock poisoned"))?;
            for id in &knowledge_ids {
                queue_lens.insert(*id, q.get(id).map(|v| v.len()).unwrap_or(0));
            }
        }
        {
            let q = self.control_queues.lock()
                .map_err(|_| PyRuntimeError::new_err("control queue lock poisoned"))?;
            for id in &control_ids {
                queue_lens.insert(*id, q.get(id).map(|v| v.len()).unwrap_or(0));
            }
        }

        let result = channel_snapshot
            .into_iter()
            .map(|(id, info)| {
                let queue_len = *queue_lens.get(&id).unwrap_or(&0);
                (
                    id,
                    info.kind.as_str().to_string(),
                    info.session_id,
                    queue_len,
                    info.sent_count,
                    info.recv_count,
                    info.sent_bytes,
                    info.recv_bytes,
                )
            })
            .collect();
        Ok(result)
    }

    fn close_session(&self, session_id: u64) -> PyResult<()> {
        {
            let mut sessions = self
                .sessions
                .lock()
                .map_err(|_| PyRuntimeError::new_err("session lock poisoned"))?;
            sessions.remove(&session_id);
        }
        // Collect channels belonging to this session along with their kinds, then remove them.
        let to_remove: Vec<(u64, ChannelKind)> = {
            let mut channels = self
                .channels
                .write()
                .map_err(|_| PyRuntimeError::new_err("channel lock poisoned"))?;
            let ids: Vec<(u64, ChannelKind)> = channels
                .iter()
                .filter_map(|(channel_id, info)| {
                    if info.session_id == Some(session_id) {
                        Some((*channel_id, info.kind))
                    } else {
                        None
                    }
                })
                .collect();
            for (channel_id, _) in &ids {
                channels.remove(channel_id);
            }
            ids
        };
        // Remove from per-kind queues — acquire each lock only once.
        let mut state_ids: Vec<u64> = Vec::new();
        let mut knowledge_ids: Vec<u64> = Vec::new();
        let mut control_ids: Vec<u64> = Vec::new();
        for (channel_id, kind) in to_remove {
            match kind {
                ChannelKind::State => state_ids.push(channel_id),
                ChannelKind::Knowledge => knowledge_ids.push(channel_id),
                ChannelKind::Control => control_ids.push(channel_id),
            }
        }
        if !state_ids.is_empty() {
            let mut q = self.state_queues.lock()
                .map_err(|_| PyRuntimeError::new_err("state queue lock poisoned"))?;
            for id in state_ids {
                q.remove(&id);
            }
        }
        if !knowledge_ids.is_empty() {
            let mut q = self.knowledge_queues.lock()
                .map_err(|_| PyRuntimeError::new_err("knowledge queue lock poisoned"))?;
            for id in knowledge_ids {
                q.remove(&id);
            }
        }
        if !control_ids.is_empty() {
            let mut q = self.control_queues.lock()
                .map_err(|_| PyRuntimeError::new_err("control queue lock poisoned"))?;
            for id in control_ids {
                q.remove(&id);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use pyo3::prepare_freethreaded_python;
    use std::sync::Once;

    fn init_python() {
        static INIT: Once = Once::new();
        INIT.call_once(prepare_freethreaded_python);
    }

    use super::{TransportConfig, TransportHandle};

    #[test]
    fn open_send_receive_updates_stats() {
        init_python();
        let config = TransportConfig::new(Some(1_000), Some(2), Some(4), Some(1024));
        let handle = TransportHandle::new(config);

        let ch = handle.open_channel("state", None).expect("open channel");
        handle.send(ch, b"hello").expect("send payload");

        assert_eq!(handle.queue_len(ch).expect("queue len"), 1);
        assert_eq!(
            handle.receive(ch).expect("receive payload"),
            b"hello".to_vec()
        );

        let stats = handle.channel_stats(ch).expect("channel stats");
        assert_eq!(stats.3, 1);
        assert_eq!(stats.4, 1);
        assert_eq!(stats.5, 5);
        assert_eq!(stats.6, 5);
    }
}
