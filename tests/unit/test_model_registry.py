import pytest

from codex.registry import ModelConfigError, ModelLoader, ModelRegistry


class TrackingLoader(ModelLoader):
    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    def load_llm(self, config):
        self.calls.append(("llm", config["path"]))
        return {"loaded": config["path"]}


@pytest.fixture()
def registry():
    loader = TrackingLoader()
    registry = ModelRegistry(loader=loader)
    registry.register(
        "phi3-mini",
        {
            "type": "llm",
            "path": "models/phi3-mini",
            "context": 4096,
            "quant": "q4",
            "device": "cpu",
            "ram_required": "2GB",
        },
    )
    return registry


def test_register_and_info(registry):
    info = registry.info("phi3-mini")
    assert info["type"] == "llm"
    assert info["path"] == "models/phi3-mini"


def test_register_duplicate_raises(registry):
    with pytest.raises(ModelConfigError):
        registry.register("phi3-mini", {"type": "llm", "path": "models/phi3-mini"})


def test_register_invalid_config():
    registry = ModelRegistry()
    with pytest.raises(ModelConfigError):
        registry.register("", {"type": "llm", "path": "models/phi3-mini"})
    with pytest.raises(ModelConfigError):
        registry.register("phi3-mini", {"type": "invalid", "path": "models/phi3-mini"})


def test_lazy_load_caches(registry):
    model_first = registry.load("phi3-mini")
    model_second = registry.load("phi3-mini")
    assert model_first is model_second
    assert registry.is_loaded("phi3-mini") is True
    assert registry._loader.calls == [("llm", "models/phi3-mini")]


def test_unload_clears_cache(registry):
    registry.load("phi3-mini")
    registry.unload("phi3-mini")
    assert registry.is_loaded("phi3-mini") is False
