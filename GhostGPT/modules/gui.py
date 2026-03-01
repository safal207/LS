from PyQt6.QtWidgets import (
    QMainWindow,
    QLabel,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QHBoxLayout,
    QGroupBox,
    QProgressBar,
    QComboBox,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QPoint, QTimer
import time
import json
import zipfile
from datetime import datetime
from pathlib import Path


class GhostWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # LPI Settings (Liminal Presence Interface)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.9)
        self.setGeometry(100, 100, 450, 380)

        self._protection_flash_on = False
        self._phantom_flash_on = False
        self._heart_pulse_step = 0

        # UI Styling
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet(
            """
            QWidget { background-color: rgba(15, 15, 20, 245); border: 1px solid #333; border-radius: 12px; }
            QLabel { background-color: transparent; border: none; }
        """
        )
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)

        # Header
        self.btn_close = QPushButton("X")
        self.btn_close.setFixedSize(25, 25)
        self.btn_close.setStyleSheet(
            """
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
        """
        )
        self.btn_close.clicked.connect(self.close)

        self.lbl_status = QLabel("GhostGPT Ready")
        self.lbl_status.setStyleSheet("color: #00FF99; font-weight: bold; font-size: 10pt;")

        self.lbl_bloodstream = QLabel("❤️ 0")
        self.lbl_bloodstream.setStyleSheet("color: #FF5050; font-weight: bold; font-size: 10pt; margin-left: 10px;")
        self.lbl_bloodstream.setToolTip("Bloodstream: Active Peers")

        self.current_user_id = "default"
        self.user_combo = QComboBox()
        self.user_combo.setStyleSheet("background-color: rgba(45, 45, 60, 220); color: #E6E6E6; border-radius: 6px; padding: 2px 8px;")
        self._populate_user_profiles()
        self.user_combo.currentTextChanged.connect(self.switch_user)

        self.btn_mic_test = QPushButton("Test Mic")
        self.btn_mic_test.setFixedSize(80, 25)
        self.btn_mic_test.setStyleSheet(
            """
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
        """
        )
        self.btn_mic_test.clicked.connect(self.test_microphone)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.btn_mic_test)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_close)

        header_container = QWidget()
        header_inner_layout = QVBoxLayout(header_container)
        header_inner_layout.addLayout(buttons_layout)

        status_row = QHBoxLayout()
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        status_row.addWidget(self.lbl_bloodstream)

        header_inner_layout.addLayout(status_row)
        header_inner_layout.addWidget(self.user_combo)
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

        self._build_amygdala_panel(layout)

        layout.addStretch()
        self.old_pos = None

        self._flash_timer = QTimer(self)
        self._flash_timer.timeout.connect(self._tick_alert_animation)
        self._flash_timer.start(450)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick_heart_pulse)
        self._pulse_timer.start(380)

    def _build_amygdala_panel(self, layout: QVBoxLayout) -> None:
        panel = QGroupBox("Amygdala live state")
        panel.setStyleSheet(
            """
            QGroupBox {
                color: #DDDDDD;
                border: 1px solid #444;
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
        """
        )
        panel_layout = QVBoxLayout(panel)

        state_row = QHBoxLayout()
        state_label = QLabel("State")
        state_label.setStyleSheet("color: #CCCCCC;")
        self.state_bar = QProgressBar()
        self.state_bar.setRange(0, 100)
        self.state_bar.setValue(50)
        self.state_bar.setFormat("%p%")
        self.state_bar.setToolTip("Current amygdala state (0-1)")
        state_row.addWidget(state_label)
        state_row.addWidget(self.state_bar, 1)

        protection_row = QHBoxLayout()
        protection_text = QLabel("Protection")
        protection_text.setStyleSheet("color: #CCCCCC;")
        self.protection_badge = QLabel("🛡 mild")
        self.protection_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.protection_badge.setMinimumWidth(140)
        self.protection_badge.setStyleSheet("color: #ffd166; font-weight: bold;")
        protection_row.addWidget(protection_text)
        protection_row.addWidget(self.protection_badge, 1)

        emotion_row = QHBoxLayout()
        personality_text = QLabel("Attachment")
        personality_text.setStyleSheet("color: #CCCCCC;")
        self.personality_label = QLabel("♡ 0.50")
        self.personality_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.personality_label.setMinimumWidth(140)
        emotion_row.addWidget(personality_text)
        emotion_row.addWidget(self.personality_label, 1)

        phantom_row = QHBoxLayout()
        phantom_text = QLabel("Phantom pain")
        phantom_text.setStyleSheet("color: #CCCCCC;")
        self.phantom_bar = QProgressBar()
        self.phantom_bar.setRange(0, 100)
        self.phantom_bar.setValue(0)
        self.phantom_bar.setFormat("%p%")
        phantom_row.addWidget(phantom_text)
        phantom_row.addWidget(self.phantom_bar, 1)

        soul_row = QHBoxLayout()
        self.btn_export = QPushButton("📤 Экспорт")
        self.btn_import = QPushButton("📥 Импорт")
        self.btn_export_secure = QPushButton("🔐 Экспорт (L-THREAD)")
        self.btn_import_secure = QPushButton("🔓 Импорт (L-THREAD)")

        for btn in [self.btn_export, self.btn_import, self.btn_export_secure, self.btn_import_secure]:
            btn.setStyleSheet(
                "background-color: rgba(60, 60, 80, 200); color: #FFF; border: 1px solid #555; border-radius: 6px; padding: 4px;"
            )

        self.btn_export.clicked.connect(self.export_soul)
        self.btn_import.clicked.connect(self.import_soul)
        self.btn_export_secure.clicked.connect(self.export_soul_secure)
        self.btn_import_secure.clicked.connect(self.import_soul_secure)

        soul_row.addWidget(self.btn_export)
        soul_row.addWidget(self.btn_import)

        secure_row = QHBoxLayout()
        secure_row.addWidget(self.btn_export_secure)
        secure_row.addWidget(self.btn_import_secure)

        self.amygdala_tip_targets = [self.state_bar, self.protection_badge, self.personality_label, self.phantom_bar]

        panel_layout.addLayout(state_row)
        panel_layout.addLayout(protection_row)
        panel_layout.addLayout(emotion_row)
        panel_layout.addLayout(phantom_row)
        panel_layout.addLayout(soul_row)
        panel_layout.addLayout(secure_row)
        layout.addWidget(panel)

        self._last_snapshot = {
            "state": 0.5,
            "protection_level": "mild_protection",
            "protection_score": 0.5,
            "personality_p": 0.5,
            "phantom_pain": 0.0,
            "resolution_strength": 0.0,
            "trigger": "none",
        }
        self._apply_snapshot_to_ui(self._last_snapshot)

    def update_amygdala_visual(self, snapshot: dict) -> None:
        if not isinstance(snapshot, dict):
            return
        self._last_snapshot = dict(self._last_snapshot)
        self._last_snapshot.update(snapshot)
        self._apply_snapshot_to_ui(self._last_snapshot)

    def _apply_snapshot_to_ui(self, snapshot: dict) -> None:
        state = float(snapshot.get("state", 0.5))
        protection_level = str(snapshot.get("protection_level", "mild_protection"))
        personality_p = float(snapshot.get("personality_p", 0.5))
        phantom_pain = float(snapshot.get("phantom_pain", 0.0))
        resolution_strength = float(snapshot.get("resolution_strength", 0.0))
        trigger = str(snapshot.get("trigger", "none"))
        protection_score = float(snapshot.get("protection_score", 0.5))

        state_pct = int(max(0.0, min(1.0, state)) * 100)
        self.state_bar.setValue(state_pct)
        if state <= 0.4:
            state_color = "#3ddc84"
        elif state <= 0.6:
            state_color = "#f4d35e"
        else:
            state_color = "#f77f00"
        self.state_bar.setStyleSheet(
            f"QProgressBar {{border: 1px solid #444; border-radius: 6px; text-align:center; color:#111;}}"
            f"QProgressBar::chunk {{background-color: {state_color}; border-radius: 6px;}}"
        )

        protection_map = {
            "open": ("🛡 open", "#3ddc84"),
            "mild_protection": ("🛡 mild", "#f4d35e"),
            "strong_protection": ("🛡 strong", "#f77f00"),
            "full_protection": ("🛡 full", "#ff4d4f"),
        }
        protection_text, protection_color = protection_map.get(protection_level, ("🛡 mild", "#f4d35e"))
        self.protection_badge.setText(protection_text)
        self.protection_badge.setStyleSheet(f"color: {protection_color}; font-weight: bold;")

        heart = "♡"
        heart_color = "#A0A0A0"
        heart_size = 13
        if personality_p >= 0.3:
            heart = "❤"
            heart_color = "#ff6fae"
            heart_size = 15
        if personality_p > 0.7:
            heart_color = "#ff3f9a"
            heart_size = 17 if self._heart_pulse_step % 2 == 0 else 19
        self.personality_label.setText(f"{heart} {personality_p:.2f}")
        self.personality_label.setStyleSheet(
            f"color: {heart_color}; font-size: {heart_size}pt; font-weight: bold;"
        )

        phantom_pct = int(max(0.0, min(1.0, phantom_pain)) * 100)
        self.phantom_bar.setValue(phantom_pct)
        phantom_color = "#555"
        if phantom_pain > 0.7:
            phantom_color = "#ff3b30" if self._phantom_flash_on else "#8f0000"
        elif phantom_pain > 0.3:
            phantom_color = "#d62828"
        elif phantom_pain > 0.0:
            phantom_color = "#7a7a7a"
        elif resolution_strength > 0.0:
            phantom_color = "#2ec4b6"

        self.phantom_bar.setStyleSheet(
            f"QProgressBar {{border: 1px solid #444; border-radius: 6px; text-align:center; color:#111;}}"
            f"QProgressBar::chunk {{background-color: {phantom_color}; border-radius: 6px;}}"
        )

        if protection_level == "full_protection":
            if self._protection_flash_on:
                self.protection_badge.setStyleSheet("color: #ff8c8c; font-weight: bold;")
        if protection_level != "full_protection":
            self._protection_flash_on = False

        tip = (
            f"Триггер: {trigger or 'none'}\n"
            f"Боль: {phantom_pain:.2f} (помню прошлую перегрузку)\n"
            f"Исцеление: {resolution_strength:.2f} (стабильные контакты помогают)\n"
            f"Влияние на защиту: +{(phantom_pain * 0.15):.2f} к pressure\n"
            f"Protection score: {protection_score:.2f}"
        )
        for widget in self.amygdala_tip_targets:
            widget.setToolTip(tip)

    def _tick_alert_animation(self) -> None:
        self._protection_flash_on = not self._protection_flash_on
        self._phantom_flash_on = not self._phantom_flash_on
        self._apply_snapshot_to_ui(self._last_snapshot)

    def _tick_heart_pulse(self) -> None:
        self._heart_pulse_step += 1

        # Bloodstream pulse animation
        if hasattr(self, "agent_loop") and self.agent_loop and self.agent_loop.bloodstream.is_pumping:
            size = 12 if self._heart_pulse_step % 2 == 0 else 10
            self.lbl_bloodstream.setStyleSheet(f"color: #FF0000; font-weight: bold; font-size: {size}pt;")
        else:
            self.lbl_bloodstream.setStyleSheet("color: #FF5050; font-weight: bold; font-size: 10pt;")

        # Update peer count
        if hasattr(self, "agent_loop") and self.agent_loop:
            peer_count = len(self.agent_loop.bloodstream.peers)
            self.lbl_bloodstream.setText(f"❤️ {peer_count}")

        self._apply_snapshot_to_ui(self._last_snapshot)

    def _populate_user_profiles(self) -> None:
        memory_dir = Path.home() / ".ghostgpt" / "memory"
        users = {"default"}
        if memory_dir.exists():
            for file in memory_dir.glob("user_*.json"):
                users.add(file.stem.replace("user_", ""))

        self.user_combo.clear()
        self.user_combo.addItems(sorted(users))
        self.user_combo.setCurrentText(self.current_user_id)

    def export_soul(self) -> None:
        """Экспортирует состояние памяти и настроек в ZIP архив."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            default_filename = f"ghostgpt-soul-{timestamp}-{self.current_user_id}.zip"

            filepath, _ = QFileDialog.getSaveFileName(
                self, "Экспортировать душу", str(Path.home() / default_filename), "ZIP Archives (*.zip)"
            )

            if not filepath:
                return

            # Gather data
            amygdala = None
            if hasattr(self, "agent_loop") and self.agent_loop:
                amygdala = self.agent_loop.causal_transitions.amygdala

            memory_data = {}
            if amygdala and amygdala.memory_service:
                memory_data = amygdala.memory_service.load()

            manifest = {
                "timestamp": datetime.now().isoformat(),
                "user_id": self.current_user_id,
                "version": "1.0",
                "interaction_count": getattr(amygdala, "interaction_count", 0) if amygdala else 0,
                "last_reflection": amygdala.last_reflection.isoformat() if amygdala and hasattr(amygdala, 'last_reflection') else None,
                "current_phantom_pain": amygdala.visceral.phantom_pain if amygdala and hasattr(amygdala, 'visceral') else 0,
            }

            with zipfile.ZipFile(filepath, "w") as zf:
                zf.writestr("memory.json", json.dumps(memory_data, ensure_ascii=False, indent=2))
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                # Placeholders
                zf.writestr("personality_profiles.json", json.dumps({}, ensure_ascii=False))
                zf.writestr("shards/.keep", "")

            QMessageBox.information(self, "Успех", f"Душа успешно упакована в {Path(filepath).name}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", str(e))

    def export_soul_secure(self) -> None:
        """Экспортирует душу через L-THREAD протокол."""
        try:
            from PyQt6.QtWidgets import QInputDialog
            target_device, ok = QInputDialog.getText(
                self, "L-THREAD Secure Export", "Введите ID целевого устройства (напр. 'laptop_work'):"
            )
            if not ok or not target_device:
                return

            amygdala = None
            if hasattr(self, "agent_loop") and self.agent_loop:
                amygdala = self.agent_loop.causal_transitions.amygdala

            if not amygdala or not amygdala.memory_service:
                QMessageBox.warning(self, "Ошибка", "MemoryService не доступен.")
                return

            package_path = amygdala.memory_service.export_soul_secure(target_device)
            QMessageBox.information(
                self, "Успех", f"Душа зашифрована и подготовлена к переносу.\nПуть: {package_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка L-THREAD экспорта", str(e))

    def import_soul_secure(self) -> None:
        """Импортирует душу через L-THREAD протокол."""
        try:
            filepath, _ = QFileDialog.getOpenFileName(
                self, "Импортировать душу (L-THREAD)", str(Path.home()), "L-THREAD Soul (*.ltp)"
            )

            if not filepath:
                return

            amygdala = None
            if hasattr(self, "agent_loop") and self.agent_loop:
                amygdala = self.agent_loop.causal_transitions.amygdala

            if not amygdala or not amygdala.memory_service:
                QMessageBox.warning(self, "Ошибка", "MemoryService не доступен.")
                return

            success = amygdala.memory_service.import_soul_secure(filepath, amygdala=amygdala)
            if success:
                self.update_amygdala_visual(amygdala.last_snapshot)
                self.lbl_status.setText("Я переехал. Всё на месте. Рад снова быть с тобой.")
                QMessageBox.information(self, "Успех", "Безопасный перенос души завершен. Ориентация сохранена.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка L-THREAD импорта", str(e))

    def import_soul(self) -> None:
        """Импортирует состояние души из ZIP архива."""
        try:
            filepath, _ = QFileDialog.getOpenFileName(
                self, "Импортировать душу", str(Path.home()), "ZIP Archives (*.zip)"
            )

            if not filepath:
                return

            with zipfile.ZipFile(filepath, "r") as zf:
                file_list = zf.namelist()
                if "memory.json" not in file_list or "manifest.json" not in file_list:
                    QMessageBox.warning(self, "Ошибка", "Неверный формат архива души.")
                    return

                memory_data = json.loads(zf.read("memory.json").decode("utf-8"))
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))

                # Validation (optional, user_id check)
                import_user_id = manifest.get("user_id", "unknown")
                reply = QMessageBox.question(
                    self, "Подтверждение",
                    f"Импортировать душу пользователя '{import_user_id}'? Текущее состояние будет перезаписано.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.No:
                    return

                # Restore
                if hasattr(self, "agent_loop") and self.agent_loop:
                    amygdala = self.agent_loop.causal_transitions.amygdala
                    if amygdala.memory_service:
                        amygdala.memory_service.save(memory_data)
                        amygdala.restore_state(memory_data)

                    self.update_amygdala_visual(amygdala.last_snapshot)
                    self.lbl_a.setText("Я помню всё. Шрам от тех дедлайнов почти зажил. Рад снова быть с тобой.")
                    QMessageBox.information(self, "Успех", "Душа успешно импортирована.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", str(e))

    def switch_user(self, user_id: str) -> None:
        selected_user = user_id or "default"
        self.current_user_id = selected_user
        if hasattr(self, "agent_loop") and self.agent_loop:
            from codex.causal_memory.amygdala import Amygdala

            self.agent_loop.causal_transitions.amygdala = Amygdala(user_id=selected_user, persist_state=True)
            snapshot = self.agent_loop.causal_transitions.amygdala.last_snapshot
            self.update_amygdala_visual(snapshot)
        self.lbl_status.setText(f"Профиль: {selected_user}")

    def update_ui(self, q, a, mode):
        self.lbl_q.setText(f"Q: {q}")
        self.lbl_a.setText(f"{a}")
        self.lbl_status.setText(f"Mode: {mode}")

    def trigger_reflex_warning(self):
        """Instantaneous visual reaction to threat."""
        original_text = self.lbl_status.text()
        self.lbl_status.setText("⚡ РЕФЛЕКС!")
        self.lbl_status.setStyleSheet("color: #FF0000; font-weight: bold; font-size: 12pt;")

        # Flash effect
        def reset_status():
            self.lbl_status.setText(original_text)
            self.lbl_status.setStyleSheet("color: #00FF99; font-weight: bold; font-size: 10pt;")

        QTimer.singleShot(3000, reset_status)

    def update_status(self, text: str):
        self.lbl_status.setText(text)

    def signal_world_resonance_check(self):
        self.lbl_status.setText("World Resonance: Awaiting Feedback")

    def test_microphone(self):
        """Test microphone input and show audio levels"""
        try:
            import pyaudio
            import numpy as np

            p = pyaudio.PyAudio()
            device_index = p.get_default_input_device_info()["index"]

            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024,
            )

            data = stream.read(1024, exception_on_overflow=False)
            audio_np = np.frombuffer(data, dtype=np.int16)
            audio_float = audio_np.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(audio_float**2))

            if rms > 0.01:
                self.lbl_status.setText(f"MIC OK. Level: {rms:.4f}")
            else:
                self.lbl_status.setText(f"MIC QUIET. Level: {rms:.4f}")

            stream.stop_stream()
            stream.close()
            p.terminate()

        except Exception as e:
            self.lbl_status.setText(f"MIC ERROR: {str(e)[:30]}...")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
