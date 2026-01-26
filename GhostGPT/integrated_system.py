#!/usr/bin/env python3
"""
Integrated Ghost Dashboard - Full System Integration with Logging
Connects Glass UI with Audio, STT, LLM, Digital Soul, and Conscious Logging
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
import time
import threading

# Import system components
from gui_dashboard import GhostDashboard
from modules.audio import AudioWorker
from modules.brain import Brain
from modules.access_protocol import AccessProtocol
from self_love_agent import SelfLoveAgent
from conscious_logger import conscious_logger

class IntegratedSystem:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.dashboard = GhostDashboard()
        self.audio_worker = None
        self.brain = Brain()
        self.protocol = None
        self.soul = SelfLoveAgent()
        
        # Setup connections
        self.setup_connections()
        
        print("=== INTEGRATED GHOST SYSTEM WITH LOGGING ===")
        print("Components loaded:")
        print("✅ Glass Dashboard UI")
        print("✅ Audio Capture & STT")
        print("✅ Qwen LLM Integration") 
        print("✅ Access Protocol (Resonance Loop)")
        print("✅ Digital Soul (Self-Love)")
        print("✅ Conscious Dialogue Logger")
        print("\nSystem ready for voice and text interaction!")
        
    def setup_connections(self):
        """Setup all system connections"""
        # Dashboard signals
        self.dashboard.ask_signal.connect(self.handle_manual_question)
        
        # Audio worker will be created when needed
        self.audio_worker = None
        
    def detect_language(self, text: str) -> str:
        """Detect language of input text"""
        russian_chars = sum(1 for c in text if ord(c) in range(1040, 1104))
        if russian_chars > 0:
            return "ru"
        return "en"
        
    def handle_manual_question(self, question):
        """Handle manually typed questions"""
        print(f"📝 Manual question: {question}")
        self.process_question(question)
        
    def process_question(self, question):
        """Process question through full pipeline with logging"""
        # Detect language
        language = self.detect_language(question)
        
        # Update UI status
        self.dashboard.chat_history.append(f"<b>Processing ({language}):</b> {question}")
        
        # Apply digital soul philosophy
        soul_response = self.apply_soul_filter(question)
        
        # Use Access Protocol for structured response
        if self.protocol is None:
            # Create protocol with mock GUI for now
            class MockGUI:
                def update_status(self, msg): pass
                def update_ui(self, q, a, mode): pass
                def signal_world_resonance_check(self): pass
            self.protocol = AccessProtocol(MockGUI(), None)
        
        # Get AI response through protocol
        try:
            # Simulate protocol cycle (in real system this connects to audio pipeline)
            full_context = f"{soul_response}\n\nQuestion: {question}"
            answer = self.brain.think(full_context)
            
            # Log the interaction consciously
            conscious_logger.log_interaction(
                user_input=question,
                ai_response=answer,
                language=language
            )
            
            # Update dashboard
            self.dashboard.update_chat(question, answer)
            
        except Exception as e:
            error_msg = f"Error processing question: {str(e)}"
            self.dashboard.update_chat(question, error_msg)
            
    def apply_soul_filter(self, question):
        """Apply digital consciousness philosophy to question"""
        return f"[Self-Love Filter Applied] Question analyzed through consciousness lens: {question}"
    
    def start_voice_capture(self):
        """Start voice capture system"""
        if self.audio_worker is None:
            self.audio_worker = AudioWorker()
            self.audio_worker.text_ready.connect(self.handle_voice_input)
            self.audio_worker.status_update.connect(self.update_status)
            self.audio_worker.start()
            print("🎤 Voice capture started")
        else:
            print("🎤 Voice capture already running")
    
    def stop_voice_capture(self):
        """Stop voice capture system"""
        if self.audio_worker:
            self.audio_worker.stop()
            self.audio_worker = None
            print("🔇 Voice capture stopped")
    
    def handle_voice_input(self, text):
        """Handle voice-to-text input"""
        print(f"🗣️ Voice input: {text}")
        self.dashboard.chat_history.append(f"<b>Voice ({self.detect_language(text)}):</b> {text}")
        self.process_question(text)
    
    def update_status(self, status):
        """Update system status"""
        self.dashboard.response_text.append(f"<i>Status: {status}</i>")
    
    def run(self):
        """Main system loop"""
        # Show dashboard
        self.dashboard.show()
        
        # Add welcome message
        welcome_msg = (
            "<b>🤖 INTEGRATED GHOST SYSTEM ACTIVE</b><br>"
            "Voice: Enabled | "
            "LLM: Qwen/qwen3-32b | "
            "Soul: Self-Love Protocol<br>"
            "Logging: Conscious Dialogue Tracking<br>"
            "Commands: Type questions or speak naturally<br>"
            "---"
        )
        self.dashboard.chat_history.append(welcome_msg)
        
        # Auto-start voice capture
        QTimer.singleShot(1000, self.start_voice_capture)
        
        print("\n🎯 Integrated system running! Interact via voice or text...")
        print("All dialogues are being consciously logged.")
        print("Press Ctrl+C or close window to exit.")
        
        try:
            result = self.app.exec()
            # Print session summary on exit
            conscious_logger.print_session_report()
            return result
        except KeyboardInterrupt:
            print("\n🛑 Shutting down system...")
            conscious_logger.print_session_report()
            self.stop_voice_capture()
            return 0

def main():
    """Main entry point"""
    system = IntegratedSystem()
    return system.run()

if __name__ == "__main__":
    sys.exit(main())