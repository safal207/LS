import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "python" / "modules"
SHARED = MODULES / "shared"
for candidate in (ROOT, MODULES, SHARED):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from config_loader import load_config, _CONFIG_CACHE


class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        _CONFIG_CACHE.clear()

    def test_console_merge(self):
        cfg = load_config("console")
        self.assertIn("audio", cfg)
        self.assertEqual(cfg["audio"]["chunk_duration"], 3.0)
        self.assertEqual(cfg["audio"]["sample_rate"], 16000)

    def test_ghostgpt_merge(self):
        cfg = load_config("ghostgpt")
        self.assertEqual(cfg["audio"]["chunk_duration"], 5)
        self.assertTrue(cfg["llm"]["use_groq"])

    def test_alias_uses_ghostgpt_profile(self):
        cfg = load_config("ghost_gui")
        self.assertEqual(cfg["audio"]["chunk_duration"], 5)

    def test_unknown_profile_raises_clear_error(self):
        with self.assertRaises(ValueError) as err:
            load_config("market_layer")
        self.assertIn("Unknown app config", str(err.exception))


if __name__ == "__main__":
    unittest.main()
