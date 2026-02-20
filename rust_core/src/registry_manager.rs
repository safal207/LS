use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

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
}
