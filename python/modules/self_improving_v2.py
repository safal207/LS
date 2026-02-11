import json
import time
import logging
import hashlib
import threading
import queue
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..rust_bridge import RustOptimizer

logger = logging.getLogger("SelfImprovingV2")

# --- Config Loader (Robust) ---
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
        return defaults

    config = defaults.copy()
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or ':' not in line:
                    continue

                key, val = line.split(':', 1)
                key = key.strip()
                val = val.split('#')[0].strip() # Remove comments

                # Simple type casting
                if val.isdigit():
                    val = int(val)
                elif val.lower() == 'true':
                    val = True
                elif val.lower() == 'false':
                    val = False
                elif val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]

                if key in config:
                    config[key] = val
    except Exception as e:
        logger.error(f"Config load error: {e}")

    return config

# --- Embedders ---
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]: pass

class LocalEmbedder(EmbeddingProvider):
    def __init__(self, dim: int = 384): self.dim = dim
    def embed(self, texts: List[str]) -> List[List[float]]:
        # Deterministic Mock (SHA256)
        embeddings = []
        for t in texts:
            h = hashlib.sha256(t.encode('utf-8')).digest()
            vec = [(h[i % 32] / 255.0) for i in range(self.dim)]
            embeddings.append(vec)
        return embeddings

class RemoteEmbedder(EmbeddingProvider):
    def __init__(self, dim: int = 384): self.dim = dim
    def embed(self, texts: List[str]) -> List[List[float]]:
        time.sleep(0.1) # Mock latency
        return [[0.0] * self.dim for _ in texts]

# --- Main V2 Class ---
class SelfImprovingBrainV2:
    def __init__(self, config_path: str = "config/self_improving.yaml", rust_instance=None):
        self.config = load_config(config_path)
        self.rust = rust_instance if rust_instance else RustOptimizer(
            db_path=self.config.get("storage_path", "./data/patterns.db")
        )

        # Select Embedder
        if self.config.get("embedding_provider") == "remote":
            self.embedder = RemoteEmbedder(self.config.get("embedding_dim"))
        else:
            self.embedder = LocalEmbedder(self.config.get("embedding_dim"))

        # Thread-safe Queue
        self.queue = queue.Queue(maxsize=self.config.get("max_queue_size", 1000))

        # Metrics Lock
        self.lock = threading.Lock()
        self.processed_count = 0
        self.failed_count = 0
        self.last_cluster_time = 0

        # Lifecycle
        self.stop_event = threading.Event()
        self.workers = []
        self.start()

    def start(self):
        self.stop_event.clear()

        # Start Workers
        for i in range(self.config.get("max_workers", 1)):
            t = threading.Thread(target=self._worker_loop, name=f"Worker-{i}")
            t.start()
            self.workers.append(t)

        # Start Clusterer
        self.cluster_thread = threading.Thread(target=self._background_clusterer, name="ClusterWorker")
        self.cluster_thread.start()

        logger.info("SelfImprovingBrainV2 Active.")

    def shutdown(self):
        logger.info("Stopping V2...")
        # 1. Stop accepting new tasks (implicit by caller stopping)
        # 2. Process remaining items
        self.flush()

        # 3. Signal stop
        self.stop_event.set()

        for t in self.workers:
            t.join(timeout=2.0)

        if self.cluster_thread:
            self.cluster_thread.join(timeout=2.0)

        logger.info("V2 Stopped.")

    def learn_from_session(self, session_data: List[Dict]):
        if self.stop_event.is_set():
            return

        dropped = 0
        for item in session_data:
            try:
                self.queue.put(item, block=False)
            except queue.Full:
                dropped += 1

        if dropped > 0:
            with self.lock:
                self.failed_count += dropped
            logger.warning(f"Queue full. Dropped {dropped} items.")

    def _worker_loop(self):
        batch_size = self.config.get("batch_size", 10)
        batch = []

        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                try:
                    item = self.queue.get(timeout=0.5)
                    batch.append(item)
                except queue.Empty:
                    # If queue empty and we have a partial batch, process it
                    if batch:
                        self._process_batch(batch)
                        batch = []
                    continue

                if len(batch) >= batch_size:
                    self._process_batch(batch)
                    batch = []

            except Exception as e:
                logger.error(f"Worker Error: {e}")

        # Final cleanup
        if batch:
            self._process_batch(batch)

    def _process_batch(self, batch: List[Dict]):
        if not batch:
            return
        try:
            texts = [f"Q: {i.get('question','')} A: {i.get('answer','')}" for i in batch]
            embeddings = self.embedder.embed(texts)

            if self.rust.available:
                patterns = []
                for idx, item in enumerate(batch):
                    key = f"pat_{int(item.get('timestamp', time.time()))}_{idx}"
                    # Rust save data
                    self.rust.save_to_storage(key, json.dumps(item).encode('utf-8'))
                    # Rust add vector
                    patterns.append(embeddings[idx])

                self.rust.add_patterns(patterns)
            else:
                self._fallback_save(batch)

            # Atomic update
            with self.lock:
                self.processed_count += len(batch)

            # Mark tasks as done for queue.join()
            for _ in batch:
                self.queue.task_done()

        except Exception as e:
            logger.error(f"Batch Failed: {e}")
            with self.lock:
                self.failed_count += len(batch)
            # Ensure task_done called even on failure
            for _ in batch:
                try:
                    self.queue.task_done()
                except ValueError:
                    pass

    def _fallback_save(self, batch):
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/learning_fallback.jsonl", "a") as f:
                for item in batch:
                    f.write(json.dumps(item) + "\n")
        except Exception:
            pass

    def _background_clusterer(self):
        interval = max(1, self.config.get("cluster_interval", 60))
        while not self.stop_event.is_set():
            # Sleep in small chunks to react to stop_event
            for _ in range(interval):
                if self.stop_event.is_set():
                    return
                time.sleep(1)

            if self.rust.available and hasattr(self.rust, 'reindex'):
                try:
                    self.rust.reindex()
                    self.last_cluster_time = time.time()
                except Exception:
                    pass

    def flush(self):
        """Blocks until all items in queue are processed."""
        self.queue.join()

    def status(self):
        with self.lock:
            return {
                "queue": self.queue.qsize(),
                "processed": self.processed_count,
                "failed": self.failed_count,
                "rust": self.rust.available
            }

    def search_similar(self, query: str, k: int = 5):
        if not self.rust.available:
            return []
        embedding = self.embedder.embed([f"{query}"])[0]
        results = self.rust.find_similar(embedding, k)

        # Mock decoding logic (assuming Rust returns IDs, need to fetch Data)
        # For now just return raw results or empty list if no data fetching implemented
        return results
