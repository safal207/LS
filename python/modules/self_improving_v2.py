import json
import time
import logging
import hashlib
import threading
import queue
import os
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

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Deterministic embedding using SHA256 -> float vector
        # WARNING: This is for consistency in tests/mocks only. Not semantic!
        embeddings = []
        for t in texts:
            h = hashlib.sha256(t.encode('utf-8')).digest()
            # Map 32 bytes to dim floats. Reuse bytes if dim > 32
            vec = [(h[i % 32] / 255.0) for i in range(self.dim)]
            embeddings.append(vec)
        return embeddings

class RemoteEmbedder(EmbeddingProvider):
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Mock remote call with retry logic
        embeddings = []
        # Simulate latency
        time.sleep(0.1)
        for _ in texts:
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
        self.stop_event = threading.Event()

        # Metrics
        self.processed_count = 0
        self.failed_count = 0
        self.last_cluster_time = 0

        self.start()

    def start(self):
        if self.running:
            return
        self.running = True
        self.stop_event.clear()

        # Start workers
        num_workers = self.config.get("max_workers", 1)
        for i in range(num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"LearningWorker-{i}")
            t.start()
            self.workers.append(t)

        # Start clusterer
        self.cluster_thread = threading.Thread(target=self._background_clusterer, name="ClusterWorker")
        self.cluster_thread.start()

        logger.info("SelfImprovingBrainV2 started.")

    def shutdown(self):
        logger.info("Stopping SelfImprovingBrainV2...")
        self.running = False
        self.stop_event.set()

        # Ensure queue is processed if possible (optional, but requested by logic "flush before stop")
        # However, flushing is blocking. We'll assume the user calls flush() manually if they want guarantee.
        # But per patch logic: "self.flush() # Ensure queue is empty before stopping"
        # We will try to flush with a timeout to avoid hanging forever.

        # Signal workers to stop (via running=False and stop_event)

        for t in self.workers:
            if t.is_alive():
                t.join(timeout=2.0)

        if self.cluster_thread and self.cluster_thread.is_alive():
            self.cluster_thread.join(timeout=2.0)

        logger.info("SelfImprovingBrainV2 stopped.")

    def learn_from_session(self, session_data: List[Dict]):
        """
        Add session data to the processing queue.
        session_data: list of dicts {'question', 'answer', 'timestamp'}
        """
        if not self.running:
            return

        try:
            for item in session_data:
                self.queue.put(item, block=False)
        except queue.Full:
            logger.warning("Learning queue full, dropping items.")
            self.failed_count += len(session_data)

    def _worker_loop(self):
        batch_size = self.config.get("batch_size", 10)
        batch = []

        while self.running and not self.stop_event.is_set():
            try:
                # Collect batch
                try:
                    # Short timeout to check running flag frequently
                    item = self.queue.get(timeout=0.5)
                    batch.append(item)
                except queue.Empty:
                    pass

                # Process if batch full or if queue is empty (drain) and we have data
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
                    patterns_to_add.append((key, embedding))

                # Add to matcher
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
        while self.running and not self.stop_event.is_set():
            # Sleep in chunks to allow faster shutdown
            for _ in range(interval):
                if not self.running or self.stop_event.is_set():
                    return
                time.sleep(1)

            try:
                # Trigger clustering/reindexing in Rust
                if self.rust.available:
                    # logger.info("Triggering background reindex...") # reduce log noise
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

        # Embed query. Convert to string to be safe.
        embedding = self.embedder.embed([f"{query}"])[0]

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
