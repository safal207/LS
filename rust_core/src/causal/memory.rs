use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

const RESONANCE_THRESHOLD: f32 = 0.35;

type NodeSnapshot = (String, i64, String, f32, f32, Option<String>, String);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum LayerType {
    Customer,
    Consumer,
    Execution,
    Stability,
}

impl LayerType {
    fn as_str(self) -> &'static str {
        match self {
            Self::Customer => "Customer",
            Self::Consumer => "Consumer",
            Self::Execution => "Execution",
            Self::Stability => "Stability",
        }
    }

    fn from_str(value: &str) -> Option<Self> {
        match value {
            "Customer" => Some(Self::Customer),
            "Consumer" => Some(Self::Consumer),
            "Execution" => Some(Self::Execution),
            "Stability" => Some(Self::Stability),
            _ => None,
        }
    }

    fn level(self) -> u8 {
        match self {
            Self::Customer => 1,
            Self::Consumer => 2,
            Self::Execution => 3,
            Self::Stability => 4,
        }
    }
}

#[derive(Clone, Debug)]
struct Node {
    id: u64,
    timestamp: i64,
    content: String,
    resonance_score: f32,
    axis_position: f32,
    parent_id: Option<u64>,
    layer: LayerType,
}

#[pyclass]
pub struct RustCausalMemory {
    next_id: u64,
    nodes: HashMap<u64, Node>,
    layers: HashMap<LayerType, Vec<u64>>,
}

impl Default for RustCausalMemory {
    fn default() -> Self {
        Self::new()
    }
}

#[pymethods]
impl RustCausalMemory {
    #[new]
    pub fn new() -> Self {
        let mut layers = HashMap::new();
        layers.insert(LayerType::Customer, Vec::new());
        layers.insert(LayerType::Consumer, Vec::new());
        layers.insert(LayerType::Execution, Vec::new());
        layers.insert(LayerType::Stability, Vec::new());

        Self {
            next_id: 1,
            nodes: HashMap::new(),
            layers,
        }
    }

    #[pyo3(name = "add_intent")]
    pub fn add_intent(&mut self, layer: String, content: String) -> PyResult<String> {
        let parsed = LayerType::from_str(layer.as_str())
            .ok_or_else(|| PyValueError::new_err("Unknown layer"))?;
        if parsed != LayerType::Customer {
            return Err(PyValueError::new_err(
                "add_intent supports only layer=Customer",
            ));
        }

        let id = self.next_id;
        self.next_id += 1;

        let node = Node {
            id,
            timestamp: unix_ts(),
            content,
            resonance_score: 1.0,
            axis_position: axis_position(LayerType::Customer),
            parent_id: None,
            layer: LayerType::Customer,
        };

        self.nodes.insert(id, node);
        if let Some(entries) = self.layers.get_mut(&LayerType::Customer) {
            entries.push(id);
        }
        Ok(id.to_string())
    }

    #[pyo3(name = "transition_down")]
    pub fn transition_down(
        &mut self,
        id: String,
        new_content: String,
        new_layer: String,
    ) -> PyResult<String> {
        let source_id = parse_id(&id)?;
        if !self.nodes.contains_key(&source_id) {
            return Err(PyValueError::new_err("Parent id not found"));
        }
        let parent = self
            .nodes
            .get(&source_id)
            .cloned()
            .ok_or_else(|| PyValueError::new_err("Parent id not found"))?;
        let target_layer = LayerType::from_str(new_layer.as_str())
            .ok_or_else(|| PyValueError::new_err("Unknown target layer"))?;

        if target_layer.level() != parent.layer.level() + 1 {
            return Err(PyValueError::new_err(
                "transition_down requires moving exactly one layer lower",
            ));
        }

        let base_resonance = compute_resonance(parent.content.as_str(), new_content.as_str());
        let target_axis = axis_position(target_layer);
        let delta = (target_axis - parent.axis_position).abs();
        let resonance = (base_resonance * (1.0 - delta * 0.4)).clamp(0.0, 1.0);
        if resonance < 0.5 {
            log::warn!(
                "Low resonance on transition {} -> {}: {:.3}",
                parent.layer.as_str(),
                target_layer.as_str(),
                resonance
            );
        }
        if resonance < RESONANCE_THRESHOLD {
            return Err(PyValueError::new_err(format!(
                "ResonanceError: score {resonance:.3} is below threshold {RESONANCE_THRESHOLD:.3}"
            )));
        }

        let new_id = self.next_id;
        self.next_id += 1;

        let node = Node {
            id: new_id,
            timestamp: unix_ts(),
            content: new_content,
            resonance_score: resonance,
            axis_position: axis_position(target_layer),
            parent_id: Some(source_id),
            layer: target_layer,
        };

        self.nodes.insert(new_id, node);
        if let Some(entries) = self.layers.get_mut(&target_layer) {
            entries.push(new_id);
        }

        Ok(new_id.to_string())
    }

    #[pyo3(name = "check_resonance")]
    pub fn check_resonance(&self, id: String) -> PyResult<f32> {
        let node_id = parse_id(&id)?;
        let node = self
            .nodes
            .get(&node_id)
            .ok_or_else(|| PyValueError::new_err("Node id not found"))?;
        if let Some(parent_id) = node.parent_id {
            let parent = self
                .nodes
                .get(&parent_id)
                .ok_or_else(|| PyValueError::new_err("Parent id not found"))?;
            Ok(compute_resonance(
                parent.content.as_str(),
                node.content.as_str(),
            ))
        } else {
            Ok(1.0)
        }
    }

    #[pyo3(name = "stabilize")]
    pub fn stabilize(&self, id: String) -> PyResult<bool> {
        let node_id = parse_id(&id)?;
        let node = self
            .nodes
            .get(&node_id)
            .ok_or_else(|| PyValueError::new_err("Node id not found"))?;

        if node.layer != LayerType::Stability {
            return Ok(false);
        }

        Ok(node.resonance_score >= RESONANCE_THRESHOLD)
    }

    #[pyo3(name = "get_node")]
    pub fn get_node(&self, id: String) -> PyResult<Option<NodeSnapshot>> {
        let node_id = parse_id(&id)?;
        let maybe = self.nodes.get(&node_id).map(|n| {
            (
                n.id.to_string(),
                n.timestamp,
                n.content.clone(),
                n.resonance_score,
                n.axis_position,
                n.parent_id.map(|pid| pid.to_string()),
                n.layer.as_str().to_string(),
            )
        });
        Ok(maybe)
    }

    #[pyo3(name = "get_axis_position")]
    pub fn get_axis_position(&self, id: String) -> PyResult<f32> {
        let node_id = parse_id(&id)?;
        let node = self
            .nodes
            .get(&node_id)
            .ok_or_else(|| PyValueError::new_err("Node id not found"))?;
        Ok(node.axis_position)
    }
}

fn parse_id(id: &str) -> PyResult<u64> {
    id.parse::<u64>()
        .map_err(|_| PyValueError::new_err("Invalid node id"))
}

fn unix_ts() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn compute_resonance(parent: &str, child: &str) -> f32 {
    let p_tokens = normalize_tokens(parent);
    let c_tokens = normalize_tokens(child);

    if p_tokens.is_empty() || c_tokens.is_empty() {
        return 0.0;
    }

    let parent_len = parent.chars().count();
    let child_len = child.chars().count();
    if parent_len > 50 || child_len > 50 {
        cosine_from_tokens(parent, child, parent_len, child_len)
    } else {
        let overlap = p_tokens.intersection(&c_tokens).count() as f32;
        let denom = p_tokens.union(&c_tokens).count() as f32;
        if denom == 0.0 {
            0.0
        } else {
            overlap / denom
        }
    }
}

fn normalize_tokens(text: &str) -> std::collections::HashSet<String> {
    text.split_whitespace()
        .map(|t| {
            t.trim_matches(|c: char| !c.is_alphanumeric())
                .to_lowercase()
        })
        .filter(|t| !t.is_empty())
        .collect()
}

fn axis_position(layer: LayerType) -> f32 {
    match layer {
        LayerType::Customer => -1.0,
        LayerType::Consumer => -0.33,
        LayerType::Execution => 0.33,
        LayerType::Stability => 1.0,
    }
}

fn cosine_from_tokens(a: &str, b: &str, a_len: usize, b_len: usize) -> f32 {
    let mut a_freq: HashMap<String, f32> = HashMap::new();
    let mut b_freq: HashMap<String, f32> = HashMap::new();

    for token in a
        .split_whitespace()
        .map(normalize_token)
        .filter(|t| !t.is_empty())
    {
        *a_freq.entry(token).or_insert(0.0) += 1.0;
    }
    for token in b
        .split_whitespace()
        .map(normalize_token)
        .filter(|t| !t.is_empty())
    {
        *b_freq.entry(token).or_insert(0.0) += 1.0;
    }

    if a_freq.is_empty() || b_freq.is_empty() {
        return 0.0;
    }

    let mut dot = 0.0;
    for (token, a_value) in &a_freq {
        if let Some(b_value) = b_freq.get(token) {
            dot += a_value * b_value;
        }
    }

    let a_len_f = (a_len.max(1)) as f32;
    let b_len_f = (b_len.max(1)) as f32;
    let a_norm = (a_freq.values().map(|v| v * v).sum::<f32>() / a_len_f).sqrt();
    let b_norm = (b_freq.values().map(|v| v * v).sum::<f32>() / b_len_f).sqrt();
    if a_norm == 0.0 || b_norm == 0.0 {
        0.0
    } else {
        (dot / (a_norm * b_norm)).clamp(0.0, 1.0)
    }
}

fn normalize_token(token: &str) -> String {
    token
        .trim_matches(|c: char| !c.is_alphanumeric())
        .to_lowercase()
}

#[cfg(test)]
mod tests {
    use super::RustCausalMemory;

    #[test]
    fn allows_linear_transitions_and_stabilization() {
        let mut memory = RustCausalMemory::new();
        let customer = memory
            .add_intent(
                "Customer".to_string(),
                "mission resonance care balance self-love".to_string(),
            )
            .expect("add intent");
        let consumer = memory
            .transition_down(
                customer.clone(),
                "mission resonance care balance desire".to_string(),
                "Consumer".to_string(),
            )
            .expect("consumer transition");
        let execution = memory
            .transition_down(
                consumer.clone(),
                "mission resonance care balance execution plan".to_string(),
                "Execution".to_string(),
            )
            .expect("execution transition");
        let stability = memory
            .transition_down(
                execution.clone(),
                "mission resonance care balance stability monitor".to_string(),
                "Stability".to_string(),
            )
            .expect("stability transition");

        let score = memory
            .check_resonance(execution.clone())
            .expect("resonance");
        assert!(score > 0.0);
        assert!(memory.stabilize(stability.clone()).expect("stabilize"));
        assert_eq!(
            memory.get_axis_position(customer).expect("customer axis"),
            -1.0
        );
        assert_eq!(
            memory.get_axis_position(consumer).expect("consumer axis"),
            -0.33
        );
        assert_eq!(
            memory.get_axis_position(execution).expect("execution axis"),
            0.33
        );
        assert_eq!(memory.get_axis_position(stability).expect("axis"), 1.0);
    }

    #[test]
    fn blocks_low_resonance_transition() {
        let mut memory = RustCausalMemory::new();
        let customer = memory
            .add_intent("Customer".to_string(), "alpha beta gamma".to_string())
            .expect("add intent");

        let err = memory
            .transition_down(
                customer,
                "unrelated tokens only".to_string(),
                "Consumer".to_string(),
            )
            .expect_err("must reject low resonance");

        assert!(err.to_string().contains("ResonanceError"));
    }
}
