#![allow(dead_code)]
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet, VecDeque};

const MAX_NODES: usize = 500;
const MAX_AGE_DAYS: i64 = 30;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalNode {
    pub id: String,
    #[serde(default)]
    pub thread_id: String,
    pub cause: String,
    pub solution: String,
    pub ts: String,
    pub lri_core: serde_json::Value,
    pub edges: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalEdge {
    pub from: String,
    pub to: String,
    pub weight: f64,
    pub relation: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct TemporalGraph {
    pub nodes: HashMap<String, TemporalNode>,
    pub edges: Vec<TemporalEdge>,
}

impl TemporalGraph {
    pub fn build_from_causal_memory(entries: &[serde_json::Value]) -> Self {
        let mut graph = Self::default();

        let mut by_thread: HashMap<String, Vec<(String, DateTime<Utc>)>> = HashMap::new();
        let mut ordered: Vec<(String, DateTime<Utc>, String, String, serde_json::Value)> =
            Vec::new();

        for entry in entries {
            let ts = entry
                .get("ts")
                .and_then(|v| v.as_str())
                .and_then(parse_ts)
                .unwrap_or_else(Utc::now);

            let cause = entry
                .get("cause")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .to_string();
            let solution = entry
                .get("solution")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .to_string();
            let lri_core = entry
                .get("lri_core")
                .cloned()
                .unwrap_or(serde_json::Value::Null);

            let thread_id = entry
                .get("ltp_trace")
                .and_then(|v| v.get("thread_id"))
                .and_then(|v| v.as_str())
                .or_else(|| {
                    entry
                        .get("lce")
                        .and_then(|v| v.get("memory"))
                        .and_then(|v| v.get("thread"))
                        .and_then(|v| v.as_str())
                })
                .unwrap_or("unknown");

            let node_id = format!("{}:{}", thread_id, ts.timestamp_millis());
            graph.nodes.insert(
                node_id.clone(),
                TemporalNode {
                    id: node_id.clone(),
                    thread_id: thread_id.to_string(),
                    cause: cause.clone(),
                    solution: solution.clone(),
                    ts: ts.to_rfc3339(),
                    lri_core,
                    edges: Vec::new(),
                },
            );

            by_thread
                .entry(thread_id.to_string())
                .or_default()
                .push((node_id.clone(), ts));
            ordered.push((node_id, ts, cause, solution, entry.clone()));
        }

        ordered.sort_by(|a, b| a.1.cmp(&b.1));

        for nodes in by_thread.values_mut() {
            nodes.sort_by(|a, b| a.1.cmp(&b.1));
            for pair in nodes.windows(2) {
                let (from, from_ts) = (&pair[0].0, pair[0].1);
                let (to, to_ts) = (&pair[1].0, pair[1].1);
                let delta = (to_ts - from_ts).num_seconds().unsigned_abs();
                let weight = 1.0 / (delta as f64 + 1.0);
                graph.add_edge(from, to, weight, "temporal");
            }
        }

        for i in 0..ordered.len() {
            for j in (i + 1)..ordered.len() {
                let (left_id, _left_ts, left_cause, left_solution, left_entry) = &ordered[i];
                let (right_id, _right_ts, right_cause, right_solution, right_entry) = &ordered[j];

                // causal: if solution of one appears in cause of another
                if contains_case_insensitive(right_cause, left_solution) {
                    graph.add_edge(left_id, right_id, 1.0, "causal");
                }
                if contains_case_insensitive(left_cause, right_solution) {
                    graph.add_edge(right_id, left_id, 1.0, "causal");
                }

                // resonance: cosine similarity over resonance_map.focus scalar -> 1.0 if both present, else 0.0
                let focus_a = extract_focus(left_entry);
                let focus_b = extract_focus(right_entry);
                if let (Some(a), Some(b)) = (focus_a, focus_b) {
                    let similarity = cosine_similarity_1d(a, b);
                    if similarity > 0.0 {
                        graph.add_edge(left_id, right_id, similarity, "resonance");
                        graph.add_edge(right_id, left_id, similarity, "resonance");
                    }
                }
            }
        }

        graph.apply_rolling_window();
        graph
    }

    pub fn add_entry(&mut self, entry: &serde_json::Value) {
        let Some((node_id, ts, thread_id, cause, solution, lri_core)) = parse_entry(entry) else {
            return;
        };

        self.nodes.insert(
            node_id.clone(),
            TemporalNode {
                id: node_id.clone(),
                thread_id: thread_id.clone(),
                cause: cause.clone(),
                solution: solution.clone(),
                ts: ts.to_rfc3339(),
                lri_core,
                edges: Vec::new(),
            },
        );

        let mut same_thread: Vec<(String, DateTime<Utc>)> = self
            .nodes
            .values()
            .filter_map(|node| {
                if node.thread_id == thread_id {
                    parse_ts(&node.ts).map(|node_ts| (node.id.clone(), node_ts))
                } else {
                    None
                }
            })
            .collect();
        same_thread.sort_by(|a, b| a.1.cmp(&b.1));

        if let Some(index) = same_thread.iter().position(|(id, _)| *id == node_id) {
            let predecessor = index.checked_sub(1).and_then(|i| same_thread.get(i));
            let successor = same_thread.get(index + 1);

            if let Some((pred_id, pred_ts)) = predecessor {
                let delta = (ts - *pred_ts).num_seconds().unsigned_abs();
                let weight = 1.0 / (delta as f64 + 1.0);
                self.add_edge(pred_id, &node_id, weight, "temporal");
            }

            if let Some((succ_id, succ_ts)) = successor {
                let delta = (*succ_ts - ts).num_seconds().unsigned_abs();
                let weight = 1.0 / (delta as f64 + 1.0);
                self.add_edge(&node_id, succ_id, weight, "temporal");

                if let Some((pred_id, _)) = predecessor {
                    self.edges.retain(|e| {
                        !(e.relation == "temporal" && e.from == *pred_id && e.to == *succ_id)
                    });
                }
            }
        }

        let focus_new = extract_focus(entry);
        let existing_ids: Vec<String> = self
            .nodes
            .keys()
            .filter(|id| **id != node_id)
            .cloned()
            .collect();

        for existing_id in existing_ids {
            let Some(existing_node) = self.nodes.get(&existing_id) else {
                continue;
            };
            let existing_solution = existing_node.solution.clone();
            let existing_cause = existing_node.cause.clone();
            let focus_existing = extract_focus(&serde_json::json!({
                "lri_core": existing_node.lri_core.clone()
            }));

            if contains_case_insensitive(&cause, &existing_solution) {
                self.add_edge(&existing_id, &node_id, 1.0, "causal");
            }
            if contains_case_insensitive(&existing_cause, &solution) {
                self.add_edge(&node_id, &existing_id, 1.0, "causal");
            }

            if let (Some(a), Some(b)) = (focus_new, focus_existing) {
                let similarity = cosine_similarity_1d(a, b);
                if similarity > 0.0 {
                    self.add_edge(&existing_id, &node_id, similarity, "resonance");
                    self.add_edge(&node_id, &existing_id, similarity, "resonance");
                }
            }
        }

        self.apply_rolling_window();
    }

    pub fn get_neighbors(&self, node_id: &str) -> Vec<String> {
        self.nodes
            .get(node_id)
            .map(|n| n.edges.clone())
            .unwrap_or_default()
    }

    pub fn shortest_path(&self, from: &str, to: &str) -> Option<Vec<String>> {
        if from == to {
            return Some(vec![from.to_string()]);
        }

        let mut queue = VecDeque::new();
        let mut visited = HashSet::new();
        let mut parent: HashMap<String, String> = HashMap::new();

        queue.push_back(from.to_string());
        visited.insert(from.to_string());

        while let Some(current) = queue.pop_front() {
            for edge in self
                .edges
                .iter()
                .filter(|e| e.from == current && e.relation == "temporal")
            {
                if !visited.contains(&edge.to) {
                    visited.insert(edge.to.clone());
                    parent.insert(edge.to.clone(), current.clone());
                    if edge.to == to {
                        let mut path = vec![to.to_string()];
                        let mut cursor = to.to_string();
                        while let Some(p) = parent.get(&cursor) {
                            path.push(p.clone());
                            cursor = p.clone();
                            if cursor == from {
                                break;
                            }
                        }
                        path.reverse();
                        return Some(path);
                    }
                    queue.push_back(edge.to.clone());
                }
            }
        }

        None
    }

    pub fn export_json(&self) -> serde_json::Value {
        serde_json::json!({
            "nodes": self.nodes,
            "edges": self.edges,
        })
    }

    fn add_edge(&mut self, from: &str, to: &str, weight: f64, relation: &str) {
        if self
            .edges
            .iter()
            .any(|e| e.from == from && e.to == to && e.relation == relation)
        {
            return;
        }

        self.edges.push(TemporalEdge {
            from: from.to_string(),
            to: to.to_string(),
            weight,
            relation: relation.to_string(),
        });

        if let Some(node) = self.nodes.get_mut(from) {
            if !node.edges.iter().any(|e| e == to) {
                node.edges.push(to.to_string());
            }
        }
    }

    pub(crate) fn apply_rolling_window(&mut self) {
        let cutoff = Utc::now() - chrono::Duration::days(MAX_AGE_DAYS);
        let mut dated_nodes: Vec<(String, DateTime<Utc>)> = self
            .nodes
            .values()
            .filter_map(|node| parse_ts(&node.ts).map(|ts| (node.id.clone(), ts)))
            .collect();
        dated_nodes.sort_by(|a, b| b.1.cmp(&a.1));

        let allowed: HashSet<String> = dated_nodes
            .iter()
            .filter(|(_, ts)| *ts >= cutoff)
            .take(MAX_NODES)
            .map(|(id, _)| id.clone())
            .collect();

        self.nodes.retain(|id, _| allowed.contains(id));
        self.edges
            .retain(|edge| allowed.contains(&edge.from) && allowed.contains(&edge.to));

        for node in self.nodes.values_mut() {
            node.edges.clear();
        }

        let edge_pairs: Vec<(String, String)> = self
            .edges
            .iter()
            .map(|edge| (edge.from.clone(), edge.to.clone()))
            .collect();
        for (from, to) in edge_pairs {
            if let Some(node) = self.nodes.get_mut(&from) {
                if !node.edges.iter().any(|e| e == &to) {
                    node.edges.push(to);
                }
            }
        }
    }
}

fn parse_entry(
    entry: &serde_json::Value,
) -> Option<(
    String,
    DateTime<Utc>,
    String,
    String,
    String,
    serde_json::Value,
)> {
    let ts = entry
        .get("ts")
        .and_then(|v| v.as_str())
        .and_then(parse_ts)
        .unwrap_or_else(Utc::now);

    let cause = entry
        .get("cause")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string();
    let solution = entry
        .get("solution")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string();
    let lri_core = entry
        .get("lri_core")
        .cloned()
        .unwrap_or(serde_json::Value::Null);

    let thread_id = entry
        .get("ltp_trace")
        .and_then(|v| v.get("thread_id"))
        .and_then(|v| v.as_str())
        .or_else(|| {
            entry
                .get("lce")
                .and_then(|v| v.get("memory"))
                .and_then(|v| v.get("thread"))
                .and_then(|v| v.as_str())
        })
        .unwrap_or("unknown")
        .to_string();

    let node_id = format!("{}:{}", thread_id, ts.timestamp_millis());
    Some((node_id, ts, thread_id, cause, solution, lri_core))
}

fn parse_ts(raw: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(raw)
        .map(|ts| ts.with_timezone(&Utc))
        .ok()
}

fn extract_focus(entry: &serde_json::Value) -> Option<f64> {
    entry
        .get("lri_core")
        .and_then(|v| v.get("resonance_map"))
        .and_then(|v| v.get("focus"))
        .and_then(|v| v.as_f64())
}

fn cosine_similarity_1d(a: f64, b: f64) -> f64 {
    let denom = (a.abs() * b.abs()).max(1e-12);
    let ratio = (a * b) / denom;
    ratio.clamp(0.0, 1.0)
}

fn contains_case_insensitive(haystack: &str, needle: &str) -> bool {
    if needle.trim().is_empty() {
        return false;
    }
    haystack.to_lowercase().contains(&needle.to_lowercase())
}

pub fn parse_causal_memory_yaml(content: &str) -> Vec<serde_json::Value> {
    content
        .lines()
        .filter_map(|line| line.trim().strip_prefix("- "))
        .filter_map(|line| serde_json::from_str::<serde_json::Value>(line).ok())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cmp::Ordering;

    #[test]
    fn builds_graph_and_finds_temporal_path() {
        let now = Utc::now();
        let entries = vec![
            serde_json::json!({"ts":(now - chrono::Duration::hours(2)).to_rfc3339(),"cause":"A","solution":"B","ltp_trace":{"thread_id":"thread-1"},"lri_core":{"resonance_map":{"focus":0.9}}}),
            serde_json::json!({"ts":(now - chrono::Duration::hours(1)).to_rfc3339(),"cause":"B issue","solution":"C","ltp_trace":{"thread_id":"thread-1"},"lri_core":{"resonance_map":{"focus":0.8}}}),
        ];

        let graph = TemporalGraph::build_from_causal_memory(&entries);
        assert_eq!(graph.nodes.len(), 2);
        assert!(graph.edges.iter().any(|e| e.relation == "temporal"));

        let ids: Vec<String> = graph.nodes.keys().cloned().collect();
        let start = ids
            .iter()
            .min_by(|a, b| {
                if a < b {
                    Ordering::Less
                } else {
                    Ordering::Greater
                }
            })
            .unwrap();
        let end = ids
            .iter()
            .max_by(|a, b| {
                if a < b {
                    Ordering::Less
                } else {
                    Ordering::Greater
                }
            })
            .unwrap();
        let path = graph.shortest_path(start, end);
        assert!(path.is_some());
    }

    #[test]
    fn test_causal_edge() {
        let now = Utc::now();
        let entries = vec![
            serde_json::json!({"ts":(now - chrono::Duration::hours(2)).to_rfc3339(),"cause":"Initial issue","solution":"Patch auth", "ltp_trace":{"thread_id":"t1"}}),
            serde_json::json!({"ts":(now - chrono::Duration::hours(1)).to_rfc3339(),"cause":"Need to apply patch auth soon","solution":"Done", "ltp_trace":{"thread_id":"t2"}}),
        ];

        let graph = TemporalGraph::build_from_causal_memory(&entries);
        assert!(graph.edges.iter().any(|e| e.relation == "causal"));
    }

    #[test]
    fn test_resonance_weight() {
        let now = Utc::now();
        let entries = vec![
            serde_json::json!({"ts":(now - chrono::Duration::hours(2)).to_rfc3339(),"cause":"A","solution":"B","ltp_trace":{"thread_id":"t1"},"lri_core":{"resonance_map":{"focus":0.8}}}),
            serde_json::json!({"ts":(now - chrono::Duration::hours(1)).to_rfc3339(),"cause":"C","solution":"D","ltp_trace":{"thread_id":"t2"},"lri_core":{"resonance_map":{"focus":0.9}}}),
        ];

        let graph = TemporalGraph::build_from_causal_memory(&entries);
        let resonance = graph
            .edges
            .iter()
            .find(|e| e.relation == "resonance")
            .expect("resonance edge should exist");
        assert!(resonance.weight > 0.0 && resonance.weight <= 1.0);
    }

    #[test]
    fn test_rolling_window_max_nodes() {
        let now = Utc::now();
        let entries: Vec<serde_json::Value> = (0..600)
            .map(|i| {
                serde_json::json!({
                    "ts": (now - chrono::Duration::minutes(i)).to_rfc3339(),
                    "cause": format!("cause-{i}"),
                    "solution": format!("solution-{i}"),
                    "ltp_trace": {"thread_id": "rolling"}
                })
            })
            .collect();

        let graph = TemporalGraph::build_from_causal_memory(&entries);
        assert!(graph.nodes.len() <= MAX_NODES);
    }

    #[test]
    fn test_build_from_empty_json() {
        let entries = vec![];
        let graph = TemporalGraph::build_from_causal_memory(&entries);
        assert_eq!(graph.nodes.len(), 0);
        assert_eq!(graph.edges.len(), 0);
    }

    #[test]
    fn test_build_from_minimal_json() {
        let entries = vec![serde_json::json!({})];
        let graph = TemporalGraph::build_from_causal_memory(&entries);
        assert_eq!(graph.nodes.len(), 1);
        assert_eq!(graph.edges.len(), 0);
        let node = graph.nodes.values().next().unwrap();
        assert_eq!(node.thread_id, "unknown");
        assert_eq!(node.cause, "");
        assert_eq!(node.solution, "");
    }
}
