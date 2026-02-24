use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

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
        Utc::now().to_rfc3339()
    }

    // === LRI-Core железная валидация (Rust-side guard) ===
    fn validate_lri_core(&self, lri: &serde_json::Value) -> PyResult<()> {
        if let Some(drift) = lri.get("emotional_drift").and_then(|v| v.as_f64()) {
            if !(0.0..=1.0).contains(&drift) {
                return Err(PyValueError::new_err(format!(
                    "emotional_drift out of range [0.0, 1.0]: {}",
                    drift
                )));
            }
        }
        if let Some(res) = lri.get("resonance_map").and_then(|v| v.as_object()) {
            if let Some(focus) = res.get("focus").and_then(|v| v.as_f64()) {
                if !(0.0..=1.0).contains(&focus) {
                    return Err(PyValueError::new_err(format!(
                        "resonance focus out of range [0.0, 1.0]: {}",
                        focus
                    )));
                }
            }
        }
        if let Some(inv) = lri.get("invariants").and_then(|v| v.as_array()) {
            for item in inv {
                if !item.is_string() {
                    return Err(PyValueError::new_err("all invariants must be strings"));
                }
            }
        }
        Ok(())
    }

    fn trim_entries(entries: &mut Vec<String>) {
        let now = Utc::now();
        let max_age = chrono::Duration::days(90);

        entries.retain(|line| {
            if let Some(ts_pos) = line.find(r#""ts":""#) {
                let start = ts_pos + 7;
                if let Some(ts_end) = line[start..].find('"') {
                    let ts_str = &line[start..start + ts_end];
                    if let Ok(ts) = chrono::DateTime::parse_from_rfc3339(ts_str) {
                        return now.signed_duration_since(ts.with_timezone(&Utc)) < max_age;
                    }
                }
            }
            true
        });

        if entries.len() > 50 {
            entries.truncate(50);
        }
    }

    // === Умная ротация: max 50 + старше 90 дней (YAML) ===
    fn trim_causal_memory(&self) -> PyResult<()> {
        let path = self.yaml_fallback.with_file_name("causal_memory.yaml");
        if !path.exists() {
            return Ok(());
        }

        let content =
            fs::read_to_string(&path).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

        let mut entries: Vec<String> = content
            .lines()
            .filter_map(|line| line.trim().strip_prefix("- ").map(ToOwned::to_owned))
            .collect();

        Self::trim_entries(&mut entries);

        let out = entries
            .iter()
            .map(|e| format!("- {}\n", e))
            .collect::<String>();
        fs::write(&path, out).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(())
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
        lri_core: PyObject,
        confidence: f32,
    ) -> PyResult<()> {
        if !(0.0..=1.0).contains(&confidence) {
            return Err(PyValueError::new_err(format!(
                "confidence must be in [0.0, 1.0], got {}",
                confidence
            )));
        }

        let entry =
            Python::with_gil(|py| -> PyResult<String> {
                let json = py.import("json")?;
                let lce_dump: String = json.call_method1("dumps", (lce.as_ref(py),))?.extract()?;
                let ltp_dump: String = json
                    .call_method1("dumps", (ltp_trace.as_ref(py),))?
                    .extract()?;
                let lri_dump: String = json
                    .call_method1("dumps", (lri_core.as_ref(py),))?
                    .extract()?;

                let lri_value = serde_json::from_str::<serde_json::Value>(&lri_dump)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

                self.validate_lri_core(&lri_value)?;

                let entry = serde_json::json!({
                    "ts": Self::now_iso(),
                    "cause": cause,
                    "solution": solution,
                    "confidence": confidence,
                    "lce": serde_json::from_str::<serde_json::Value>(&lce_dump).map_err(|e| PyRuntimeError::new_err(e.to_string()))?,
                    "ltp_trace": serde_json::from_str::<serde_json::Value>(&ltp_dump).map_err(|e| PyRuntimeError::new_err(e.to_string()))?,
                    "lri_core": lri_value,
                })
                .to_string();

                Ok(entry)
            })?;

        // Registry = Single Source of Truth
        #[cfg(windows)]
        {
            let hkcu = RegKey::predef(HKEY_CURRENT_USER);
            let (key, _) = hkcu
                .create_subkey(r"Software\LS\GhostGPT\CausalMemory")
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            let mut entries: Vec<String> = key.get_value("entries").unwrap_or_default();
            entries.insert(0, entry);

            Self::trim_entries(&mut entries);

            key.set_value("entries", &entries)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            key.set_value("last_timestamp", &Self::now_iso())
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            return Ok(());
        }

        #[cfg(not(windows))]
        {
            use std::io::Write;
            let path = self.yaml_fallback.with_file_name("causal_memory.yaml");
            let mut file = fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&path)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            writeln!(file, "- {}", entry).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            self.trim_causal_memory()?; // then unified trim
        }
        Ok(())
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

                if ltp_thread != thread_id && lce_thread != thread_id {
                    continue;
                }

                let obj = json.call_method1("loads", (entry.as_str(),))?;
                out.push(obj.to_object(py));
            }

            Ok(out)
        })
    }
}
