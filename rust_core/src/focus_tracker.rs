use pyo3::prelude::*;
use pyo3::types::PyDict;

#[pyclass]
#[derive(Clone, Default)]
pub struct FocusTracker;

#[pymethods]
impl FocusTracker {
    #[new]
    fn new() -> Self {
        Self
    }

    fn get_active_window(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        dict.set_item("title", "")?;
        dict.set_item("class_name", "")?;
        dict.set_item("hwnd", "0x0")?;
        dict.set_item("process_name", "")?;
        dict.set_item("text_snippet", "")?;

        let cursor = PyDict::new(py);
        cursor.set_item("line", 0)?;
        cursor.set_item("column", 0)?;
        dict.set_item("cursor_position", cursor)?;

        dict.set_item("confusion_score", 0.0f32)?;
        dict.set_item("fuzzy_factors", PyDict::new(py))?;
        dict.set_item("confidence", 0.9f32)?;
        Ok(dict.to_object(py))
    }
}
