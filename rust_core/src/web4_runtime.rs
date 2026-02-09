use pyo3::prelude::*;

#[pyclass]
pub struct Web4RttBinding {
    connected: bool,
    queue: Vec<String>,
    max_queue: usize,
}

#[pymethods]
impl Web4RttBinding {
    #[new]
    fn new(max_queue: usize) -> Self {
        Self {
            connected: true,
            queue: Vec::new(),
            max_queue: max_queue.max(1),
        }
    }

    fn connect(&mut self) {
        self.connected = true;
    }

    fn disconnect(&mut self) {
        self.connected = false;
    }

    fn send(&mut self, message: String) -> PyResult<()> {
        if !self.connected {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "RTT binding disconnected",
            ));
        }
        if self.queue.len() >= self.max_queue {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "RTT binding backpressure",
            ));
        }
        self.queue.push(message);
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
}


#[cfg(test)]
mod tests {
    use super::Web4RttBinding;

    #[test]
    fn send_receive_roundtrip() {
        let mut binding = Web4RttBinding::new(2);
        binding.send("hello".to_string()).unwrap();
        assert_eq!(binding.receive(), Some("hello".to_string()));
    }

    #[test]
    fn backpressure_rejects_when_full() {
        let mut binding = Web4RttBinding::new(1);
        binding.send("first".to_string()).unwrap();
        let err = binding.send("second".to_string()).unwrap_err();
        assert!(err.to_string().contains("backpressure"));
    }

    #[test]
    fn reconnect_restores_sends() {
        let mut binding = Web4RttBinding::new(2);
        binding.disconnect();
        assert!(binding.send("offline".to_string()).is_err());
        binding.connect();
        binding.send("online".to_string()).unwrap();
        assert_eq!(binding.receive(), Some("online".to_string()));
    }
}
