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
        self.transport = None

        if ghostgpt_core is None:
            logger.warning("🦀 ghostgpt_core not available at module import time.")
            return

        try:
            self.memory = ghostgpt_core.MemoryManager(max_size_mb=memory_mb)
            self.matcher = ghostgpt_core.PatternMatcher()

            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.storage = ghostgpt_core.Storage(db_path)
            self.transport = ghostgpt_core.TransportHandle(
                ghostgpt_core.TransportConfig()
            )

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

    def transport_available(self) -> bool:
        return self.available and self.transport is not None

    def open_channel(self, kind: str, session_id: int | None = None) -> int | None:
        if self.transport_available():
            try:
                return self.transport.open_channel(kind, session_id)
            except Exception as e:
                logger.error(f"Rust Transport open_channel error: {e}")
        return None

    def bind_channel(self, channel: int, session_id: int) -> bool:
        if self.transport_available():
            try:
                self.transport.bind_channel(channel, session_id)
                return True
            except Exception as e:
                logger.error(f"Rust Transport bind_channel error: {e}")
        return False

    def send(self, channel: int, payload: bytes) -> bool:
        if self.transport_available():
            try:
                self.transport.send(channel, payload)
                return True
            except Exception as e:
                logger.error(f"Rust Transport send error: {e}")
        return False

    def receive(self, channel: int) -> bytes | None:
        if self.transport_available():
            try:
                return self.transport.receive(channel)
            except Exception as e:
                logger.error(f"Rust Transport receive error: {e}")
        return None

    def queue_len(self, channel: int) -> int:
        if self.transport_available():
            try:
                return self.transport.queue_len(channel)
            except Exception as e:
                logger.error(f"Rust Transport queue_len error: {e}")
        return 0

    def drain(self, channel: int, max_items: int | None = None) -> list[bytes]:
        if self.transport_available():
            try:
                return self.transport.drain(channel, max_items)
            except Exception as e:
                logger.error(f"Rust Transport drain error: {e}")
        return []

    def close_channel(self, channel: int) -> bool:
        if self.transport_available():
            try:
                self.transport.close_channel(channel)
                return True
            except Exception as e:
                logger.error(f"Rust Transport close_channel error: {e}")
        return False

    def clear_channel(self, channel: int) -> int:
        if self.transport_available():
            try:
                return self.transport.clear_channel(channel)
            except Exception as e:
                logger.error(f"Rust Transport clear_channel error: {e}")
        return 0

    def create_session(self, peer_id: str) -> int | None:
        if self.transport_available():
            try:
                return self.transport.create_session(peer_id)
            except Exception as e:
                logger.error(f"Rust Transport create_session error: {e}")
        return None

    def handshake(self, session_id: int, challenge: bytes) -> bytes | None:
        if self.transport_available():
            try:
                return self.transport.handshake(session_id, challenge)
            except Exception as e:
                logger.error(f"Rust Transport handshake error: {e}")
        return None

    def heartbeat(self, session_id: int) -> bool:
        if self.transport_available():
            try:
                return self.transport.heartbeat(session_id)
            except Exception as e:
                logger.error(f"Rust Transport heartbeat error: {e}")
        return False

    def session_info(self, session_id: int):
        if self.transport_available():
            try:
                return self.transport.session_info(session_id)
            except Exception as e:
                logger.error(f"Rust Transport session_info error: {e}")
        return None

    def list_sessions(self):
        if self.transport_available():
            try:
                return self.transport.list_sessions()
            except Exception as e:
                logger.error(f"Rust Transport list_sessions error: {e}")
        return []

    def channel_info(self, channel: int):
        if self.transport_available():
            try:
                return self.transport.channel_info(channel)
            except Exception as e:
                logger.error(f"Rust Transport channel_info error: {e}")
        return None

    def channel_stats(self, channel: int):
        if self.transport_available():
            try:
                return self.transport.channel_stats(channel)
            except Exception as e:
                logger.error(f"Rust Transport channel_stats error: {e}")
        return None

    def list_channels(self):
        if self.transport_available():
            try:
                return self.transport.list_channels()
            except Exception as e:
                logger.error(f"Rust Transport list_channels error: {e}")
        return []

    def list_channel_stats(self):
        if self.transport_available():
            try:
                return self.transport.list_channel_stats()
            except Exception as e:
                logger.error(f"Rust Transport list_channel_stats error: {e}")
        return []

    def transport_snapshot(self) -> dict:
        if not self.transport_available():
            return {"available": False, "sessions": [], "channels": []}
        try:
            return {
                "available": True,
                "sessions": self.transport.list_sessions(),
                "channels": self.transport.list_channel_stats(),
            }
        except Exception as e:
            logger.error(f"Rust Transport transport_snapshot error: {e}")
            return {"available": False, "sessions": [], "channels": []}

    def prune_sessions(self) -> int:
        if self.transport_available():
            try:
                return self.transport.prune_sessions()
            except Exception as e:
                logger.error(f"Rust Transport prune_sessions error: {e}")
        return 0

    def close_session(self, session_id: int) -> bool:
        if self.transport_available():
            try:
                self.transport.close_session(session_id)
                return True
            except Exception as e:
                logger.error(f"Rust Transport close_session error: {e}")
        return False
