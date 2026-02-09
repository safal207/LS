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
    use super::*;

    #[test]
    fn test_rtt_send_receive() {
        let mut rtt = Web4RttBinding::new(10);
        assert!(rtt.send("hello".to_string()).is_ok());
        assert_eq!(rtt.receive(), Some("hello".to_string()));
        assert_eq!(rtt.receive(), None);
    }

    #[test]
    fn test_rtt_backpressure() {
        let mut rtt = Web4RttBinding::new(1);
        rtt.send("one".to_string()).unwrap();
        assert!(rtt.send("two".to_string()).is_err());
    }

    #[test]
    fn test_rtt_disconnect() {
        let mut rtt = Web4RttBinding::new(10);
        rtt.disconnect();
        assert!(rtt.send("fail".to_string()).is_err());
        assert_eq!(rtt.receive(), None);
        rtt.connect();
        assert!(rtt.send("ok".to_string()).is_ok());
    }
}
