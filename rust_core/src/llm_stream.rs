use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde_json::Value;

#[pyfunction]
pub fn extract_ollama_token(frame_line: &str, has_messages: bool) -> PyResult<Option<String>> {
    let value: Value = serde_json::from_str(frame_line)
        .map_err(|err| PyValueError::new_err(format!("invalid ollama stream frame: {err}")))?;

    let token = if has_messages {
        value
            .get("message")
            .and_then(|message| message.get("content"))
            .and_then(Value::as_str)
    } else {
        value.get("response").and_then(Value::as_str)
    };

    Ok(token.map(ToOwned::to_owned))
}
