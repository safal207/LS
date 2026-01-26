import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, 
                             QFrame, QScrollArea, QSizePolicy, QTextEdit)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QFont

class GhostDashboard(QMainWindow):
    # Define signals at class level
    ask_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GhostGPT Command Center")
        self.resize(1000, 600)
        
        # 1. Убираем рамки окна и делаем фон прозрачным (для эффекта стекла)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Основной виджет и layout
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10) # Отступы для тени

        # === [А] HEADER (ВЕРХНЯЯ ПАНЕЛЬ) ===
        self.header = QFrame()
        self.header.setObjectName("Header")
        self.header_layout = QHBoxLayout(self.header)
        
        # Кнопки управления (Пауза, Настройки, Скриншот)
        self.btn_pause = QPushButton("⏸")
        self.btn_settings = QPushButton("⚙️")
        self.btn_screenshot = QPushButton("📸 Скриншот")
        self.btn_ask = QPushButton("💬 Спросить")
        
        # Spacer чтобы раздвинуть элементы
        self.header_layout.addWidget(self.btn_pause)
        self.header_layout.addWidget(self.btn_settings)
        self.header_layout.addStretch() # Пружина посередине
        self.header_layout.addWidget(self.btn_ask)
        self.header_layout.addWidget(self.btn_screenshot)
        
        # Кнопка закрытия (справа)
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("CloseBtn")
        self.btn_close.clicked.connect(self.close)
        self.header_layout.addWidget(self.btn_close)

        # === [Б] CONTENT AREA (РАБОЧАЯ ЗОНА) ===
        self.content_area = QHBoxLayout()
        
        # --- ЛЕВАЯ КОЛОНКА (ЧАТ) ---
        self.left_panel = QFrame()
        self.left_panel.setObjectName("LeftPanel")
        self.left_layout = QVBoxLayout(self.left_panel)
        
        # История чата с прокруткой
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setObjectName("ChatHistory")
        self.chat_history.append("<b>GhostGPT Ready...</b>")
        self.chat_history.append("Listening...")
        self.chat_history.setWordWrapMode(True)
        self.chat_history.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_history.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_history.setMaximumHeight(400)  # Ограничиваем высоту для лучшей прокрутки
        self.left_layout.addWidget(self.chat_history)
        
        # Поле ввода
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Введите запрос вручную...")
        self.input_field.returnPressed.connect(self.manual_ask)
        self.left_layout.addWidget(self.input_field)

        # --- ПРАВАЯ КОЛОНКА (СТРУКТУРИРОВАННЫЙ ОТВЕТ) ---
        self.right_panel = QFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_layout = QVBoxLayout(self.right_panel)
        
        # Заголовок ответа
        self.response_title = QLabel("Подробный ответ")
        self.response_title.setObjectName("TitleLabel")
        self.right_layout.addWidget(self.response_title)
        
        # Текст ответа с прокруткой и без обрезки
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setObjectName("ResponseText")
        self.response_text.setWordWrapMode(True)
        self.response_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.response_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.response_text.setMaximumHeight(400)  # Ограничиваем высоту для лучшей прокрутки
        self.response_text.append("• <b>Анализ:</b> Запрос принят.")
        self.response_text.append("• <b>Контекст:</b> Разработка UI.")
        self.response_text.append("• <b>Решение:</b> Использован QSS для стилизации.")
        self.right_layout.addWidget(self.response_text)

        # Добавляем панели в контент
        self.content_area.addWidget(self.left_panel, 1) # Пропорция 1
        self.content_area.addWidget(self.right_panel, 2) # Пропорция 2 (шире)

        # Собираем всё вместе
        self.main_layout.addWidget(self.header)
        self.main_layout.addLayout(self.content_area)

        # === [В] STYLING (ОФОРМЛЕНИЕ) ===
        self.apply_styles()
        
        # Перетаскивание окна (так как убрали рамку)
        self.old_pos = None

    def apply_styles(self):
        # CSS-подобные стили для Qt
        self.setStyleSheet("""
            /* Глобальный фон (полупрозрачный черный) */
            #CentralWidget {
                background-color: rgba(20, 20, 30, 240); 
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 20);
            }
            
            /* Текст */
            QLabel { color: #E0E0E0; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
            #TitleLabel { font-size: 18px; font-weight: bold; color: #FFFFFF; margin-bottom: 10px; }
            
            /* Панели */
            #LeftPanel, #RightPanel {
                background-color: rgba(255, 255, 255, 10);
                border-radius: 15px;
                padding: 10px;
            }
            
            /* Кнопки */
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
            
            /* Кнопка закрытия */
            #CloseBtn { background-color: transparent; color: #FF5555; font-size: 16px; }
            #CloseBtn:hover { color: #FF0000; }
            
            /* Поле ввода */
            QLineEdit {
                background-color: rgba(0, 0, 0, 50);
                color: white;
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 10px;
                padding: 8px;
            }
            
            /* Текстовые поля */
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
                min-height: 300px;  /* Минимальная высота для чата */
            }
            
            QTextEdit#ResponseText {
                background-color: rgba(0, 0, 0, 35);
                min-height: 200px;  /* Минимальная высота для ответов */
            }
        """)

    # Логика перетаскивания окна мышкой
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
        """Обработка ручного ввода вопроса"""
        question = self.input_field.text().strip()
        if question:
            self.chat_history.append(f"<b>Вы:</b> {question}")
            self.input_field.clear()
            self.ask_signal.emit(question)
    
    def update_chat(self, question, answer):
        """Обновление чата новым сообщением - исправленная версия"""
        # Добавляем вопрос в историю
        self.chat_history.append(f"<b>Вы:</b> {question}")
        self.chat_history.append(f"<b>GhostGPT:</b> {answer}")
        self.chat_history.append("---")
        
        # Обновляем правую панель ПОЛНОСТЬЮ
        self.response_text.clear()
        self.response_text.append(f"<b>Вопрос:</b> {question}")
        self.response_text.append("")
        self.response_text.append("<b>Ответ:</b>")
        
        # Разбиваем длинный ответ на строки для лучшего отображения
        if len(answer) > 1000:
            # Для очень длинных ответов - показываем первые 800 символов + продолжение
            preview = answer[:800] + "..."
            self.response_text.append(preview)
            self.response_text.append("")
            self.response_text.append("<i>Полный ответ сохранен в логах</i>")
        else:
            # Для нормальных ответов - показываем полностью
            self.response_text.append(answer)
        
        # Прокручиваем вниз
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