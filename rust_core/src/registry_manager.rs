use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

#[cfg(windows)]
use chrono::Utc;
#[cfg(windows)]
use winreg::enums::*;
#[cfg(windows)]
use winreg::RegKey;

#[pyclass]
#[derive(Clone)]
pub struct RegistryManager {
    yaml_fallback: PathBuf,
}

impl RegistryManager {
    fn yaml_value(&self, key: &str) -> Option<String> {
        let content = fs::read_to_string(&self.yaml_fallback).ok()?;
        let parsed = parse_simple_yaml(&content);
        parsed.get(key).cloned()
    }

    fn now_iso() -> String {
        #[cfg(windows)]
        {
            Utc::now().to_rfc3339()
        }
        #[cfg(not(windows))]
        {
            use std::time::{SystemTime, UNIX_EPOCH};
            let secs = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or_default();
            format!("{}", secs)
        }
    }
}

fn parse_simple_yaml(content: &str) -> HashMap<String, String> {
    let mut out = HashMap::new();
    for raw in content.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once(':') {
            out.insert(k.trim().to_string(), v.trim().trim_matches('"').to_string());
        }
    }
    out
}

#[pymethods]
impl RegistryManager {
    #[new]
    fn new(yaml_path: String) -> Self {
        Self {
            yaml_fallback: PathBuf::from(yaml_path),
        }
    }

    fn get_config(&self, key: String) -> PyResult<String> {
        #[cfg(windows)]
        {
            let hkcu = RegKey::predef(HKEY_CURRENT_USER);
            if let Ok(k) = hkcu.open_subkey(r"Software\LS\GhostGPT") {
                if let Ok(v) = k.get_value::<String, _>(&key) {
                    return Ok(v);
                }
            }
        }
        Ok(self.yaml_value(&key).unwrap_or_default())
    }

    fn set_config(&self, key: String, value: String) -> PyResult<()> {
        #[cfg(windows)]
        {
            let hkcu = RegKey::predef(HKEY_CURRENT_USER);
            let (k, _) = hkcu
                .create_subkey(r"Software\LS\GhostGPT")
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            k.set_value(&key, &value)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            return Ok(());
        }

        #[cfg(not(windows))]
        {
            let mut existing = if self.yaml_fallback.exists() {
                parse_simple_yaml(
                    &fs::read_to_string(&self.yaml_fallback)
                        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?,
                )
            } else {
                HashMap::new()
            };
            existing.insert(key, value);
            let mut lines = Vec::new();
            for (k, v) in existing {
                lines.push(format!("{}: {}", k, v));
            }
            lines.sort();
            fs::write(&self.yaml_fallback, format!("{}\n", lines.join("\n")))
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            Ok(())
        }
    }

    fn enable_auto_start(&self, exe_path: String) -> PyResult<()> {
        #[cfg(windows)]
        {
            let hkcu = RegKey::predef(HKEY_CURRENT_USER);
            let (run, _) = hkcu
                .create_subkey(r"Software\Microsoft\Windows\CurrentVersion\Run")
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            run.set_value("GhostGPT", &exe_path)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            return Ok(());
        }

        #[cfg(not(windows))]
        {
            let _ = exe_path;
            Ok(())
        }
    }

    fn save_last_event_id(&self, event_id: String) -> PyResult<()> {
        self.set_config("LastEventId".to_string(), event_id)
    }

    fn get_last_event_id(&self) -> PyResult<String> {
        self.get_config("LastEventId".to_string())
    }

    fn save_causal_trace(
        &self,
        cause: String,
        solution: String,
        lce: PyObject,
        ltp_trace: PyObject,
        confidence: f32,
    ) -> PyResult<()> {
        let (lce_str, ltp_str) = Python::with_gil(|py| -> PyResult<(String, String)> {
            let json = py.import("json")?;
            let lce_dump: String = json.call_method1("dumps", (lce.as_ref(py),))?.extract()?;
            let ltp_dump: String = json
                .call_method1("dumps", (ltp_trace.as_ref(py),))?
                .extract()?;
            Ok((lce_dump, ltp_dump))
        })?;

        let entry = format!(
            r#"{{"ts":"{}","cause":"{}","solution":"{}","confidence":{},"lce":{},"ltp_trace":{}}}"#,
            Self::now_iso(),
            cause.replace('"', r#"\""#),
            solution.replace('"', r#"\""#),
            confidence,
            lce_str,
            ltp_str
        );

        #[cfg(windows)]
        {
            let hkcu = RegKey::predef(HKEY_CURRENT_USER);
            let (key, _) = hkcu
                .create_subkey(r"Software\LS\GhostGPT\CausalMemory")
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            let mut entries: Vec<String> = key.get_value("entries").unwrap_or_default();
            entries.insert(0, entry);
            if entries.len() > 50 {
                entries.truncate(50);
            }
            key.set_value("entries", &entries)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            key.set_value("last_timestamp", &Self::now_iso())
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            return Ok(());
        }

        #[cfg(not(windows))]
        {
            let path = self.yaml_fallback.with_file_name("causal_memory.yaml");
            let mut content = if path.exists() {
                fs::read_to_string(&path).map_err(|e| PyRuntimeError::new_err(e.to_string()))?
            } else {
                String::new()
            };
            content.push_str("- ");
            content.push_str(&entry);
            content.push('\n');
            fs::write(path, content).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            Ok(())
        }
    }

    fn replay_thread(&self, thread_id: String) -> PyResult<Vec<PyObject>> {
        let mut raw_entries: Vec<String> = Vec::new();

        #[cfg(windows)]
        {
            let hkcu = RegKey::predef(HKEY_CURRENT_USER);
            if let Ok(key) = hkcu.open_subkey(r"Software\LS\GhostGPT\CausalMemory") {
                raw_entries = key.get_value("entries").unwrap_or_default();
            }
        }

        #[cfg(not(windows))]
        {
            let path = self.yaml_fallback.with_file_name("causal_memory.yaml");
            if path.exists() {
                let content = fs::read_to_string(&path)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
                raw_entries = content
                    .lines()
                    .filter_map(|line| line.trim().strip_prefix("- ").map(ToOwned::to_owned))
                    .collect();
            }
        }

        Python::with_gil(|py| -> PyResult<Vec<PyObject>> {
            let json = py.import("json")?;
            let mut out: Vec<PyObject> = Vec::new();

            for entry in raw_entries {
                let parsed: serde_json::Value = match serde_json::from_str(&entry) {
                    Ok(v) => v,
                    Err(_) => continue,
                };

                let ltp_thread = parsed
                    .get("ltp_trace")
                    .and_then(|v| v.get("thread_id"))
                    .and_then(|v| v.as_str())
                    .unwrap_or_default();

                let lce_thread = parsed
                    .get("lce")
                    .and_then(|v| v.get("memory"))
                    .and_then(|v| v.get("thread"))
                    .and_then(|v| v.as_str())
                    .unwrap_or_default();

                if !(entry.contains(&thread_id)
                    || ltp_thread == thread_id
                    || lce_thread == thread_id)
                {
                    continue;
                }

                let obj = json.call_method1("loads", (entry.as_str(),))?;
                out.push(obj.to_object(py));
            }

            Ok(out)
        })
    }
}
