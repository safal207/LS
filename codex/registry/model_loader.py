from __future__ import annotations

import importlib.util
from typing import Any, Dict

from .loaders.llama_loader import LlamaLoader
from .loaders.phi_loader import PhiLoader
from .loaders.qwen_loader import QwenLoader
from .loaders.vad_loader import VADLoader
from .loaders.whisper_loader import WhisperLoader


class ModelLoader:
    """Loader routing for registry-backed models."""

    def __init__(self) -> None:
        self.whisper = WhisperLoader()
        self.vad = VADLoader()
        self.phi = PhiLoader()
        self.qwen = QwenLoader()
        self.llama = LlamaLoader()

    def load_llm(self, config: Dict[str, Any]) -> Any:
        name = config["path"].lower()
        if "phi" in name:
            return self.phi.load(config)
        if "qwen" in name:
            return self.qwen.load(config)
        if "llama" in name:
            return self.llama.load(config)
        return self.phi.load(config)

    def load_stt(self, config: Dict[str, Any]) -> Any:
        return self.whisper.load(config)

    def load_vad(self, config: Dict[str, Any]) -> Any:
        return self.vad.load(config)

    def load_embeddings(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": "embeddings", "config": config}

    def load_custom(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": "custom", "config": config}

    def unload(self, model: Any) -> None:
        if importlib.util.find_spec("torch") is None:
            return
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
