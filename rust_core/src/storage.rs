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
        let res = self
            .db
            .get(key.as_bytes())
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Failed to get: {}", e)))?;

        Ok(res.map(|ivec| ivec.to_vec()))
    }

    #[pyo3(name = "flush")]
    pub fn flush(&self) -> PyResult<()> {
        self.db
            .flush()
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Failed to flush: {}", e)))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::Storage;
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn unique_db_path() -> PathBuf {
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        std::env::temp_dir().join(format!("ghostgpt_core_storage_test_{ts}"))
    }

    #[test]
    fn save_and_load_roundtrip() {
        let path = unique_db_path();
        let storage = Storage::new(path.to_string_lossy().to_string()).expect("storage open");

        storage
            .save("key-1".to_string(), b"payload".to_vec())
            .expect("save payload");
        storage.flush().expect("flush db");

        let loaded = storage.load("key-1".to_string()).expect("load payload");
        assert_eq!(loaded, Some(b"payload".to_vec()));

        let _ = fs::remove_dir_all(&path);
    }
}
