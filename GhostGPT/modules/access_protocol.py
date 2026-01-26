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
        # PHASE I: CALIBRATION (Step 0)
        if not self.brain.client:
            self.gui.update_status("⚠️ No Resonance (Check API)")
            return

        # PHASE II: INITIALIZATION (Step 1-3)
        # 1. Access Point (Filter noise)
        if len(user_audio_text) < 5: 
            return
        
        # 2. Assembly & 3. Orientation
        # CaPU gathers DMP/CML and sets LRI Persona
        self.gui.update_status("🔄 Assembly...")
        full_context_prompt = self.capu.construct_prompt(user_audio_text)
        current_persona = self.capu.lri.current_mode

        # PHASE III: DYNAMICS (Step 4-5)
        # 4. Transition & 5. Movement
        self.gui.update_status("⚡ Transition...")
        
        # Pass the PROMPT + CONTEXT to the Brain
        answer = self.brain.think(full_context_prompt)

        # Output to GUI (LPI Interface)
        self.gui.update_ui(user_audio_text, answer, current_persona)

        # PHASE IV: VERIFICATION (Step 6-7)
        # Signal that we are waiting for World Resonance (User Confirmation)
        self.gui.signal_world_resonance_check()