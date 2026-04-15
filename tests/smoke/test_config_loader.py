import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "python" / "modules"
SHARED = MODULES / "shared"
for candidate in (ROOT, MODULES, SHARED):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import config_loader
from config_loader import get_config, load_config


class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        config_loader._CONFIG_CACHE.clear()
        config_loader._APP_ALIASES_CACHE = None

    def test_console_merge(self):
        cfg = load_config("console")
        self.assertIn("audio", cfg)
        self.assertEqual(cfg["audio"]["chunk_duration"], 3.0)
        self.assertEqual(cfg["audio"]["sample_rate"], 16000)

    def test_ghostgpt_merge(self):
        cfg = load_config("ghostgpt")
        self.assertEqual(cfg["audio"]["chunk_duration"], 5)
        self.assertTrue(cfg["llm"]["use_groq"])

    def test_alias_uses_registry(self):
        cfg = load_config("ghost_gui")
        self.assertEqual(cfg["audio"]["chunk_duration"], 5)

    def test_detect_app_from_env_alias(self):
        old = os.environ.get("LS_APP")
        os.environ["LS_APP"] = "operator_runtime"
        try:
            cfg = get_config()
            self.assertEqual(cfg["audio"]["chunk_duration"], 5)
        finally:
            if old is None:
                os.environ.pop("LS_APP", None)
            else:
                os.environ["LS_APP"] = old

    def test_unknown_profile_raises_clear_error(self):
        with self.assertRaises(ValueError) as err:
            load_config("market_layer")
        self.assertIn("Unknown app config", str(err.exception))

    def test_schema_validation_fails_on_missing_sections(self):
        with self.assertRaises(ValueError) as err:
            config_loader._validate_runtime_schema({"audio": {}}, "console")
        self.assertIn("missing top-level section", str(err.exception))

    def test_local_profile_layer_preserves_local_overrides(self):
        profile_path = ROOT / "config" / "local.profile.yaml"
        local_path = ROOT / "config" / "local.yaml"
        profile_backup = profile_path.read_text(encoding="utf-8") if profile_path.exists() else None
        local_backup = local_path.read_text(encoding="utf-8") if local_path.exists() else None

        try:
            profile_path.write_text("llm:\n  backend: local\n  use_groq: false\n", encoding="utf-8")
            local_path.write_text("llm:\n  groq:\n    api_key: test-key\n", encoding="utf-8")
            config_loader._CONFIG_CACHE.clear()
            cfg = load_config("console")
            self.assertEqual(cfg["llm"]["backend"], "local")
            self.assertEqual(cfg["llm"]["groq"]["api_key"], "test-key")
        finally:
            if profile_backup is None:
                profile_path.unlink(missing_ok=True)
            else:
                profile_path.write_text(profile_backup, encoding="utf-8")
            if local_backup is None:
                local_path.unlink(missing_ok=True)
            else:
                local_path.write_text(local_backup, encoding="utf-8")
            config_loader._CONFIG_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
