import time
import logging
from ..rust_bridge import RustOptimizer

logger = logging.getLogger("AdaptiveBrain")

class AdaptiveBrain:
    def __init__(self, tier="local", api_keys=None, rust_instance=None, learner_instance=None):
        self.tier = tier
        self.api_keys = api_keys or {}
        self.rust = rust_instance if rust_instance else RustOptimizer()

        # ✅ LAZY IMPORT v2: Безопасная загрузка
        try:
            from .hexagon_core.capu_v2 import CaPU
        except ImportError:
            from .hexagon_core.capu import CaPU

        # ✅ SINGLE INIT: Инициализируем CaPU только один раз
        self.capu = CaPU(memory_module=learner_instance)
        self.latency_stats = []

    def generate(self, prompt, context_data=None):
        start_time = time.time()

        # 1. Update history (user)
        try:
            self.capu.update_history("user", prompt)
        except Exception:
            pass

        # 2. Build context ONCE
        full_prompt = self.capu.construct_prompt(prompt)

        # 3. Inference
        response = self._inference_strategy(full_prompt)

        # 4. Update history (AI)
        try:
            self.capu.update_history("ai", response)
        except Exception:
            pass

        # 5. Latency
        self.latency_stats.append(time.time() - start_time)

        return response

    def _inference_strategy(self, prompt):
        return "Simulated AI Response"
