import sys
import os
import time

# Add current directory (python/) to sys.path to find ghostgpt_core.so/.pyd
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import ghostgpt_core
except ImportError:
    # Fallback or error if not built
    print("WARNING: ghostgpt_core module not found. Building or check paths.")
    ghostgpt_core = None

class RustOptimizer:
    """Wrapper around Rust modules for memory and pattern matching."""

    def __init__(self, memory_mb=2000, db_path="./data/patterns.db"):
        if ghostgpt_core:
            self.memory = ghostgpt_core.MemoryManager(max_size_mb=memory_mb)
            self.matcher = ghostgpt_core.PatternMatcher()
            # Ensure data dir exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.storage = ghostgpt_core.Storage(db_path)
            self.available = True
        else:
            self.available = False
            self.memory = None
            self.matcher = None
            self.storage = None
            print("Rust core unavailable - running in pure Python mode (slower).")

    def cache_pattern(self, key: str, embedding: list):
        if self.available:
            self.memory.cache_pattern(key, embedding)

    def add_patterns(self, patterns: list):
        if self.available:
            self.matcher.add_patterns(patterns)

    def find_similar(self, query: list, k: int = 5):
        if self.available:
            return self.matcher.find_similar(query, k)
        return []

    def save_to_storage(self, key: str, data: bytes):
        if self.available:
            self.storage.save(key, data)

    def load_from_storage(self, key: str):
        if self.available:
            return self.storage.load(key)
        return None

    def optimize_memory(self):
        if self.available:
            freed = self.memory.optimize()
            return freed
        return 0

    def close(self):
        # Sled db flush/close happens on drop, but we can force flush
        if self.available and self.storage:
            try:
                self.storage.flush()
            except:
                pass
            # We rely on Rust Drop to close DB handle when object is deleted
