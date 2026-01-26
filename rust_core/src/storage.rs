use pyo3::prelude::*;
use sled::Db;
use std::path::Path;

#[pyclass]
pub struct Storage {
    db: Db,
}

#[pymethods]
impl Storage {
    #[new]
    pub fn new(path: String) -> PyResult<Self> {
        let db = sled::open(Path::new(&path)).map_err(|e| {
            pyo3::exceptions::PyIOError::new_err(format!("Failed to open DB: {}", e))
        })?;
        Ok(Storage { db })
    }

    #[pyo3(name = "save")]
    pub fn save(&self, key: String, data: Vec<u8>) -> PyResult<()> {
        self.db.insert(key.as_bytes(), data).map_err(|e| {
            pyo3::exceptions::PyIOError::new_err(format!("Failed to insert: {}", e))
        })?;
        // Sled flushes automatically periodically, but we can rely on OS cache for speed
        Ok(())
    }

    #[pyo3(name = "load")]
    pub fn load(&self, key: String) -> PyResult<Option<Vec<u8>>> {
        let res = self.db.get(key.as_bytes()).map_err(|e| {
            pyo3::exceptions::PyIOError::new_err(format!("Failed to get: {}", e))
        })?;

        Ok(res.map(|ivec| ivec.to_vec()))
    }

    #[pyo3(name = "flush")]
    pub fn flush(&self) -> PyResult<()> {
        self.db.flush().map_err(|e| {
            pyo3::exceptions::PyIOError::new_err(format!("Failed to flush: {}", e))
        })?;
        Ok(())
    }
}
