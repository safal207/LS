import json
import time
import logging
import threading
import queue
import os
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

# Attempt to import numpy, handle if missing
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from ..rust_bridge import RustOptimizer

logger = logging.getLogger("SelfImprovingV2")

# --- Configuration Loading ---
def load_config(config_path: str = "config/self_improving.yaml") -> Dict[str, Any]:
    defaults = {
        "batch_size": 10,
        "cluster_interval": 60,
        "embedding_provider": "local",
        "max_workers": 2,
        "max_queue_size": 1000,
        "storage_path": "./data/patterns.db",
        "embedding_dim": 384
    }

    if not os.path.exists(config_path):
        logger.warning(f"Config file {config_path} not found. Using defaults.")
        return defaults

    try:
        # Simple YAML parser since PyYAML is not available
        config = defaults.copy()
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.split('#')[0].strip() # Remove comments

                    # Type conversion
                    if value.isdigit():
                        value = int(value)
                    elif value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    if key in config:
                        config[key] = value
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}. Using defaults.")
        return defaults

# --- Embedding Providers ---
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        pass

class LocalEmbedder(EmbeddingProvider):
    def __init__(self, dim: int = 384):
        self.dim = dim
        self.rng = random.Random(42)

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Mock implementation using random vectors or numpy if available
        embeddings = []
        for _ in texts:
            if HAS_NUMPY:
                vec = np.random.rand(self.dim).tolist()
            else:
                vec = [self.rng.random() for _ in range(self.dim)]
            embeddings.append(vec)
        return embeddings

class RemoteEmbedder(EmbeddingProvider):
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Mock remote call with retry logic
        # In a real scenario, this would call an API
        embeddings = []
        # Simulate latency
        time.sleep(0.1)
        for _ in texts:
            # Return dummy embeddings
            vec = [0.0] * self.dim
            embeddings.append(vec)
        return embeddings

# --- Main Module ---
class SelfImprovingBrainV2:
    def __init__(self, config_path: str = "config/self_improving.yaml", rust_instance=None):
        self.config = load_config(config_path)
        self.rust = rust_instance if rust_instance else RustOptimizer(
            db_path=self.config.get("storage_path", "./data/patterns.db")
        )

        provider_type = self.config.get("embedding_provider", "local")
        dim = self.config.get("embedding_dim", 384)
        if provider_type == "remote":
            self.embedder = RemoteEmbedder(dim)
        else:
            self.embedder = LocalEmbedder(dim)

        self.queue = queue.Queue(maxsize=self.config.get("max_queue_size", 1000))
        self.running = False
        self.workers = []
        self.cluster_thread = None

        # Metrics
        self.processed_count = 0
        self.failed_count = 0
        self.last_cluster_time = 0

        self.start()

    def start(self):
        if self.running:
            return
        self.running = True

        # Start workers
        num_workers = self.config.get("max_workers", 1)
        for _ in range(num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self.workers.append(t)

        # Start clusterer
        self.cluster_thread = threading.Thread(target=self._background_clusterer, daemon=True)
        self.cluster_thread.start()

        logger.info("SelfImprovingBrainV2 started.")

    def stop(self):
        self.running = False
        # Wait for queue to empty? Or just stop?
        # Typically we want to process remaining items if possible, but for shutdown speed we might just flag.
        for t in self.workers:
            t.join(timeout=1.0)
        if self.cluster_thread:
            self.cluster_thread.join(timeout=1.0)
        logger.info("SelfImprovingBrainV2 stopped.")

    def learn_from_session(self, session_data: List[Dict]):
        """
        Add session data to the processing queue.
        session_data: list of dicts {'question', 'answer', 'timestamp'}
        """
        try:
            for item in session_data:
                self.queue.put(item, block=False)
        except queue.Full:
            logger.warning("Learning queue full, dropping items.")
            self.failed_count += len(session_data)

    def _worker_loop(self):
        batch_size = self.config.get("batch_size", 10)
        batch = []

        while self.running:
            try:
                # Collect batch
                try:
                    item = self.queue.get(timeout=1.0)
                    batch.append(item)
                except queue.Empty:
                    pass

                if len(batch) >= batch_size or (batch and self.queue.empty()):
                    self._process_batch(batch)
                    batch = []

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                if batch:
                    self.failed_count += len(batch)
                    batch = []

    def _process_batch(self, batch: List[Dict]):
        if not batch:
            return

        try:
            # 1. Compute embeddings
            texts = [f"Q: {item.get('question', '')} A: {item.get('answer', '')}" for item in batch]
            embeddings = self.embedder.embed(texts)

            # 2. Store in Rust
            if self.rust.available:
                patterns_to_add = []
                for i, item in enumerate(batch):
                    key = f"pattern_{int(item.get('timestamp', time.time()))}_{i}"
                    embedding = embeddings[i]
                    data_bytes = json.dumps(item).encode('utf-8')

                    # Save raw data
                    self.rust.save_to_storage(key, data_bytes)

                    # Prepare for pattern matcher
                    # Assuming add_patterns takes list of tuples (id, vector)
                    patterns_to_add.append((key, embedding))

                self.rust.add_patterns(patterns_to_add)
            else:
                # Fallback to local file (e.g. JSONL)
                self._fallback_save(batch)

            self.processed_count += len(batch)

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            self.failed_count += len(batch)

    def _fallback_save(self, batch: List[Dict]):
        # Simple append to a jsonl file
        fallback_dir = "data"
        if not os.path.exists(fallback_dir):
            os.makedirs(fallback_dir)

        fallback_path = os.path.join(fallback_dir, "learning_fallback.jsonl")
        try:
            with open(fallback_path, 'a') as f:
                for item in batch:
                    f.write(json.dumps(item) + "\n")
        except Exception as e:
            logger.error(f"Fallback save failed: {e}")

    def _background_clusterer(self):
        interval = self.config.get("cluster_interval", 60)
        while self.running:
            # Sleep in chunks to allow faster shutdown
            for _ in range(interval):
                if not self.running:
                    return
                time.sleep(1)

            try:
                # Trigger clustering/reindexing in Rust
                if self.rust.available:
                    logger.info("Triggering background reindex...")
                    self.rust.reindex()
                    self.last_cluster_time = time.time()
            except Exception as e:
                logger.error(f"Clusterer error: {e}")

    def flush(self):
        """Wait until queue is empty."""
        while not self.queue.empty():
            time.sleep(0.1)
        # Give workers a moment to finish processing
        time.sleep(0.5)

    def status(self) -> Dict:
        return {
            "queue_size": self.queue.qsize(),
            "processed": self.processed_count,
            "failed": self.failed_count,
            "last_cluster": self.last_cluster_time,
            "rust_available": self.rust.available
        }

    def search_similar(self, query: str, k: int = 5) -> List[Dict]:
        """
        Search for similar patterns.
        """
        if not self.rust.available:
            return []

        # Embed query
        embedding = self.embedder.embed([query])[0]

        # Search Rust
        results = self.rust.find_similar(embedding, k)

        # Results might be list of (id, score). We need to load data.
        decoded_results = []
        if results:
            for res in results:
                try:
                    # Assuming result structure
                    if isinstance(res, (tuple, list)):
                        pid = res[0]
                        score = res[1] if len(res) > 1 else 0.0
                    else:
                        pid = res
                        score = 0.0

                    data_bytes = self.rust.load_from_storage(pid)
                    if data_bytes:
                        data = json.loads(data_bytes)
                        data['score'] = score
                        decoded_results.append(data)
                except Exception as e:
                    logger.warning(f"Failed to load result {res}: {e}")

        return decoded_results
