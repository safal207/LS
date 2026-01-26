#!/usr/bin/env python3
"""
Quick GUI Test - Minimal version to test overlay functionality
"""

import sys
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QFont

class QuickTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Ghost mode window flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |      # No borders
            Qt.WindowType.WindowStaysOnTopHint |     # Always on top
            Qt.WindowType.Tool |                     # Hide from taskbar
            Qt.WindowType.WindowDoesNotAcceptFocus   # Don't steal focus
        )
        
        # Transparency
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.95)
        
        # Position (top-right)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen.width() - 400, 100, 350, 250)
        
        # Setup UI
        self.setup_ui()
        
        # Drag variables
        self.drag_pos = None
        
        # Test timer
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.run_test_sequence)
        self.test_step = 0
        self.test_timer.start(3000)  # Run test every 3 seconds
        
    def setup_ui(self):
        """Setup simple test UI"""
        central_widget = QWidget()
        
        # Dark theme
        central_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 230);
                border: 1px solid #444444;
                border-radius: 10px;
            }
            QLabel {
                background-color: transparent;
                border: none;
                color: white;
            }
            QPushButton {
                background-color: rgba(60, 60, 60, 200);
                border: 1px solid #555555;
                border-radius: 5px;
                color: #CCCCCC;
                padding: 5px;
                font-size: 11px;
            }
        """)
        
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_layout = QHBoxLayout()
        self.status_label = QLabel("🚀 Ghost Mode Test")
        self.status_label.setStyleSheet("color: #00FF99; font-weight: bold; font-size: 12px;")
        header_layout.addWidget(self.status_label)
        
        header_layout.addStretch()
        
        close_btn = QPushButton("✕ Close")
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        
        layout.addLayout(header_layout)
        
        # Test content
        self.content_label = QLabel("Testing overlay functionality...\n\n"
                                   "1. This window should appear OVER other apps\n"
                                   "2. Text should be readable on dark background\n"
                                   "3. Try dragging window with left mouse button\n"
                                   "4. Close with right mouse button or ✕ button")
        self.content_label.setWordWrap(True)
        self.content_label.setStyleSheet("color: #FFFFFF; font-size: 12px; line-height: 1.4;")
        layout.addWidget(self.content_label)
        
        layout.addStretch()
        
        # Footer
        self.footer_label = QLabel("Test step: 0")
        self.footer_label.setStyleSheet("color: #777777; font-size: 10px;")
        layout.addWidget(self.footer_label)
        
    def run_test_sequence(self):
        """Run automated test sequence"""
        test_messages = [
            "🧪 Test 1: Basic overlay functionality",
            "🧠 Test 2: Simulated question processing", 
            "💡 Test 3: Mock answer generation",
            "✅ Test 4: All systems operational",
            "🔄 Restarting test sequence..."
        ]
        
        message = test_messages[self.test_step % len(test_messages)]
        self.content_label.setText(message)
        self.footer_label.setText(f"Test step: {self.test_step + 1}")
        self.test_step += 1
        
        # Change status color for variety
        colors = ["#00FF99", "#FFAA00", "#55AAFF", "#FF5555"]
        color = colors[self.test_step % len(colors)]
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            
    def mouseReleaseEvent(self, event):
        self.drag_pos = None

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Ghost Mode Quick Test")
    
    window = QuickTestWindow()
    window.show()
    
    print("=== Ghost Mode Quick Test ===")
    print("Instructions:")
    print("1. Open a browser or IDE in fullscreen")
    print("2. This window should appear OVER other applications")
    print("3. Check readability of text")
    print("4. Try dragging the window")
    print("5. Close with right-click or X button")
    print("=============================")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()