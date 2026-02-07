from __future__ import annotations

from typing import Any, Dict


class VADLoader:
    def load(self, config: Dict[str, Any]):
        import torch

        model, _utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
        )
        return model
