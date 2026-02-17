#![allow(non_local_definitions)]

use pyo3::prelude::*;

mod async_web4_runtime;
mod governance;
mod memory_manager;
mod pattern_matcher;
mod storage;
mod transport;
mod web4_runtime;

use governance::AdaptiveGovernor;
use memory_manager::MemoryManager;
use pattern_matcher::PatternMatcher;
use storage::Storage;
use transport::{TransportConfig, TransportHandle};
use web4_runtime::Web4RttBinding;

#[pymodule]
fn ghostgpt_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<AdaptiveGovernor>()?;
    m.add_class::<MemoryManager>()?;
    m.add_class::<PatternMatcher>()?;
    m.add_class::<Storage>()?;
    m.add_class::<TransportConfig>()?;
    m.add_class::<TransportHandle>()?;
    m.add_class::<Web4RttBinding>()?;
    Ok(())
}
