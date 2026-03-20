# Bug Report: GhostGPT Agent GUI — Frontend & Backend

**Branch:** `claude/analyze-agent-gui-bugs-0k8Jd`
**Scope:** `ghost_gui.py`, `ghost_gui_simple.py`, `GhostGPT/modules/gui.py`, `apps/ghostgpt/main.py`, backend pipeline modules

---

## FRONTEND BUGS

### GhostGPT/modules/gui.py

---

#### BUG-01 · `btn_reflect` создаётся дважды — первый экземпляр теряется
**Файл:** `GhostGPT/modules/gui.py:222-223`
**Severity:** High

```python
self.btn_reflect = QPushButton("🪞 Reflect")   # line 222 — теряется
self.btn_reflect = QPushButton("Reflect")       # line 223 — перезаписывает
```
Первый `QPushButton` со значком `🪞` создаётся и немедленно теряется: переменная перезаписывается второй кнопкой. В итоге в layout добавляется кнопка без значка.

---

#### BUG-02 · `btn_reflect.clicked` подключён к `open_reflection_dashboard` дважды
**Файл:** `GhostGPT/modules/gui.py:234,236`
**Severity:** High

```python
self.btn_reflect.clicked.connect(self.open_reflection_dashboard)  # line 234
self.btn_reflect.clicked.connect(self.open_reflection_dashboard)  # line 236 — дубликат
```
Каждый клик вызовет `open_reflection_dashboard` дважды, открывая два дашборда или вызывая двойной показ окна.

---

#### BUG-03 · `btn_reflect` добавляется в `secure_row` дважды
**Файл:** `GhostGPT/modules/gui.py:245,247`
**Severity:** Medium

```python
secure_row.addWidget(self.btn_reflect)  # line 245
secure_row.addWidget(self.btn_reflect)  # line 247 — тот же виджет
```
В Qt виджет может находиться только в одном месте layout. Повторное `addWidget` переместит его, что приведёт к непредсказуемой компоновке и пустому месту в первой позиции.

---

#### BUG-04 · `open_reflection_dashboard` определена дважды в классе — первая переопределяется
**Файл:** `GhostGPT/modules/gui.py:538-549` и `635-640`
**Severity:** Critical

```python
def open_reflection_dashboard(self) -> None:  # line 538 — с decision_pipeline логикой
    ...
def open_reflection_dashboard(self) -> None:  # line 635 — перезаписывает первую!
    if self._reflection_dashboard_factory is None:
        self.update_status("Reflection dashboard unavailable")
        return
    ...
```
Python использует последнее определение метода. Первая (более полная) реализация с `decision_pipeline` и `create_reflection_dashboard` полностью игнорируется. Кнопка "Reflect" всегда попадёт во вторую реализацию, которая требует `_reflection_dashboard_factory` — его нет → статус "Reflection dashboard unavailable".

---

#### BUG-05 · `_reflection_widget` не инициализирован в `__init__` — возможен `AttributeError`
**Файл:** `GhostGPT/modules/gui.py:538-549`
**Severity:** Medium

Первая реализация `open_reflection_dashboard` (line 546) проверяет `self._reflection_widget`, но этот атрибут создаётся только в `set_decision_pipeline()` (line 536). Если `open_reflection_dashboard` вызвать до `set_decision_pipeline` — `AttributeError`.

---

#### BUG-06 · `mouseReleaseEvent` отсутствует — окно "прилипает" и движется без нажатой кнопки
**Файл:** `GhostGPT/modules/gui.py:683-691`
**Severity:** High

```python
def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
        self.old_pos = event.globalPosition().toPoint()

def mouseMoveEvent(self, event):
    if self.old_pos:   # <-- проверяет только на None, не на нажатость кнопки
        delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
        self.move(...)
        self.old_pos = event.globalPosition().toPoint()
```
`mouseReleaseEvent` отсутствует. После отпускания LMB `old_pos` остаётся установленным. При следующем движении мыши (без нажатой кнопки) окно продолжит двигаться. Сравните с `ghost_gui.py:350`, где `mouseReleaseEvent` правильно сбрасывает `drag_position = None`.

---

#### BUG-07 · `test_microphone` — блокирующий I/O в главном потоке UI
**Файл:** `GhostGPT/modules/gui.py:648-681`
**Severity:** Medium

`stream.read(1024)` — блокирующий системный вызов, выполняется в главном Qt thread. Если аудиоустройство недоступно или медленно отвечает, весь GUI замёрзнет. Должен выполняться в отдельном потоке с сигналом обратно в UI.

---

#### BUG-08 · `_apply_snapshot_to_ui` — стиль `protection_badge` при `full_protection` перезаписывается некорректно
**Файл:** `GhostGPT/modules/gui.py:311-351`
**Severity:** Low

Строка 313 устанавливает стиль из `protection_map`. Строка 349 перезаписывает стиль только при `_protection_flash_on == True`. При `_protection_flash_on == False` && `full_protection` — стиль из строки 313 (`"#ff4d4f"`) остаётся, но анимация мигания не работает как задумано (должна переключаться между двумя цветами, а переключается только в одну сторону).

---

#### BUG-09 · `switch_user` заменяет `amygdala`, но `ReflexArc` держит ссылку на старый объект
**Файл:** `GhostGPT/modules/gui.py:570-579`
**Severity:** High

```python
def switch_user(self, user_id: str) -> None:
    self.agent_loop.causal_transitions.amygdala = Amygdala(user_id=selected_user, ...)
```
`ReflexArc` создаётся в `loop.py:116` как:
```python
self.reflex = ReflexArc(self.causal_transitions.amygdala)
```
После `switch_user` `self.reflex` (и `self.bloodstream`) по-прежнему указывают на **старый** `amygdala`. Рефлексы и bloodstream продолжают работать со старым состоянием, игнорируя нового пользователя.

---

### ghost_gui.py

---

#### BUG-10 · Сигнал `question_detected` объявлен, но не подключён ни к одному слоту
**Файл:** `ghost_gui.py:31, 258-262`
**Severity:** Medium

```python
question_detected = pyqtSignal(str)   # объявлен

def connect_signals(self):
    self.backend.status_update.connect(self.update_status)
    self.backend.answer_ready.connect(self.display_answer)
    self.backend.error_occurred.connect(self.show_error)
    # question_detected — не подключён!
```
Даже если backend испустит `question_detected`, вопрос никогда не отобразится отдельно — только вместе с ответом через `answer_ready`.

---

#### BUG-11 · `toggle_pause` создаёт утечку потоков при Resume
**Файл:** `ghost_gui.py:311-322`
**Severity:** High

```python
def toggle_pause(self):
    if "Pause" in self.pause_button.text():
        self.backend.stop_backend()     # останавливает флагом running=False
    else:
        self.backend.start_backend()    # создаёт НОВЫЕ потоки!
```
`stop_backend()` устанавливает `self.running = False`. `start_backend()` создаёт новые `audio_thread`, `stt_thread`, `llm_thread`, `ui_thread` **без уничтожения старых** (daemon-потоки ждут завершения queue, а не флага `running`). При многократном Pause/Resume накапливаются зомби-потоки.

---

#### BUG-12 · `keyPressEvent` для SPACE не выполняет паузу — только `print`
**Файл:** `ghost_gui.py:362-364`
**Severity:** Medium

```python
elif event.key() == Qt.Key.Key_Space:
    print("⏯️ Toggle pause/resume")  # только вывод в консоль!
```
Нет вызова `self.toggle_pause()`. Горячая клавиша SPACE задокументирована как "pause/resume", но не работает.

---

#### BUG-13 · `auto_hide_timer` создаётся но никогда не запускается
**Файл:** `ghost_gui.py:142-145`
**Severity:** Low

```python
self.auto_hide_timer = QTimer()
self.auto_hide_timer.timeout.connect(self.toggle_visibility)
self.auto_hidden = False
# start() отсутствует
```
Функциональность автоскрытия заявлена ("Auto-hide timer (optional feature)") но не реализована.

---

### ghost_gui_simple.py

---

#### BUG-14 · GUI полностью статичен — методы `update_ui` и `update_system_stats` существуют, но ничто их не вызывает
**Файл:** `ghost_gui_simple.py`
**Severity:** High

В `GhostWindow` есть `update_ui()` и `update_system_stats()`, но нет backend-контроллера и нет подключений сигналов. GUI показывает только начальные placeholder-значения и никогда не обновляется.

---

## BACKEND BUGS

### python/modules/agent/resonance_agent.py

---

#### BUG-15 · `anchor_used` в выводе содержит весь контекст, а не только использованные якоря
**Файл:** `python/modules/agent/resonance_agent.py:516`
**Severity:** Medium

```python
"anchor_used": item.get("_anchor_context") or [],
```
Поле `anchor_used` по спецификации должно содержать якоря, которые были использованы в ответе LLM. Но возвращается весь `_anchor_context`. Метод `_rate_response` корректно проверяет, есть ли якори в ответе, но в выходной объект это не проецируется.

---

#### BUG-16 · `feedback()` использует дефолтный `resonance_score = 0.5` для ненайденных циклов
**Файл:** `python/modules/agent/resonance_agent.py:288`
**Severity:** Medium

```python
"resonance_score": cached.get("resonance_score", 0.5),
```
Если `cycle_id` не найден в `_recent_cycles` (кэш ограничен 50 записями), learner получает нейтральный сигнал `0.5` вместо реального значения. Это некорректно обучает модель — подкрепляет нейтральный результат вместо сигнализации об ошибке.
Правильное значение: `0.0` или `None` с проверкой в learner'е.

---

### python/modules/agent/loop.py

---

#### BUG-17 · `_bloodstream_loop` не может быть остановлен быстрее чем через 30 секунд
**Файл:** `python/modules/agent/loop.py:236-244`
**Severity:** Medium

```python
def _bloodstream_loop(self):
    while self.running:
        try:
            self.bloodstream.pump()
            self.bloodstream.filter_toxins()
        except Exception as e:
            logger.error(...)
        time.sleep(30)    # <-- блокирует на 30с после каждой итерации
```
При вызове `stop()` поток не завершится до истечения текущего `sleep(30)`. Нужен `threading.Event` с `wait(timeout)` вместо `time.sleep`.

---

#### BUG-18 · `_maybe_enter_sleep_mode` при `temporal is None` всегда считает state="idle"
**Файл:** `python/modules/agent/loop.py:175-178`
**Severity:** Low

```python
@property
def state(self) -> str:
    return self.temporal.state if self.temporal else "idle"

def _maybe_enter_sleep_mode(self):
    if self.state != "idle":   # при temporal=None → всегда "idle"!
        return
```
При `temporal_enabled=False` агент всегда будет видеть себя в состоянии "idle" и попытается войти в sleep mode при любом idle timeout, даже если реально обрабатывает запрос.

---

### apps/ghostgpt/main.py

---

#### BUG-19 · `_build_reflection_dashboard` обращается к `self.reflection_pipeline`, который не существует
**Файл:** `apps/ghostgpt/main.py:105-106`
**Severity:** High

```python
def _build_reflection_dashboard(self):
    return ReflectionDashboard(self.reflection_pipeline)   # AttributeError!
```
`self.reflection_pipeline` нигде не определён в `__init__`. Вызов метода всегда приведёт к `AttributeError`. Также `ReflectionDashboard` не импортирован.

---

#### BUG-20 · `_tick_heart_pulse` вызывает `_apply_snapshot_to_ui` каждые 380ms без изменений данных
**Файл:** `GhostGPT/modules/gui.py:368-383`
**Severity:** Low

```python
def _tick_heart_pulse(self) -> None:
    self._heart_pulse_step += 1
    ...
    self._apply_snapshot_to_ui(self._last_snapshot)  # пересоздаёт весь UI!
```
`_apply_snapshot_to_ui` устанавливает стили всем виджетам (state_bar, phantom_bar, protection_badge и др.). Вызов каждые 380ms без изменений данных создаёт ~2.6 лишних стилевых пересчёта в секунду. Оба таймера (`_flash_timer` 450ms + `_pulse_timer` 380ms) оба вызывают `_apply_snapshot_to_ui` → суммарно ~4.8 раза/с.

---

## СВОДНАЯ ТАБЛИЦА

| ID | Файл | Описание | Severity |
|----|------|----------|----------|
| BUG-01 | `gui.py:222` | `btn_reflect` создаётся дважды | High |
| BUG-02 | `gui.py:234,236` | `open_reflection_dashboard` подключён дважды | High |
| BUG-03 | `gui.py:245,247` | `btn_reflect` добавлен в layout дважды | Medium |
| BUG-04 | `gui.py:538,635` | `open_reflection_dashboard` определена дважды | **Critical** |
| BUG-05 | `gui.py:546` | `_reflection_widget` не инициализирован в `__init__` | Medium |
| BUG-06 | `gui.py:683` | `mouseReleaseEvent` отсутствует — окно прилипает | High |
| BUG-07 | `gui.py:648` | `test_microphone` блокирует UI поток | Medium |
| BUG-08 | `gui.py:347` | Мигание `protection_badge` в одну сторону | Low |
| BUG-09 | `gui.py:576` | `switch_user` не обновляет `ReflexArc` и `Bloodstream` | High |
| BUG-10 | `ghost_gui.py:31` | Сигнал `question_detected` не подключён | Medium |
| BUG-11 | `ghost_gui.py:311` | `toggle_pause` создаёт утечку потоков | High |
| BUG-12 | `ghost_gui.py:362` | SPACE hotkey не вызывает `toggle_pause` | Medium |
| BUG-13 | `ghost_gui.py:142` | `auto_hide_timer` не запускается | Low |
| BUG-14 | `ghost_gui_simple.py` | GUI статичен — нет backend подключений | High |
| BUG-15 | `resonance_agent.py:516` | `anchor_used` содержит весь контекст, не использованные | Medium |
| BUG-16 | `resonance_agent.py:288` | `feedback()` — дефолт 0.5 вместо 0.0 для ненайденных циклов | Medium |
| BUG-17 | `loop.py:244` | `_bloodstream_loop` не останавливается 30с | Medium |
| BUG-18 | `loop.py:175` | `state="idle"` при `temporal=None` вызывает ложный sleep | Low |
| BUG-19 | `main.py:106` | `reflection_pipeline` не существует → `AttributeError` | High |
| BUG-20 | `gui.py:383` | Избыточный ре-рендер UI ~4.8 раз/с | Low |
