import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

for name in ["pyaudio", "numpy", "soundfile", "faster_whisper", "requests", "psutil"]:
    sys.modules.setdefault(name, MagicMock())

qtwidgets = types.ModuleType("PyQt6.QtWidgets")

class DummyApp:
    def __init__(self, argv):
        self.argv = argv

    def exec(self):
        return 0

qtwidgets.QApplication = DummyApp
pyqt6 = types.ModuleType("PyQt6")
pyqt6.QtWidgets = qtwidgets
sys.modules.setdefault("PyQt6", pyqt6)
sys.modules.setdefault("PyQt6.QtWidgets", qtwidgets)

keyboard = types.ModuleType("keyboard")
keyboard.add_hotkey = lambda *args, **kwargs: None
sys.modules.setdefault("keyboard", keyboard)

class DummySignal:
    def connect(self, fn):
        return None

class GhostWindow:
    def __init__(self):
        self._visible = False
        self.status = None

    def isVisible(self):
        return self._visible

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def update_status(self, text):
        self.status = text

class AudioWorker:
    def __init__(self):
        self.text_ready = DummySignal()
        self.status_update = DummySignal()

    def start(self):
        return None

class DummyLRI:
    def set_mode(self, mode):
        return True

class DummyCapu:
    def __init__(self):
        self.lri = DummyLRI()

class AccessProtocol:
    def __init__(self, window, audio):
        self.capu = DummyCapu()

    def execute_cycle(self, text):
        return None

mod_gui = types.ModuleType("GhostGPT.modules.gui")
mod_gui.GhostWindow = GhostWindow
mod_audio = types.ModuleType("GhostGPT.modules.audio")
mod_audio.AudioWorker = AudioWorker
mod_access = types.ModuleType("GhostGPT.modules.access_protocol")
mod_access.AccessProtocol = AccessProtocol

sys.modules["GhostGPT.modules.gui"] = mod_gui
sys.modules["GhostGPT.modules.audio"] = mod_audio
sys.modules["GhostGPT.modules.access_protocol"] = mod_access


class TestEntrypointImports(unittest.TestCase):
    def test_imports(self):
        import importlib

        console = importlib.import_module("apps.console.main")
        ghost = importlib.import_module("apps.ghostgpt.main")

        self.assertTrue(hasattr(console, "InterviewCopilot"))
        self.assertTrue(hasattr(ghost, "GhostGPT"))


if __name__ == "__main__":
    unittest.main()
