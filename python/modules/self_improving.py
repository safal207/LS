from ..rust_bridge import RustOptimizer
import json
import time
import logging

logger = logging.getLogger("SelfImproving")

class SelfImprovingBrain:
    def __init__(self, rust_instance=None):
        self.rust = rust_instance if rust_instance else RustOptimizer()

    def learn_from_session(self, session_data):
        """
        Analyze session data and store valuable patterns.
        session_data: list of dicts {'question', 'answer', 'timestamp'}
        """
        if not self.rust.available:
            logger.info("Rust core unavailable, skipping optimized learning.")
            return

        logger.info(f"Learning from {len(session_data)} interactions...")

        for item in session_data:
            key = f"pattern_{int(item['timestamp'])}"
            # In a real system, we would compute an embedding here.
            # For now, we store the raw data in the efficient Rust storage.

            data_bytes = json.dumps(item).encode('utf-8')
            try:
                self.rust.save_to_storage(key, data_bytes)
                # Mock embedding for cache (random or simple hash for demo)
                # self.rust.cache_pattern(key, [0.1] * 384)
            except Exception as e:
                logger.error(f"Failed to save pattern: {e}")

        # Trigger memory optimization
        freed = self.rust.optimize_memory()
        logger.info(f"Memory optimization complete. Freed virtual units: {freed}")
