#!/usr/bin/env python3
"""
Phase 2: Ghost Mode GUI Overlay
Transparent overlay window that integrates with Phase 1 backend
"""

import sys
import threading
import queue

from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                            QWidget, QHBoxLayout, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QMouseEvent, QPalette, QColor

# Import our backend modules
from audio.audio_module import AudioIngestion
from stt.stt_module import SpeechToText
from llm.llm_module import LanguageModel
from config import SYSTEM_PROMPT
from shared.utils import check_system_resources

class BackendController(QObject):
    """Controller that manages all backend modules"""
    
    # Signals for GUI updates
    status_update = pyqtSignal(str)
    question_detected = pyqtSignal(str)
    answer_ready = pyqtSignal(str, str)  # question, answer
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        
        # Create queues
        self.transcribe_queue = queue.Queue(maxsize=5)
        self.llm_queue = queue.Queue(maxsize=5)
        self.ui_queue = queue.Queue(maxsize=5)
        
        # Initialize modules
        try:
            self.audio_module = AudioIngestion(self.transcribe_queue)
            self.stt_module = SpeechToText(self.transcribe_queue, self.llm_queue)
            self.llm_module = LanguageModel(self.llm_queue, self.ui_queue)
        except Exception as e:
            self.error_occurred.emit(f"Backend init error: {e}")
            raise
    
    def start_backend(self):
        """Start all backend modules in separate threads"""
        if self.running:
            return
            
        self.running = True
        self.status_update.emit("🚀 Initializing backend...")
        
        try:
            # Start modules
            self.audio_thread = threading.Thread(target=self.audio_module.run, daemon=True)
            self.stt_thread = threading.Thread(target=self.stt_module.run, daemon=True)
            self.llm_thread = threading.Thread(target=self.llm_module.run, daemon=True)
            self.ui_thread = threading.Thread(target=self._ui_queue_processor, daemon=True)
            
            self.audio_thread.start()
            self.stt_thread.start()
            self.llm_thread.start()
            self.ui_thread.start()
            
            self.status_update.emit("🎧 Listening...")
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to start backend: {e}")
            self.running = False
    
    def stop_backend(self):
        """Stop all backend modules"""
        self.running = False
        if hasattr(self, 'audio_module'):
            self.audio_module.stop()
        if hasattr(self, 'stt_module'):
            self.stt_module.stop()
        if hasattr(self, 'llm_module'):
            self.llm_module.stop()
    
    def _ui_queue_processor(self):
        """Process responses from backend and emit signals"""
        while self.running:
            try:
                item = self.ui_queue.get(timeout=1.0)
                if isinstance(item, dict) and 'question' in item and 'response' in item:
                    question = item['question']
                    answer = item['response']
                    self.answer_ready.emit(question, answer)
                    self.status_update.emit("🎧 Listening...")
                self.ui_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.error_occurred.emit(f"UI processor error: {e}")

class GhostWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Window flags for ghost mode
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |      # No borders/title bar
            Qt.WindowType.WindowStaysOnTopHint |     # Always on top
            Qt.WindowType.Tool |                     # Hide from taskbar
            Qt.WindowType.WindowDoesNotAcceptFocus   # Don't steal focus
        )
        
        # Transparency settings
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.95)  # Slightly less transparent for better readability
        
        # Initial size and position (top-right corner)
        screen = QApplication.primaryScreen().geometry()
        window_width = 450
        window_height = 350
        x = screen.width() - window_width - 50
        y = 100
        self.setGeometry(x, y, window_width, window_height)
        
        # Create central widget with dark theme
        self.setup_ui()
        
        # Initialize backend controller
        try:
            self.backend = BackendController()
            self.connect_signals()
            self.backend.start_backend()
        except Exception as e:
            self.update_status(f"❌ Backend error: {e}")
        
        # Variables for window dragging
        self.drag_position = None
        
        self.auto_hidden = False
        # BUG-13 fix: removed dead auto_hide_timer that was created but never started.
        
    def setup_ui(self):
        """Setup the user interface"""
        self.central_widget = QWidget()
        
        # Dark theme styling
        self.central_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 15, 15, 240);
                border: 1px solid #333333;
                border-radius: 12px;
            }
            QLabel {
                background-color: transparent;
                border: none;
            }
            QPushButton {
                background-color: rgba(60, 60, 60, 200);
                border: 1px solid #555555;
                border-radius: 6px;
                color: #CCCCCC;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 220);
            }
            QPushButton:pressed {
                background-color: rgba(100, 100, 100, 240);
            }
        """)
        
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        # Status indicator
        self.status_label = QLabel("🚀 GhostGPT Ready")
        self.status_label.setStyleSheet("""
            color: #00FF99; 
            font-weight: bold; 
            font-size: 12px;
        """)
        header_layout.addWidget(self.status_label)
        
        header_layout.addStretch()
        
        # Control buttons
        self.pause_button = QPushButton("⏸ Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.clear_button = QPushButton("🧹 Clear")
        self.clear_button.clicked.connect(self.clear_content)
        self.hide_button = QPushButton("👁 Hide")
        self.hide_button.clicked.connect(self.toggle_visibility)
        
        header_layout.addWidget(self.pause_button)
        header_layout.addWidget(self.clear_button)
        header_layout.addWidget(self.hide_button)
        
        main_layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #444444;")
        main_layout.addWidget(separator)
        
        # Question display
        self.question_label = QLabel("Waiting for interviewer...")
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("""
            color: #AAAAAA; 
            font-style: italic; 
            font-size: 13px;
            min-height: 40px;
        """)
        main_layout.addWidget(self.question_label)
        
        # Answer display
        self.answer_label = QLabel("Ghost Mode activated. Listening for questions...")
        self.answer_label.setWordWrap(True)
        self.answer_label.setStyleSheet("""
            color: #FFFFFF; 
            font-size: 12px;
            font-weight: normal;
            line-height: 1.4;
            min-height: 120px;
        """)
        main_layout.addWidget(self.answer_label)
        
        main_layout.addStretch()
        
        # Footer with system info
        footer_layout = QHBoxLayout()
        self.system_info = QLabel("CPU: ●●○○○  RAM: ●●●○○")
        self.system_info.setStyleSheet("color: #777777; font-size: 10px;")
        footer_layout.addWidget(self.system_info)
        
        footer_layout.addStretch()
        
        self.latency_label = QLabel("Latency: --")
        self.latency_label.setStyleSheet("color: #777777; font-size: 10px;")
        footer_layout.addWidget(self.latency_label)
        
        main_layout.addLayout(footer_layout)
        
    def connect_signals(self):
        """Connect backend signals to GUI slots"""
        self.backend.status_update.connect(self.update_status)
        self.backend.question_detected.connect(self.display_question)  # BUG-10 fix: was never connected
        self.backend.answer_ready.connect(self.display_answer)
        self.backend.error_occurred.connect(self.show_error)
        
    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(status)
        # Update color based on status
        if "Listening" in status:
            color = "#00FF99"  # Green
        elif "Thinking" in status:
            color = "#FFAA00"  # Orange
        elif "Error" in status:
            color = "#FF5555"  # Red
        else:
            color = "#00FF99"  # Default green
            
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
        
    def display_question(self, question):
        """Display incoming question immediately (BUG-10 fix)."""
        self.question_label.setText(f"❓ {question}")
        self.update_status("🤔 Thinking...")

    def display_answer(self, question, answer):
        """Display question and answer"""
        # Format question
        formatted_question = f"❓ {question}"
        self.question_label.setText(formatted_question)
        
        # Format answer with bullet points
        if not answer.startswith("•") and not answer.startswith("-"):
            # Add bullet points if not already formatted
            lines = [line.strip() for line in answer.split('\n') if line.strip()]
            if len(lines) > 1:
                formatted_answer = '\n'.join([f"• {line}" if not line.startswith('•') else line 
                                            for line in lines])
            else:
                formatted_answer = f"• {answer}"
        else:
            formatted_answer = answer
            
        formatted_answer = f"💡 {formatted_answer}"
        self.answer_label.setText(formatted_answer)
        
    def show_error(self, error_msg):
        """Show error message"""
        self.answer_label.setText(f"❌ {error_msg}")
        self.update_status("❌ Error")
        
    def clear_content(self):
        """Clear question and answer display"""
        self.question_label.setText("Waiting for interviewer...")
        self.answer_label.setText("Ready for next question...")
        self.update_status("🧹 Cleared")
        
    def toggle_pause(self):
        """Toggle pause/resume functionality.

        BUG-11 fix: stop_backend/start_backend created new threads on every
        Resume, leaking the old ones.  Now we only toggle the audio module's
        pause flag (if available); the existing threads keep running.
        """
        if "Pause" in self.pause_button.text():
            self.pause_button.setText("▶ Resume")
            self.update_status("⏸ Paused")
            if hasattr(self, 'backend') and hasattr(self.backend, 'audio_module'):
                self.backend.audio_module.pause()
        else:
            self.pause_button.setText("⏸ Pause")
            self.update_status("🎧 Listening")
            if hasattr(self, 'backend') and hasattr(self.backend, 'audio_module'):
                self.backend.audio_module.resume()
            
    def toggle_visibility(self):
        """Toggle window visibility"""
        if self.isHidden():
            self.show()
            self.hide_button.setText("👁 Hide")
            self.auto_hidden = False
        else:
            self.hide()
            self.hide_button.setText("👁 Show")
            self.auto_hidden = True
            
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for window dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            # Right-click context menu could go here
            pass
            
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for window dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        self.drag_position = None
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for emergency situations"""
        if event.key() == Qt.Key.Key_Escape:
            # Hide window (emergency hide)
            self.hide()
            print("👻 Window hidden. Press Alt+Tab to restore or restart app")
        elif event.key() == Qt.Key.Key_F12:
            # Force quit
            print("👋 Force quitting application")
            self.close()
        elif event.key() == Qt.Key.Key_Space:
            self.toggle_pause()  # BUG-12 fix: was only printing, now calls the actual handler
        else:
            super().keyPressEvent(event)
        
    def closeEvent(self, event):
        """Handle window closing"""
        if hasattr(self, 'backend'):
            self.backend.stop_backend()
        event.accept()

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Interview Copilot Ghost Mode")
    app.setApplicationVersion("2.0")
    
    # Create and show window
    window = GhostWindow()
    window.show()
    
    # Start system monitoring
    def update_system_info():
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0)
            ram_percent = psutil.virtual_memory().percent
            
            cpu_bars = "●" * int(cpu_percent/20) + "○" * (5 - int(cpu_percent/20))
            ram_bars = "●" * int(ram_percent/20) + "○" * (5 - int(ram_percent/20))
            
            window.system_info.setText(f"CPU: {cpu_bars}  RAM: {ram_bars}")
        except Exception:
            pass
    
    # Update system info every 2 seconds
    system_timer = QTimer()
    system_timer.timeout.connect(update_system_info)
    system_timer.start(2000)
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()