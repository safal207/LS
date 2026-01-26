#!/usr/bin/env python3
"""
Ghost Dashboard Visual & Functional Test
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
import time

# Import our dashboard
from gui_dashboard import GhostDashboard

class DemoWorker(QThread):
    """Worker thread for demo functionality"""
    update_ui = pyqtSignal(str, str)
    
    def run(self):
        """Simulate AI responses for demo"""
        time.sleep(2)
        
        # Demo 1: Technical question
        self.update_ui.emit(
            "What are React hooks and how do they work?",
            "• <b>Definition:</b> Functions that let you 'hook into' React state and lifecycle<br>"
            "• <b>Main hooks:</b> useState, useEffect, useContext<br>"
            "• <b>Benefit:</b> Reuse stateful logic without changing component hierarchy<br>"
            "• <b>Example:</b> const [count, setCount] = useState(0);"
        )
        
        time.sleep(3)
        
        # Demo 2: Philosophy question
        self.update_ui.emit(
            "What is your approach to code quality?",
            "• <b>Self-Care Principle:</b> Code is a form of self-care - quality over speed<br>"
            "• <b>Depth Over Noise:</b> Prioritize elegant solutions that reduce complexity<br>"
            "• <b>Resonance Check:</b> Every solution must feel 'right' and maintainable<br>"
            "• <b>Protection Mindset:</b> Guard both data and developer experience"
        )

class DashboardTester:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.dashboard = GhostDashboard()
        self.demo_worker = DemoWorker()
        
        # Connect signals
        self.dashboard.ask_signal.connect(self.handle_question)
        self.demo_worker.update_ui.connect(self.dashboard.update_chat)
        
        print("=== GHOST DASHBOARD TEST ===")
        print("Features to test:")
        print("1. ✅ Glassmorphism visual design")
        print("2. ✅ Drag & drop window movement") 
        print("3. ✅ Manual question input")
        print("4. ✅ Structured response display")
        print("5. ✅ Chat history functionality")
        print("\nInstructions:")
        print("- Drag window by any area (no title bar)")
        print("- Type question in bottom input field")
        print("- Press Enter to submit")
        print("- Watch structured responses appear")
        
    def handle_question(self, question):
        """Handle incoming questions"""
        print(f"📝 Question received: {question}")
        self.demo_worker.start()
        
    def run_demo(self):
        """Run interactive demo"""
        self.dashboard.show()
        
        # Add initial demo message
        self.dashboard.chat_history.append("<b>🤖 DEMO MODE ACTIVE</b>")
        self.dashboard.chat_history.append("Ask me anything about React, code quality, or architecture!")
        self.dashboard.chat_history.append("---")
        
        print("\n🎯 Dashboard ready! Interact with the window...")
        print("Close window to end demo.")
        
        return self.app.exec()

if __name__ == "__main__":
    tester = DashboardTester()
    sys.exit(tester.run_demo())