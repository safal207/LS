#!/usr/bin/env python3
"""
Simplified Ghost GUI for Golden Master

BUG-14 fix: wired BackendController signals so the GUI actually updates.
"""

import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QObject
from PyQt6.QtGui import QMouseEvent

class _BackendBridge(QObject):
    """Thin Qt signal bridge so BackendController can update the UI thread safely."""
    status_changed = pyqtSignal(str)
    question_ready = pyqtSignal(str)
    answer_ready   = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)


class GhostWindow(QMainWindow):
    """
    Simplified transparent overlay window for interview assistance
    """
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.drag_position = None
        self._connect_backend()  # BUG-14 fix: wire up backend signals
        
    def init_ui(self):
        """Initialize the user interface"""
        # Window setup
        self.setWindowTitle("GhostGPT")
        self.setGeometry(100, 100, 400, 300)
        
        # Make window transparent and frameless
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |      # No borders/title bar
            Qt.WindowType.WindowStaysOnTopHint |     # Always on top
            Qt.WindowType.Tool |                     # Hide from taskbar
            Qt.WindowType.WindowDoesNotAcceptFocus   # Don't steal focus
        )
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Style the widget with dark theme and transparency
        self.central_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 25, 220);  /* Dark semi-transparent */
                border: 1px solid #444444;
                border-radius: 10px;
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_layout = QHBoxLayout()
        
        # Status label
        self.lbl_status = QLabel("🚀 GhostGPT Ready")
        self.lbl_status.setStyleSheet("""
            color: #00FF99; 
            font-weight: bold; 
            font-size: 12px;
        """)
        header_layout.addWidget(self.lbl_status)
        
        header_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(25, 25)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5555;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF3333;
            }
        """)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        
        main_layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #444444;")
        main_layout.addWidget(separator)
        
        # Question display
        self.lbl_question = QLabel("Waiting for interviewer...")
        self.lbl_question.setWordWrap(True)
        self.lbl_question.setStyleSheet("""
            color: #AAAAAA; 
            font-style: italic; 
            font-size: 13px;
            min-height: 40px;
        """)
        main_layout.addWidget(self.lbl_question)
        
        # Answer display
        self.lbl_answer = QLabel("Ghost Mode activated. Listening for questions...")
        self.lbl_answer.setWordWrap(True)
        self.lbl_answer.setStyleSheet("""
            color: #FFFFFF; 
            font-size: 12px;
            font-weight: normal;
            line-height: 1.4;
            min-height: 120px;
        """)
        main_layout.addWidget(self.lbl_answer)
        
        main_layout.addStretch()
        
        # Footer
        footer_layout = QHBoxLayout()
        self.lbl_system = QLabel("CPU: --  RAM: --")
        self.lbl_system.setStyleSheet("color: #777777; font-size: 10px;")
        footer_layout.addWidget(self.lbl_system)
        
        footer_layout.addStretch()
        
        self.lbl_latency = QLabel("Latency: --")
        self.lbl_latency.setStyleSheet("color: #777777; font-size: 10px;")
        footer_layout.addWidget(self.lbl_latency)
        
        main_layout.addLayout(footer_layout)
    
    def _connect_backend(self):
        """Wire backend → UI signals (BUG-14 fix)."""
        try:
            import queue, threading
            from audio.audio_module import AudioIngestion
            from stt.stt_module import SpeechToText
            from llm.llm_module import LanguageModel

            self._bridge = _BackendBridge()
            self._bridge.status_changed.connect(lambda t: self.lbl_status.setText(t))
            self._bridge.question_ready.connect(lambda q: self.lbl_question.setText(f"❓ {q}"))
            self._bridge.answer_ready.connect(self.update_ui)
            self._bridge.error_occurred.connect(
                lambda e: (self.lbl_answer.setText(f"❌ {e}"), self.lbl_status.setText("❌ Error"))
            )

            self._tq = queue.Queue(maxsize=5)
            self._lq = queue.Queue(maxsize=5)
            self._uq = queue.Queue(maxsize=5)

            self._audio = AudioIngestion(self._tq)
            self._stt   = SpeechToText(self._tq, self._lq)
            self._llm   = LanguageModel(self._lq, self._uq)
            self._running = True

            for target in (self._audio.run, self._stt.run, self._llm.run, self._ui_processor):
                threading.Thread(target=target, daemon=True).start()

            self._bridge.status_changed.emit("🎧 Listening...")
        except Exception as exc:
            self.lbl_status.setText(f"⚠ Backend: {exc}")

    def _ui_processor(self):
        import queue as _q
        while self._running:
            try:
                item = self._uq.get(timeout=1.0)
                if isinstance(item, dict) and "question" in item and "response" in item:
                    self._bridge.question_ready.emit(item["question"])
                    self._bridge.answer_ready.emit(item["question"], item["response"])
                    self._bridge.status_changed.emit("🎧 Listening...")
                self._uq.task_done()
            except _q.Empty:
                continue
            except Exception as exc:
                self._bridge.error_occurred.emit(str(exc))

    def update_ui(self, question, answer):
        """Update the UI with new question and answer"""
        # Update question
        formatted_question = f"❓ {question}"
        self.lbl_question.setText(formatted_question)
        
        # Update answer with formatting
        if not answer.startswith("•") and not answer.startswith("-"):
            lines = [line.strip() for line in answer.split('\n') if line.strip()]
            if len(lines) > 1:
                formatted_answer = '\n'.join([f"• {line}" if not line.startswith('•') else line 
                                            for line in lines])
            else:
                formatted_answer = f"• {answer}"
        else:
            formatted_answer = answer
            
        formatted_answer = f"💡 {formatted_answer}"
        self.lbl_answer.setText(formatted_answer)
    
    def update_system_stats(self, stats):
        """Update system statistics display"""
        cpu = stats.get('cpu', '--')
        ram = stats.get('ram', '--')
        latency = stats.get('latency', '--')
        
        self.lbl_system.setText(f"CPU: {cpu}%  RAM: {ram}%")
        self.lbl_latency.setText(f"Latency: {latency}ms")
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for window dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()  # Right-click to close
            
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for window dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        self.drag_position = None
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() == Qt.Key.Key_F12:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "_running"):
            self._running = False
            for mod in ("_audio", "_stt", "_llm"):
                obj = getattr(self, mod, None)
                if obj and hasattr(obj, "stop"):
                    obj.stop()
        event.accept()

def main():
    """Test the simplified GUI"""
    app = QApplication(sys.argv)
    window = GhostWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()