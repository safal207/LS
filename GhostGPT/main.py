from PyQt6.QtWidgets import QApplication
import sys
import keyboard
from modules.gui import GhostWindow
from modules.audio import AudioWorker
from modules.access_protocol import AccessProtocol
import config


class GhostGPT:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = GhostWindow()
        self.audio = AudioWorker()

        # Initialize Access Protocol
        self.protocol = AccessProtocol(self.window, self.audio)

        # Connect signals
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
