use pyo3::exceptions::PyNotImplementedError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;

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
}

#[pymethods]
impl TransportHandle {
    #[new]
    fn new(config: TransportConfig) -> Self {
        Self {
            config,
            next_id: AtomicU64::new(1),
            channels: Mutex::new(HashMap::new()),
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
        Ok(channel_id)
    }

    fn send(&self, _channel: u64, _payload: &[u8]) -> PyResult<()> {
        Err(PyNotImplementedError::new_err(
            "transport send not implemented",
        ))
    }

    fn receive(&self, _channel: u64) -> PyResult<Vec<u8>> {
        Err(PyNotImplementedError::new_err(
            "transport receive not implemented",
        ))
    }

    fn close_channel(&self, channel: u64) -> PyResult<()> {
        let mut channels = self
            .channels
            .lock()
            .map_err(|_| PyNotImplementedError::new_err("channel registry poisoned"))?;
        channels.remove(&channel);
        Ok(())
    }
}
