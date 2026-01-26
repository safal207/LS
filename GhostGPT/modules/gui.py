from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QFont

class GhostWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # LPI Settings (Liminal Presence Interface)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.9)
        self.setGeometry(100, 100, 450, 300)

        # UI Styling
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("""
            QWidget { background-color: rgba(15, 15, 20, 245); border: 1px solid #333; border-radius: 12px; }
            QLabel { background-color: transparent; border: none; }
        """)
        self.setCentralWidget(self.central_widget)
        
        layout = QVBoxLayout(self.central_widget)
        
        # Header (LRI Status)
        header_layout = QVBoxLayout()
        
        # Close button
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(25, 25)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 80, 80, 200);
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: rgba(255, 100, 100, 255);
            }
        """)
        self.btn_close.clicked.connect(self.close)
        
        # Status label
        self.lbl_status = QLabel("👻 GhostGPT Ready")
        self.lbl_status.setStyleSheet("color: #00FF99; font-weight: bold; font-size: 10pt;")
        
        # Microphone test button
        self.btn_mic_test = QPushButton("🎤 Test Mic")
        self.btn_mic_test.setFixedSize(80, 25)
        self.btn_mic_test.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 150, 255, 200);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 8pt;
            }
            QPushButton:hover {
                background-color: rgba(0, 180, 255, 255);
            }
            QPushButton:pressed {
                background-color: rgba(0, 120, 220, 255);
            }
        """)
        self.btn_mic_test.clicked.connect(self.test_microphone)
        
        # Header buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.btn_mic_test)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_close)
        
        # Header container
        header_container = QWidget()
        header_inner_layout = QVBoxLayout(header_container)
        header_inner_layout.addLayout(buttons_layout)
        header_inner_layout.addWidget(self.lbl_status)
        layout.addWidget(header_container)

        # Question
        self.lbl_q = QLabel("Listening...")
        self.lbl_q.setStyleSheet("color: #888; font-style: italic; font-size: 10pt;")
        self.lbl_q.setWordWrap(True)
        layout.addWidget(self.lbl_q)

        # Answer
        self.lbl_a = QLabel("")
        self.lbl_a.setStyleSheet("color: #FFF; font-weight: bold; font-size: 11pt;")
        self.lbl_a.setWordWrap(True)
        self.lbl_a.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.lbl_a)
        
        layout.addStretch()
        self.old_pos = None

    # LPI: Interface Update
    def update_ui(self, q, a, mode):
        self.lbl_q.setText(f"❓ {q}")
        self.lbl_a.setText(f"{a}")
        self.lbl_status.setText(f"🛡️ Mode: {mode}")
    
    # Signal for World Resonance Check (Verification Phase)
    def signal_world_resonance_check(self):
        self.lbl_status.setText("🎯 World Resonance: Awaiting Feedback")
    
    def test_microphone(self):
        """Test microphone input and show audio levels"""
        try:
            import pyaudio
            import numpy as np
            
            p = pyaudio.PyAudio()
            device_index = p.get_default_input_device_info()['index']
            
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024
            )
            
            # Read audio data
            data = stream.read(1024, exception_on_overflow=False)
            audio_np = np.frombuffer(data, dtype=np.int16)
            audio_float = audio_np.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(audio_float**2))
            
            # Update status
            if rms > 0.01:
                self.lbl_status.setText(f"✅ MIC WORKING! Level: {rms:.4f}")
            else:
                self.lbl_status.setText(f"🔇 MIC QUIET Level: {rms:.4f}")
                
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            self.lbl_status.setText(f"❌ MIC ERROR: {str(e)[:30]}...")

    # Drag & Drop
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()