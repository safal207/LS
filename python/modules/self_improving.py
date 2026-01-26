import logging
from .self_improving_v2 import SelfImprovingBrainV2
from ..rust_bridge import RustOptimizer

logger = logging.getLogger("SelfImproving")

class SelfImprovingBrain:
    """
    Facade for SelfImprovingBrainV2.
    Maintains backward compatibility while leveraging the new V2 architecture.
    """
    def __init__(self, rust_instance=None):
        # Initialize V2. It will handle its own threads and config.
        self.v2 = SelfImprovingBrainV2(rust_instance=rust_instance)
        # Expose rust instance as legacy consumers might expect it
        self.rust = self.v2.rust

    def learn_from_session(self, session_data):
        """
        Delegates to V2 implementation.
        session_data: list of dicts {'question', 'answer', 'timestamp'}
        """
        self.v2.learn_from_session(session_data)

    def optimize_memory(self):
        """
        Legacy method. V2 handles optimization in background.
        We trigger reindex and return optimization result for compatibility.
        """
        if self.v2.rust.available:
            self.v2.rust.reindex()
            return self.v2.rust.optimize_memory()
        return 0

    def stop(self):
        """Stops the underlying V2 background threads."""
        self.v2.stop()

    def status(self):
        """Returns status from V2."""
        return self.v2.status()

    def search_similar(self, query, k=5):
        """New V2 method exposed."""
        return self.v2.search_similar(query, k)

    def flush(self):
        """Wait for processing to complete."""
        self.v2.flush()
