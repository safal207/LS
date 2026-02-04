from modules.capu import CaPU
from modules.brain import Brain


class AccessProtocol:
    def __init__(self, gui, audio):
        self.gui = gui
        self.audio = audio
        self.capu = CaPU()
        self.brain = Brain()

    def execute_cycle(self, user_audio_text):
        """
        Executes the 0-7 Resonance Loop.
        """
        # Phase I: Calibration
        if not self.brain.client:
            self.gui.update_status("No resonance (check API)")
            return

        # Phase II: Initialization
        if len(user_audio_text) < 5:
            return

        self.gui.update_status("Assembly...")
        full_context_prompt = self.capu.construct_prompt(user_audio_text)
        current_persona = self.capu.lri.current_mode

        # Phase III: Dynamics
        self.gui.update_status("Transition...")
        answer = self.brain.think(full_context_prompt)

        # Output to GUI
        self.gui.update_ui(user_audio_text, answer, current_persona)

        # Phase IV: Verification
        self.gui.signal_world_resonance_check()
