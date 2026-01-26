# SelfImprovingBrain V2

## Overview
The `SelfImprovingBrain` module enables the agent to learn from its interactions autonomously. It uses a non-blocking, background processing architecture to compute embeddings, store patterns in the Rust-optimized database, and perform periodic clustering/reindexing.

## Configuration
Configuration is loaded from `config/self_improving.yaml`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `batch_size` | 10 | Number of interactions to process in a single batch. |
| `cluster_interval` | 60 | Interval (in seconds) for background clustering/reindexing. |
| `embedding_provider` | "local" | "local" (uses internal embedder) or "remote" (external API). |
| `max_workers` | 2 | Number of background worker threads for processing embeddings. |
| `max_queue_size` | 1000 | Maximum number of items in the learning queue. |
| `storage_path` | "./data/patterns.db" | Path to the Rust storage database. |
| `embedding_dim` | 384 | Dimension of the embedding vectors. |

## API Usage

### Initialization
```python
from python.modules.self_improving import SelfImprovingBrain

brain = SelfImprovingBrain()
```

### Learning
Add a session (list of interactions) to the learning queue. This method is non-blocking.
```python
session_data = [
    {"question": "What is Rust?", "answer": "Rust is a systems programming language...", "timestamp": 1234567890},
    # ... more items
]
brain.learn_from_session(session_data)
```

### Searching
Find similar past interactions.
```python
results = brain.search_similar("Tell me about memory safety", k=3)
for res in results:
    print(f"Found: {res['question']} (Score: {res.get('score', 0)})")
```

### Status
Get current metrics.
```python
stats = brain.status()
print(f"Processed: {stats['processed']}, Queue: {stats['queue_size']}")
```

### Stopping
Stop background threads gracefully.
```python
brain.stop()
```

## Architecture
- **Facade Pattern**: `python/modules/self_improving.py` wraps the new V2 implementation to maintain backward compatibility.
- **Background Workers**: Embeddings are computed in separate threads to avoid blocking the main application loop.
- **Rust Integration**: Leverages `RustOptimizer` for efficient storage and pattern matching. Fallback to JSONL if Rust is unavailable.
- **Clustering**: A dedicated background thread triggers `reindex()` on the Rust core periodically.
