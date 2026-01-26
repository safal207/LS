#!/usr/bin/env python3
"""
The Golden Master - Main Application Entry Point
Combines GUI, Audio Worker, and AI modules into one executable
"""

import sys
import time
import queue
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSlot

# Import our modules
from ghost_gui_simple import GhostWindow  # Simplified beautiful GUI
from audio_worker import AudioWorker  # Audio + AI worker
import config  # Configuration

class GhostController:
    """
    Main controller that connects GUI and Backend.
    This is the heart of the application.
    """
    
    def __init__(self):
        # Create Qt Application
        self.app = QApplication(sys.argv)
        
        # 1. Create GUI Window
        self.window = GhostWindow()
        
        # 2. Create Audio Worker (inherits QThread)
        self.worker = AudioWorker()
        
        # 3. Connect signals and slots AFTER both objects are created
        # Worker -> GUI communication
        self.worker.status_update.connect(self.window.lbl_status.setText)
        self.worker.text_ready.connect(self.handle_ai_answer)
        # Note: system_stats signal may not be used in simplified GUI
        
        # 4. Handle application shutdown
        self.app.aboutToQuit.connect(self.cleanup)
        
        print("✅ Ghost Controller initialized")
    
    @pyqtSlot(str, str)
    def handle_ai_answer(self, question, answer):
        """Received AI response -> update UI"""
        # Log to console for debugging
        print(f"📝 Q: {question[:50]}...")
        print(f"🤖 A: {answer[:50]}...")
        
        # Update GUI
        self.window.update_ui(question, answer)
    
    def start(self):
        """Start the application"""
        print("🚀 Launching Ghost Mode...")
        print(f"🔧 Config: Model={config.LLM_MODEL_NAME}")
        
        # Show GUI window
        self.window.show()
        
        # Start audio worker
        self.worker.start()
        
        # Enter Qt event loop
        sys.exit(self.app.exec())
    
    def cleanup(self):
        """Graceful shutdown"""
        print("🛑 Shutting down...")
        if hasattr(self, 'worker'):
            self.worker.stop()

def preflight_check():
    """Pre-launch validation"""
    print("🔍 Preflight Check:")
    
    # Check config
    print(f"  • Model: {config.LLM_MODEL_NAME}")
    print(f"  • Cloud LLM: {config.USE_CLOUD_LLM}")
    print(f"  • Whisper size: {config.WHISPER_MODEL_SIZE}")
    
    # Check required modules
    required_modules = ['ghost_gui', 'audio_worker', 'config']
    for module in required_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
            return False
    
    # Check Ollama connection
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = [m['name'] for m in response.json().get('models', [])]
            target_model = config.LLM_MODEL_NAME
            if target_model in models:
                print(f"  ✅ Ollama: {target_model} available")
            else:
                print(f"  ⚠️  Ollama: {target_model} not found (available: {models})")
        else:
            print("  ❌ Ollama: Connection failed")
    except Exception as e:
        print(f"  ❌ Ollama check: {e}")
    
    return True

def main():
    """Main entry point"""
    print("=" * 50)
    print("👻 GHOST INTERVIEW COPILOT - GOLDEN MASTER 🤖")
    print("=" * 50)
    
    # Run preflight checks
    if not preflight_check():
        print("\n❌ Preflight check failed. Fix issues before launching.")
        sys.exit(1)
    
    print("\n✅ All systems ready!")
    print("💡 Press Ctrl+C or close window to exit")
    print("-" * 50)
    
    # Start the application
    try:
        controller = GhostController()
        controller.start()
    except KeyboardInterrupt:
        print("\n👋 Shutdown requested by user")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()