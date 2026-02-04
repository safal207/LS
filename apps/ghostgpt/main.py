from PyQt6.QtWidgets import QApplication
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from shared.config_loader import load_config

os.environ.setdefault("LS_APP", "ghostgpt")
cfg = load_config("ghostgpt")

import keyboard
from GhostGPT.modules.gui import GhostWindow
from GhostGPT.modules.audio import AudioWorker
from GhostGPT.modules.access_protocol import AccessProtocol
from agent.loop import AgentLoop
import config


class GhostGPT:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = GhostWindow()
        self.audio = AudioWorker()

        # Initialize Access Protocol
        self.protocol = AccessProtocol(self.window, self.audio)

        # Connect signals
        self.agent_loop = AgentLoop(
            handler=self.protocol.execute_cycle,
            temporal_enabled=config.TEMPORAL_ENABLED,
        ) if config.AGENT_ENABLED else None
        if self.agent_loop:
            self.audio.text_ready.connect(self.agent_loop.handle_input)
        else:
            self.audio.text_ready.connect(self.protocol.execute_cycle)
        self.audio.status_update.connect(self.window.update_status)

        # Hotkey setup
        keyboard.add_hotkey(config.KEY_HIDE, self.toggle_visibility)
        keyboard.add_hotkey(config.KEY_LRI_HR, lambda: self.set_lri_mode("HR"))
        keyboard.add_hotkey(config.KEY_LRI_DEV, lambda: self.set_lri_mode("TECH"))
        keyboard.add_hotkey(config.KEY_LRI_CTO, lambda: self.set_lri_mode("CTO"))

    def set_lri_mode(self, mode):
        if self.protocol.capu.lri.set_mode(mode):
            self.window.update_status(f"Mode: {mode}")

    def toggle_visibility(self):
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()

    def run(self):
        self.window.show()
        self.audio.start()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    ghost = GhostGPT()
    ghost.run()
