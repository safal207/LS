import time
import sys
import os
import random
import math

# Add root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from python.rust_bridge import RustOptimizer

def cosine_similarity_py(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def benchmark_pattern_matching():
    print("\n--- Benchmarking Pattern Matching (Python vs Rust) ---")
    rust = RustOptimizer()
    if not rust.available:
        print("Rust core not available. Skipping benchmark.")
        return

    # Generate data
    num_patterns = 10000
    dim = 384
    print(f"Generating {num_patterns} patterns of dimension {dim}...")
    patterns = [[random.random() for _ in range(dim)] for _ in range(num_patterns)]
    query = [random.random() for _ in range(dim)]

    # Load into Rust
    print("Loading patterns into Rust...")
    start_load = time.time()
    rust.add_patterns(patterns)
    print(f"Rust Load Time: {time.time() - start_load:.4f}s")

    # Benchmark Rust
    print("Running Rust search...")
    start_rust = time.time()
    rust.find_similar(query, k=5)
    rust_time = time.time() - start_rust
    print(f"Rust Search Time: {rust_time:.4f}s")

    # Benchmark Python
    print("Running Python search (Linear scan)...")
    start_py = time.time()
    # Simple linear scan top-k
    results = []
    for i, p in enumerate(patterns):
        sim = cosine_similarity_py(query, p)
        results.append((i, sim))
    results.sort(key=lambda x: x[1], reverse=True)
    _ = results[:5]
    py_time = time.time() - start_py
    print(f"Python Search Time: {py_time:.4f}s")

    speedup = py_time / rust_time if rust_time > 0 else 0
    print(f"\nSpeedup: {speedup:.1f}x 🚀")

    if speedup > 10:
        print("SUCCESS: Rust optimization confirmed!")
    else:
        print("WARNING: Speedup lower than expected.")

if __name__ == "__main__":
    benchmark_pattern_matching()
