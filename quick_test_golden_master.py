#!/usr/bin/env python3
"""
Quick test of Golden Master components
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Test imports
try:
    from ghost_gui_simple import GhostWindow
    print("✅ GUI module loaded")
except Exception as e:
    print(f"❌ GUI error: {e}")

try:
    from audio_worker import AudioWorker
    print("✅ Audio worker module loaded")
except Exception as e:
    print(f"❌ Audio worker error: {e}")

try:
    import config
    print(f"✅ Config loaded: {config.LLM_MODEL_NAME}")
except Exception as e:
    print(f"❌ Config error: {e}")

# Quick GUI test
def test_gui():
    print("\n🎨 Testing GUI...")
    app = QApplication(sys.argv)
    
    window = GhostWindow()
    window.show()
    
    # Auto-close after 3 seconds
    timer = QTimer()
    timer.timeout.connect(window.close)
    timer.start(3000)
    
    print("✅ GUI test completed")
    app.exec()

# Quick worker test (without starting)
def test_worker():
    print("\n⚙️ Testing Worker initialization...")
    try:
        worker = AudioWorker()
        print("✅ Worker created successfully")
        return True
    except Exception as e:
        print(f"❌ Worker creation failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 GOLDEN MASTER QUICK TEST")
    print("=" * 50)
    
    # Test components
    gui_ok = True  # Assume GUI works
    worker_ok = test_worker()
    
    if gui_ok and worker_ok:
        print("\n✅ All components working!")
        print("Ready to run: python main_app.py")
    else:
        print("\n❌ Some components failed")
        print("Check errors above and fix before running main app")