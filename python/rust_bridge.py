import sys
import os
import logging

logger = logging.getLogger(__name__)

# Try import at module level so import errors are visible once
try:
    import ghostgpt_core
    RUST_AVAILABLE = True
    logger.info("✅ Rust Core (ghostgpt_core) loaded successfully.")
except ImportError:
    ghostgpt_core = None
    RUST_AVAILABLE = False
    logger.warning("⚠️ Rust Core not found. Running in FALLBACK mode (Python only).")
except Exception as e:
    logger.error(f"Unexpected error importing ghostgpt_core: {e}")
    ghostgpt_core = None
    RUST_AVAILABLE = False

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

class RustOptimizer:
    """
    Robust Wrapper around Rust modules.
    Falls back to 'Silent Mode' if Rust is not available.
    """
    def __init__(self, memory_mb=2000, db_path="./data/patterns.db", transport_config=None):
        self.available = False
        self.memory = None
        self.matcher = None
        self.storage = None
        self.transport = None

        if ghostgpt_core is None:
            logger.warning("🦀 ghostgpt_core not available at module import time.")
            return

        try:
            self.memory = ghostgpt_core.MemoryManager(memory_mb)
            self.matcher = ghostgpt_core.PatternMatcher()

            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.storage = ghostgpt_core.Storage(db_path)
            transport_config = transport_config or {}
            transport = ghostgpt_core.TransportConfig(
                transport_config.get("heartbeat_ms"),
                transport_config.get("max_channels"),
                transport_config.get("max_queue_depth"),
                transport_config.get("max_payload_bytes"),
            )
            self.transport = ghostgpt_core.TransportHandle(transport)

            self.available = True
            logger.info(f"🦀 Rust Core Loaded. DB: {db_path}")

        except Exception as e:
            logger.error(f"🦀 Rust Initialization Failed: {e}")
            self.available = False

    def is_available(self) -> bool:
        return bool(self.available)

    def bridge_health(self) -> str:
        """
        Returns bridge health status.
        'OK' when Rust core is available, otherwise 'FALLBACK'.
        """
        return "OK" if self.available else "FALLBACK"

    def _log_unavailable(self, operation: str):
        logger.debug("Attempted '%s' but Rust is unavailable (fallback mode).", operation)

    def _log_transport_unavailable(self, operation: str):
        logger.debug("Attempted transport '%s' but Rust transport is unavailable (fallback mode).", operation)

    def cache_pattern(self, key: str, embedding: list) -> bool:
        if not self.available:
            self._log_unavailable("cache_pattern")
            return False
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
        if not self.available:
            self._log_unavailable("add_patterns")
            return False
        try:
            self.matcher.add_patterns(patterns)
            return True
        except Exception as e:
            logger.error(f"Rust Pattern Add Error: {e}")
            return False
        return False

    def find_similar(self, query: list, k: int = 5):
        if not self.available:
            self._log_unavailable("find_similar")
            return []
        try:
            return self.matcher.find_similar(query, k)
        except Exception as e:
            logger.error(f"Rust Search Error: {e}")
        return []

    def save_to_storage(self, key: str, data: bytes) -> bool:
        if not self.available:
            self._log_unavailable("save_to_storage")
            return False
        try:
            self.storage.save(key, data)
            return True
        except Exception as e:
            logger.error(f"Rust Save Error: {e}")
            return False
        return False

    def load_from_storage(self, key: str):
        if not self.available:
            self._log_unavailable("load_from_storage")
            return None
        try:
            return self.storage.load(key)
        except Exception as e:
            logger.error(f"Rust Load Error: {e}")
        return None

    def optimize_memory(self):
        if not self.available:
            self._log_unavailable("optimize_memory")
            return 0
        try:
            return self.memory.optimize()
        except Exception as e:
            logger.error(f"Rust Optimize Error: {e}")
        return 0

    def reindex(self) -> bool:
        if not self.available:
            self._log_unavailable("reindex")
            return False
        if not hasattr(self.matcher, 'reindex'):
            logger.debug("Attempted 'reindex' but matcher has no reindex method.")
            return False
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
        if not self.transport_available():
            self._log_transport_unavailable("open_channel")
            return None
        try:
            return self.transport.open_channel(kind, session_id)
        except Exception as e:
            logger.error(f"Rust Transport open_channel error: {e}")
        return None

    def bind_channel(self, channel: int, session_id: int) -> bool:
        if not self.transport_available():
            self._log_transport_unavailable("bind_channel")
            return False
        try:
            self.transport.bind_channel(channel, session_id)
            return True
        except Exception as e:
            logger.error(f"Rust Transport bind_channel error: {e}")
        return False

    def send(self, channel: int, payload: bytes) -> bool:
        if not self.transport_available():
            self._log_transport_unavailable("send")
            return False
        try:
            self.transport.send(channel, payload)
            return True
        except Exception as e:
            logger.error(f"Rust Transport send error: {e}")
        return False

    def receive(self, channel: int) -> bytes | None:
        if not self.transport_available():
            self._log_transport_unavailable("receive")
            return None
        try:
            return self.transport.receive(channel)
        except Exception as e:
            logger.error(f"Rust Transport receive error: {e}")
        return None

    def queue_len(self, channel: int) -> int:
        if not self.transport_available():
            self._log_transport_unavailable("queue_len")
            return 0
        try:
            return self.transport.queue_len(channel)
        except Exception as e:
            logger.error(f"Rust Transport queue_len error: {e}")
        return 0

    def drain(self, channel: int, max_items: int | None = None) -> list[bytes]:
        if not self.transport_available():
            self._log_transport_unavailable("drain")
            return []
        try:
            return self.transport.drain(channel, max_items)
        except Exception as e:
            logger.error(f"Rust Transport drain error: {e}")
        return []

    def close_channel(self, channel: int) -> bool:
        if not self.transport_available():
            self._log_transport_unavailable("close_channel")
            return False
        try:
            self.transport.close_channel(channel)
            return True
        except Exception as e:
            logger.error(f"Rust Transport close_channel error: {e}")
        return False

    def clear_channel(self, channel: int) -> int:
        if not self.transport_available():
            self._log_transport_unavailable("clear_channel")
            return 0
        try:
            return self.transport.clear_channel(channel)
        except Exception as e:
            logger.error(f"Rust Transport clear_channel error: {e}")
        return 0

    def create_session(self, peer_id: str) -> int | None:
        if not self.transport_available():
            self._log_transport_unavailable("create_session")
            return None
        try:
            return self.transport.create_session(peer_id)
        except Exception as e:
            logger.error(f"Rust Transport create_session error: {e}")
        return None

    def handshake(self, session_id: int, challenge: bytes) -> bytes | None:
        if not self.transport_available():
            self._log_transport_unavailable("handshake")
            return None
        try:
            return self.transport.handshake(session_id, challenge)
        except Exception as e:
            logger.error(f"Rust Transport handshake error: {e}")
        return None

    def heartbeat(self, session_id: int) -> bool:
        if not self.transport_available():
            self._log_transport_unavailable("heartbeat")
            return False
        try:
            return self.transport.heartbeat(session_id)
        except Exception as e:
            logger.error(f"Rust Transport heartbeat error: {e}")
        return False

    def session_info(self, session_id: int):
        if not self.transport_available():
            self._log_transport_unavailable("session_info")
            return None
        try:
            return self.transport.session_info(session_id)
        except Exception as e:
            logger.error(f"Rust Transport session_info error: {e}")
        return None

    def list_sessions(self):
        if not self.transport_available():
            self._log_transport_unavailable("list_sessions")
            return []
        try:
            return self.transport.list_sessions()
        except Exception as e:
            logger.error(f"Rust Transport list_sessions error: {e}")
        return []

    def channel_info(self, channel: int):
        if not self.transport_available():
            self._log_transport_unavailable("channel_info")
            return None
        try:
            return self.transport.channel_info(channel)
        except Exception as e:
            logger.error(f"Rust Transport channel_info error: {e}")
        return None

    def channel_stats(self, channel: int):
        if not self.transport_available():
            self._log_transport_unavailable("channel_stats")
            return None
        try:
            return self.transport.channel_stats(channel)
        except Exception as e:
            logger.error(f"Rust Transport channel_stats error: {e}")
        return None

    def list_channels(self):
        if not self.transport_available():
            self._log_transport_unavailable("list_channels")
            return []
        try:
            return self.transport.list_channels()
        except Exception as e:
            logger.error(f"Rust Transport list_channels error: {e}")
        return []

    def list_channel_stats(self):
        if not self.transport_available():
            self._log_transport_unavailable("list_channel_stats")
            return []
        try:
            return self.transport.list_channel_stats()
        except Exception as e:
            logger.error(f"Rust Transport list_channel_stats error: {e}")
        return []

    def transport_snapshot(self) -> dict:
        if not self.transport_available():
            self._log_transport_unavailable("transport_snapshot")
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
        if not self.transport_available():
            self._log_transport_unavailable("prune_sessions")
            return 0
        try:
            return self.transport.prune_sessions()
        except Exception as e:
            logger.error(f"Rust Transport prune_sessions error: {e}")
        return 0

    def close_session(self, session_id: int) -> bool:
        if not self.transport_available():
            self._log_transport_unavailable("close_session")
            return False
        try:
            self.transport.close_session(session_id)
            return True
        except Exception as e:
            logger.error(f"Rust Transport close_session error: {e}")
        return False
