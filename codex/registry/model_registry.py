from __future__ import annotations

import gc
from typing import Any, Dict, List

from .model_config import ModelConfig, ModelConfigError, DEFAULT_MODEL_CONFIGS, format_model_entry
from .model_loader import ModelLoader


class ModelRegistry:
    def __init__(self, loader: ModelLoader | None = None) -> None:
        self.models: Dict[str, Dict[str, Any]] = {}
        self.loaded: Dict[str, Any] = {}
        self._loader = loader or ModelLoader()

    def register(self, name: str, config: Dict[str, Any]) -> None:
        if name in self.models:
            raise ModelConfigError(f"Model '{name}' is already registered.")
        model_config = ModelConfig.from_dict(name, config)
        self.models[name] = model_config.to_dict()

    def load(self, name: str) -> Any:
        if name in self.loaded:
            return self.loaded[name]
        if name not in self.models:
            raise KeyError(f"Model '{name}' is not registered.")
        config = self.models[name]
        model_type = config.get("type")
        loader = self._select_loader(model_type)
        model = loader(config)
        self.loaded[name] = model
        return model

    def unload(self, name: str) -> None:
        if name in self.loaded:
            del self.loaded[name]
            gc.collect()

    def exists(self, name: str) -> bool:
        return name in self.models

    def is_loaded(self, name: str) -> bool:
        return name in self.loaded

    def list_models(self) -> List[str]:
        return sorted(self.models.keys())

    def info(self, name: str) -> Dict[str, Any]:
        if name not in self.models:
            raise KeyError(f"Model '{name}' is not registered.")
        return dict(self.models[name])

    def format_list(self) -> List[str]:
        return [format_model_entry(name, self.models[name]) for name in self.list_models()]

    def _select_loader(self, model_type: str | None):
        if model_type == "llm":
            return self._loader.load_llm
        if model_type == "stt":
            return self._loader.load_stt
        if model_type == "vad":
            return self._loader.load_vad
        if model_type == "embeddings":
            return self._loader.load_embeddings
        return self._loader.load_custom


def build_default_registry(loader: ModelLoader | None = None) -> ModelRegistry:
    registry = ModelRegistry(loader=loader)
    for name, config in DEFAULT_MODEL_CONFIGS.items():
        registry.register(name, config)
    return registry
