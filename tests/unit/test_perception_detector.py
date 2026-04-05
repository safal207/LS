import unittest
import time
from python.modules.perception.detector import WindowDetector

class TestWindowDetector(unittest.TestCase):
    def setUp(self):
        self.detector = WindowDetector()

    def test_get_active_window(self):
        """Test that get_active_window returns expected structure and types."""
        window = self.detector.get_active_window()

        # Check structure
        expected_keys = {"title", "class_name", "hwnd", "process_name", "timestamp"}
        self.assertTrue(expected_keys.issubset(window.keys()))

        # Check types
        self.assertIsInstance(window["title"], str)
        self.assertIsInstance(window["class_name"], str)
        self.assertIsInstance(window["hwnd"], str)
        self.assertIsInstance(window["process_name"], str)
        self.assertIsInstance(window["timestamp"], float)

        # Check values
        self.assertEqual(window["title"], "Active Window")
        self.assertLessEqual(window["timestamp"], time.time())

    def test_get_all_windows(self):
        """Test that get_all_windows returns a list of window dictionaries."""
        windows = self.detector.get_all_windows()

        self.assertIsInstance(windows, list)
        self.assertGreater(len(windows), 0)

        for window in windows:
            self.assertIsInstance(window, dict)
            self.assertIn("title", window)
            self.assertIn("process_name", window)
            self.assertIsInstance(window["title"], str)
            self.assertIsInstance(window["process_name"], str)

    def test_get_all_windows_content(self):
        """Test specific content of the simulated window list."""
        windows = self.detector.get_all_windows()
        titles = [w["title"] for w in windows]

        self.assertIn("Visual Studio Code", titles)
        self.assertIn("Zoom Meeting", titles)
        self.assertIn("Chrome", titles)

if __name__ == "__main__":
    unittest.main()
