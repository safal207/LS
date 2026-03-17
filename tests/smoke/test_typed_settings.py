import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"
for candidate in (ROOT, PYTHON_ROOT, MODULES_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from modules import config


def test_typed_settings_back_compat():
    assert config.SETTINGS.hardware.max_ram_usage_mb == config.MAX_RAM_USAGE_MB
    assert config.SETTINGS.audio.chunk_duration == config.AUDIO_CHUNK_DURATION
    assert config.SETTINGS.llm.model_name == config.LLM_MODEL_NAME
    assert config.SETTINGS.agent.sleep.idle_timeout == config.SLEEP_CONFIG.idle_timeout
