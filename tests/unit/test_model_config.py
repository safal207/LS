import pytest
from codex.registry.model_config import (
    ModelConfig,
    ModelConfigError,
    format_model_entry,
    validate_config,
)


def test_format_model_entry_all_fields():
    data = {"type": "llm", "quant": "q4", "device": "gpu"}
    assert format_model_entry("test-model", data) == "[LLM] test-model (q4, gpu)"


def test_format_model_entry_only_quant():
    data = {"type": "llm", "quant": "q4"}
    assert format_model_entry("test-model", data) == "[LLM] test-model (q4)"


def test_format_model_entry_only_device():
    data = {"type": "llm", "device": "gpu"}
    assert format_model_entry("test-model", data) == "[LLM] test-model (gpu)"


def test_format_model_entry_no_details():
    data = {"type": "llm"}
    assert format_model_entry("test-model", data) == "[LLM] test-model"


def test_format_model_entry_default_type():
    data = {"quant": "int8"}
    assert format_model_entry("test-model", data) == "[CUSTOM] test-model (int8)"


def test_validate_config_valid():
    validate_config("model", {"type": "llm", "path": "/path"})


def test_validate_config_invalid_name():
    with pytest.raises(ModelConfigError, match="Model name must be a non-empty string"):
        validate_config("", {"type": "llm", "path": "/path"})
    with pytest.raises(ModelConfigError, match="Model name must be a non-empty string"):
        validate_config(123, {"type": "llm", "path": "/path"})


def test_validate_config_invalid_data_type():
    with pytest.raises(ModelConfigError, match="Model config must be a dictionary"):
        validate_config("model", ["not", "a", "dict"])


def test_validate_config_missing_required():
    with pytest.raises(ModelConfigError, match="Missing required fields"):
        validate_config("model", {"type": "llm"})
    with pytest.raises(ModelConfigError, match="Missing required fields"):
        validate_config("model", {"path": "/path"})


def test_validate_config_invalid_type():
    with pytest.raises(ModelConfigError, match="Invalid model type 'invalid'"):
        validate_config("model", {"type": "invalid", "path": "/path"})


def test_validate_config_invalid_path():
    with pytest.raises(ModelConfigError, match="Model path must be a non-empty string"):
        validate_config("model", {"type": "llm", "path": ""})
    with pytest.raises(ModelConfigError, match="Model path must be a non-empty string"):
        validate_config("model", {"type": "llm", "path": 123})


def test_validate_config_invalid_context():
    with pytest.raises(ModelConfigError, match="Model context must be an integer"):
        validate_config("model", {"type": "llm", "path": "/path", "context": "4096"})


@pytest.mark.parametrize("field_name", ["quant", "device", "ram_required", "description"])
def test_validate_config_invalid_string_fields(field_name):
    data = {"type": "llm", "path": "/path", field_name: 123}
    with pytest.raises(ModelConfigError, match=f"Model {field_name} must be a string"):
        validate_config("model", data)


def test_model_config_from_dict():
    data = {
        "type": "llm",
        "path": "/path",
        "context": 4096,
        "quant": "q4",
        "device": "cpu",
        "ram_required": "2GB",
        "description": "A test model",
        "custom_field": "custom_value",
    }
    config = ModelConfig.from_dict("test-model", data)
    assert config.name == "test-model"
    assert config.type == "llm"
    assert config.path == "/path"
    assert config.context == 4096
    assert config.quant == "q4"
    assert config.device == "cpu"
    assert config.ram_required == "2GB"
    assert config.description == "A test model"
    assert config.extras == {"custom_field": "custom_value"}


def test_model_config_to_dict():
    config = ModelConfig(
        name="test-model",
        type="llm",
        path="/path",
        context=4096,
        quant="q4",
        extras={"custom_field": "custom_value"},
    )
    expected = {
        "type": "llm",
        "path": "/path",
        "context": 4096,
        "quant": "q4",
        "custom_field": "custom_value",
    }
    assert config.to_dict() == expected


def test_model_config_to_dict_minimal():
    config = ModelConfig(name="test-model", type="llm", path="/path")
    assert config.to_dict() == {"type": "llm", "path": "/path"}
