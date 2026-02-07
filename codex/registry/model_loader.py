from __future__ import annotations

from typing import Any, Dict


class ModelLoader:
    """Default loader for model types.

    This is a lightweight placeholder loader meant to be extended with
    real model initialization logic in future iterations.
    """

    def load_llm(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": "llm", "config": config}

    def load_stt(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": "stt", "config": config}

    def load_vad(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": "vad", "config": config}

    def load_embeddings(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": "embeddings", "config": config}

    def load_custom(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": "custom", "config": config}
