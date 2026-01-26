#!/usr/bin/env python3
"""
Simple Ghost Dashboard Test
"""

import sys
from PyQt6.QtWidgets import QApplication
from gui_dashboard import GhostDashboard

def main():
    print("=== GHOST DASHBOARD VISUAL TEST ===")
    print("Testing features:")
    print("✅ Glassmorphism design")
    print("✅ Frameless window")
    print("✅ Drag & drop functionality")
    print("✅ Interactive elements")
    print("\nInstructions:")
    print("- Drag window by any area")
    print("- Try the input field at bottom")
    print("- Click close button (✕) to exit")
    print("- Observe the glass effect and styling")
    
    app = QApplication(sys.argv)
    dashboard = GhostDashboard()
    dashboard.show()
    
    # Add test message
    dashboard.chat_history.append("<b>🎨 GLASS DASHBOARD ACTIVE</b>")
    dashboard.chat_history.append("This is a visual test of the new UI design.")
    dashboard.chat_history.append("Features: Transparency, rounded corners, modern styling.")
    dashboard.chat_history.append("---")
    
    print("\n🎯 Dashboard displayed! Interact with the window...")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())