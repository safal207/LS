import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from shared.config_loader import load_config


class TestConfigLoader(unittest.TestCase):
    def test_console_merge(self):
        cfg = load_config("console")
        self.assertIn("audio", cfg)
        self.assertEqual(cfg["audio"]["chunk_duration"], 3.0)
        self.assertEqual(cfg["audio"]["sample_rate"], 16000)

    def test_ghostgpt_merge(self):
        cfg = load_config("ghostgpt")
        self.assertEqual(cfg["audio"]["chunk_duration"], 5)
        self.assertTrue(cfg["llm"]["use_groq"])


if __name__ == "__main__":
    unittest.main()
