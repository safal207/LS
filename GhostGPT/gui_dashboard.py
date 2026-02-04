import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
    QTextEdit,
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal


class GhostDashboard(QMainWindow):
    ask_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GhostGPT Command Center")
        self.resize(1000, 600)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # Header
        self.header = QFrame()
        self.header.setObjectName("Header")
        self.header_layout = QHBoxLayout(self.header)

        self.btn_pause = QPushButton("Pause")
        self.btn_settings = QPushButton("Settings")
        self.btn_screenshot = QPushButton("Screenshot")
        self.btn_ask = QPushButton("Ask")

        self.header_layout.addWidget(self.btn_pause)
        self.header_layout.addWidget(self.btn_settings)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.btn_ask)
        self.header_layout.addWidget(self.btn_screenshot)

        self.btn_close = QPushButton("X")
        self.btn_close.setObjectName("CloseBtn")
        self.btn_close.clicked.connect(self.close)
        self.header_layout.addWidget(self.btn_close)

        # Content area
        self.content_area = QHBoxLayout()

        # Left panel
        self.left_panel = QFrame()
        self.left_panel.setObjectName("LeftPanel")
        self.left_layout = QVBoxLayout(self.left_panel)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setObjectName("ChatHistory")
        self.chat_history.append("<b>GhostGPT Ready...</b>")
        self.chat_history.append("Listening...")
        self.chat_history.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_history.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_history.setMaximumHeight(400)
        self.left_layout.addWidget(self.chat_history)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your question...")
        self.input_field.returnPressed.connect(self.manual_ask)
        self.left_layout.addWidget(self.input_field)

        # Right panel
        self.right_panel = QFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_layout = QVBoxLayout(self.right_panel)

        self.response_title = QLabel("Suggested Answer")
        self.response_title.setObjectName("TitleLabel")
        self.right_layout.addWidget(self.response_title)

        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setObjectName("ResponseText")
        self.response_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.response_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.response_text.setMaximumHeight(400)
        self.response_text.append("<b>Tip:</b> Keep answers concise.")
        self.response_text.append("<b>Signal:</b> Focus on the question.")
        self.response_text.append("<b>Format:</b> Use short bullet points.")
        self.right_layout.addWidget(self.response_text)

        self.content_area.addWidget(self.left_panel, 1)
        self.content_area.addWidget(self.right_panel, 2)

        self.main_layout.addWidget(self.header)
        self.main_layout.addLayout(self.content_area)

        self.apply_styles()
        self.old_pos = None

    def apply_styles(self):
        self.setStyleSheet("""
            #CentralWidget {
                background-color: rgba(20, 20, 30, 240);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 20);
            }

            QLabel { color: #E0E0E0; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
            #TitleLabel { font-size: 18px; font-weight: bold; color: #FFFFFF; margin-bottom: 10px; }

            #LeftPanel, #RightPanel {
                background-color: rgba(255, 255, 255, 10);
                border-radius: 15px;
                padding: 10px;
            }

            QPushButton {
                background-color: rgba(255, 255, 255, 15);
                color: white;
                border: none;
                border-radius: 15px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 30); }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 50); }

            #CloseBtn { background-color: transparent; color: #FF5555; font-size: 16px; }
            #CloseBtn:hover { color: #FF0000; }

            QLineEdit {
                background-color: rgba(0, 0, 0, 50);
                color: white;
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 10px;
                padding: 8px;
            }

            QTextEdit {
                background-color: rgba(0, 0, 0, 30);
                color: #E0E0E0;
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 10px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }

            QTextEdit#ChatHistory {
                background-color: rgba(0, 0, 0, 40);
                min-height: 300px;
            }

            QTextEdit#ResponseText {
                background-color: rgba(0, 0, 0, 35);
                min-height: 200px;
            }
        """)

    def mousePressEvent(self, event):
        self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def manual_ask(self):
        question = self.input_field.text().strip()
        if question:
            self.chat_history.append(f"<b>You:</b> {question}")
            self.input_field.clear()
            self.ask_signal.emit(question)

    def update_chat(self, question, answer):
        self.chat_history.append(f"<b>You:</b> {question}")
        self.chat_history.append(f"<b>GhostGPT:</b> {answer}")
        self.chat_history.append("---")

        self.response_text.clear()
        self.response_text.append(f"<b>Question:</b> {question}")
        self.response_text.append("")
        self.response_text.append("<b>Answer:</b>")

        if len(answer) > 1000:
            preview = answer[:800] + "..."
            self.response_text.append(preview)
            self.response_text.append("")
            self.response_text.append("<i>Answer truncated for preview.</i>")
        else:
            self.response_text.append(answer)

        self.chat_history.verticalScrollBar().setValue(
            self.chat_history.verticalScrollBar().maximum()
        )
        self.response_text.verticalScrollBar().setValue(
            self.response_text.verticalScrollBar().maximum()
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GhostDashboard()
    window.show()
    sys.exit(app.exec())
