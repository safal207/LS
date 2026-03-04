#![allow(non_local_definitions)]

use pyo3::prelude::*;

mod causal;
mod focus_tracker;
mod fuzzy_coherence;
mod governance;
mod memory_manager;
mod pattern_matcher;
mod registry_manager;
mod storage;
mod temporal_graph;
mod transport;
pub mod vision_core;
mod web4_runtime;

use causal::memory::RustCausalMemory;
use focus_tracker::FocusTracker;
use fuzzy_coherence::{
    smooth_coherence, tune_backpressure_limits, FuzzyBackpressureConfig, FuzzyCoherenceConfig,
};
use governance::AdaptiveGovernor;
use memory_manager::MemoryManager;
use pattern_matcher::PatternMatcher;
use registry_manager::RegistryManager;
use storage::Storage;
use transport::{TransportConfig, TransportHandle};
use vision_core::{
    RustFrameBuffer, RustPrivacyRedactor, RustRhythmAnalyzer, RustSceneChangeDetector,
    VisionPipeline,
};
use web4_runtime::Web4RttBinding;

#[pymodule]
fn ghostgpt_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<AdaptiveGovernor>()?;
    m.add_class::<FuzzyCoherenceConfig>()?;
    m.add_class::<FuzzyBackpressureConfig>()?;
    m.add_class::<FocusTracker>()?;
    m.add_class::<RegistryManager>()?;
    m.add_class::<MemoryManager>()?;
    m.add_class::<PatternMatcher>()?;
    m.add_class::<Storage>()?;
    m.add_class::<TransportConfig>()?;
    m.add_class::<TransportHandle>()?;
    m.add_class::<Web4RttBinding>()?;
    m.add_class::<RustCausalMemory>()?;
    m.add_class::<RustSceneChangeDetector>()?;
    m.add_class::<RustPrivacyRedactor>()?;
    m.add_class::<RustFrameBuffer>()?;
    m.add_class::<RustRhythmAnalyzer>()?;
    m.add_class::<VisionPipeline>()?;
    m.add_function(wrap_pyfunction!(smooth_coherence, m)?)?;
    m.add_function(wrap_pyfunction!(tune_backpressure_limits, m)?)?;
    Ok(())
}
