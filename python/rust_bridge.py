import sys
import os
import logging

logger = logging.getLogger("RustBridge")

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

class RustOptimizer:
    """
    Robust Wrapper around Rust modules.
    Falls back to 'Silent Mode' if Rust is not available.
    """
    def __init__(self, memory_mb=2000, db_path="./data/patterns.db"):
        self.available = False
        self.memory = None
        self.matcher = None
        self.storage = None

        try:
            import ghostgpt_core

            self.memory = ghostgpt_core.MemoryManager(max_size_mb=memory_mb)
            self.matcher = ghostgpt_core.PatternMatcher()

            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.storage = ghostgpt_core.Storage(db_path)

            self.available = True
            logger.info(f"🦀 Rust Core Loaded. DB: {db_path}")

        except ImportError:
            logger.warning("🦀 Rust Core NOT FOUND. Running in Python-only mode.")
        except Exception as e:
            logger.error(f"🦀 Rust Initialization Failed: {e}")
            self.available = False

    def cache_pattern(self, key: str, embedding: list):
        if self.available:
            try:
                self.memory.cache_pattern(key, embedding)
            except Exception:
                pass

    def add_patterns(self, patterns: list):
        if self.available:
            try:
                self.matcher.add_patterns(patterns)
            except Exception:
                pass

    def find_similar(self, query: list, k: int = 5):
        if self.available:
            try:
                return self.matcher.find_similar(query, k)
            except Exception:
                pass
        return []

    def save_to_storage(self, key: str, data: bytes):
        if self.available:
            try:
                self.storage.save(key, data)
            except Exception as e:
                logger.error(f"Rust Save Error: {e}")

    def load_from_storage(self, key: str):
        if self.available:
            try:
                return self.storage.load(key)
            except Exception:
                pass
        return None

    def optimize_memory(self):
        if self.available:
            try:
                return self.memory.optimize()
            except Exception:
                pass
        return 0

    def close(self):
        if self.available and self.storage:
            try:
                self.storage.flush()
            except Exception:
                pass
