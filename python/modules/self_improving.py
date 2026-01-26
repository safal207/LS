import logging
from ..rust_bridge import RustOptimizer
from .self_improving_v2 import SelfImprovingBrainV2

logger = logging.getLogger("SelfImproving")

class SelfImprovingBrain:
    """
    Facade for SelfImprovingBrainV2.
    Maintains backward compatibility while leveraging the new V2 architecture.
    """
    def __init__(self, rust_instance=None):
        self.rust = rust_instance if rust_instance else RustOptimizer()
        # Initialize V2 with the shared Rust instance
        self.v2 = SelfImprovingBrainV2(rust_instance=self.rust)

    def learn_from_session(self, session_data):
        """
        Delegate to V2 (Non-blocking queue).
        session_data: list of dicts {'question', 'answer', 'timestamp'}
        """
        self.v2.learn_from_session(session_data)

    def optimize_memory(self):
        """
        Legacy method. V2 handles optimization in background.
        We trigger reindex and return optimization result for compatibility.
        """
        if self.rust.available:
            if hasattr(self.rust, 'reindex'):
                self.rust.reindex()
            return self.rust.optimize_memory()
        return 0

    def stop(self):
        """Stops the underlying V2 background threads."""
        # Maps facade .stop() to V2 .shutdown()
        self.v2.shutdown()

    def status(self):
        """Returns status from V2."""
        return self.v2.status()

    def search_similar(self, query, k=5):
        """New V2 method exposed."""
        return self.v2.search_similar(query, k)

    def flush(self):
        """Wait for processing to complete."""
        self.v2.flush()
