use pyo3::prelude::*;
use rayon::prelude::*;

#[pyclass]
pub struct PatternMatcher {
    patterns: Vec<Vec<f32>>,
    ids: Vec<usize>, // Internal IDs to map back to original indices
}

#[pymethods]
impl PatternMatcher {
    #[new]
    pub fn new() -> Self {
        PatternMatcher {
            patterns: Vec::new(),
            ids: Vec::new(),
        }
    }

    #[pyo3(name = "add_patterns")]
    pub fn add_patterns(&mut self, new_patterns: Vec<Vec<f32>>) {
        let start_id = self.patterns.len();
        self.patterns.extend(new_patterns);
        for i in 0..self.patterns.len() - start_id {
            self.ids.push(start_id + i);
        }
    }

    #[pyo3(name = "clear")]
    pub fn clear(&mut self) {
        self.patterns.clear();
        self.ids.clear();
    }

    #[pyo3(name = "find_similar")]
    pub fn find_similar(
        &self,
        query: Vec<f32>,
        top_k: usize
    ) -> Vec<(usize, f32)> {
        let mut results: Vec<(usize, f32)> = self.patterns
            .par_iter()
            .enumerate()
            .map(|(idx, pattern)| {
                let sim = cosine_similarity(&query, pattern);
                (idx, sim) // Return index in the internal vector
            })
            .collect();

        // Sort by similarity descending
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(top_k);

        results
    }
}

#[inline]
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    let mut dot = 0.0;
    let mut norm_a = 0.0;
    let mut norm_b = 0.0;

    for (x, y) in a.iter().zip(b) {
        dot += x * y;
        norm_a += x * x;
        norm_b += y * y;
    }

    if norm_a == 0.0 || norm_b == 0.0 {
        return 0.0;
    }

    dot / (norm_a.sqrt() * norm_b.sqrt())
}
