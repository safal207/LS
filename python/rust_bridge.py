import sys
import os
import logging

logger = logging.getLogger("RustBridge")

# Try import at module level so import errors are visible once
try:
    import ghostgpt_core
except ImportError:
    ghostgpt_core = None
except Exception as e:
    logger.error(f"Unexpected error importing ghostgpt_core: {e}")
    ghostgpt_core = None

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

        if ghostgpt_core is None:
            logger.warning("🦀 ghostgpt_core not available at module import time.")
            return

        try:
            self.memory = ghostgpt_core.MemoryManager(max_size_mb=memory_mb)
            self.matcher = ghostgpt_core.PatternMatcher()

            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.storage = ghostgpt_core.Storage(db_path)

            self.available = True
            logger.info(f"🦀 Rust Core Loaded. DB: {db_path}")

        except Exception as e:
            logger.error(f"🦀 Rust Initialization Failed: {e}")
            self.available = False

    def is_available(self) -> bool:
        return bool(self.available)

    def cache_pattern(self, key: str, embedding: list) -> bool:
        if self.available:
            try:
                self.memory.cache_pattern(key, embedding)
                return True
            except Exception as e:
                logger.error(f"Rust Cache Error: {e}")
        return False

    def add_patterns(self, patterns: list) -> bool:
        """
        Add patterns to matcher.
        patterns: List of vectors (if Rust handles IDs internally) or List of (ID, Vector).
        """
        if self.available:
            try:
                self.matcher.add_patterns(patterns)
                return True
            except Exception as e:
                logger.error(f"Rust Pattern Add Error: {e}")
                return False
        return False

    def find_similar(self, query: list, k: int = 5):
        if self.available:
            try:
                return self.matcher.find_similar(query, k)
            except Exception as e:
                logger.error(f"Rust Search Error: {e}")
        return []

    def save_to_storage(self, key: str, data: bytes) -> bool:
        if self.available:
            try:
                self.storage.save(key, data)
                return True
            except Exception as e:
                logger.error(f"Rust Save Error: {e}")
                return False
        return False

    def load_from_storage(self, key: str):
        if self.available:
            try:
                return self.storage.load(key)
            except Exception as e:
                logger.error(f"Rust Load Error: {e}")
        return None

    def optimize_memory(self):
        if self.available:
            try:
                return self.memory.optimize()
            except Exception as e:
                logger.error(f"Rust Optimize Error: {e}")
        return 0

    def reindex(self) -> bool:
        if self.available and hasattr(self.matcher, 'reindex'):
            try:
                self.matcher.reindex()
                return True
            except Exception as e:
                logger.error(f"Rust Reindex Error: {e}")
        return False

    def close(self):
        if self.available and self.storage:
            try:
                self.storage.flush()
            except Exception:
                pass
