from __future__ import annotations

from typing import Any, Dict


class WhisperLoader:
    def load(self, config: Dict[str, Any]):
        from faster_whisper import WhisperModel

        return WhisperModel(
            config["path"],
            device=config.get("device", "cpu"),
            compute_type=config.get("quant", "int8"),
        )
