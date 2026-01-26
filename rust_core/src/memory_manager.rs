use pyo3::prelude::*;
use lru::LruCache;
use std::num::NonZeroUsize;

#[pyclass]
pub struct MemoryManager {
    cache: LruCache<String, Vec<f32>>,
    max_size_mb: usize,
}

#[pymethods]
impl MemoryManager {
    #[new]
    pub fn new(max_size_mb: usize) -> Self {
        // Approximate capacity based on vector size (assuming 384 floats * 4 bytes + overhead)
        // This is a rough heuristic.
        let estimated_entry_size = 384 * 4 + 100; // 1.5KB approx
        let capacity = (max_size_mb * 1024 * 1024) / estimated_entry_size;

        let cap = NonZeroUsize::new(capacity).unwrap_or(NonZeroUsize::new(100).unwrap());

        MemoryManager {
            cache: LruCache::new(cap),
            max_size_mb,
        }
    }

    #[pyo3(name = "cache_pattern")]
    pub fn cache_pattern(&mut self, key: String, data: Vec<f32>) {
        self.cache.put(key, data);
    }

    #[pyo3(name = "get_pattern")]
    pub fn get_pattern(&mut self, key: String) -> Option<Vec<f32>> {
        self.cache.get(&key).cloned()
    }

    #[pyo3(name = "optimize")]
    pub fn optimize(&mut self) -> usize {
        // In a real scenario with a custom allocator or more complex structures,
        // this would do compaction. Here we just return the current size
        // relative to max to simulate "freed" space calculation or management.
        // For the sake of the demo, let's say we clear 10% of least used if full?
        // Or simply return how much space is left.

        let current_len = self.cache.len();
        let cap = self.cache.cap().get();

        if current_len > (cap * 9 / 10) {
             // Prune 10%
             let to_remove = cap / 10;
             for _ in 0..to_remove {
                 self.cache.pop_lru();
             }
             return to_remove * 1500; // approx bytes freed
        }
        0
    }
}
