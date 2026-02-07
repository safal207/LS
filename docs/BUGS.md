# Bug Report System

## Overview
Централизованная система отслеживания багов для LS (Codex) проекта.

## Bug Severity Levels

- **🔴 CRITICAL** - Приложение падает или не запускается
- **🟠 HIGH** - Функциональность полностью сломана
- **🟡 MEDIUM** - Частичная потеря функциональности или workaround
- **🟢 LOW** - Косметические проблемы, опечатки

## Bug Categories

- **IMPORT** - Проблемы с импортами и циклические зависимости
- **RUNTIME** - Ошибки во время выполнения (IndexError, TypeError и т.д.)
- **LOGIC** - Логические ошибки в алгоритмах
- **UI/UX** - Проблемы с интерфейсом
- **TEST** - Проблемы с тестами
- **PERFORMANCE** - Проблемы производительности
- **SECURITY** - Проблемы безопасности

## Fixed Bugs Log

### 2025-02-07

#### 🔴 CRITICAL: TypeError in frame.py
- **File**: `codex/cognitive/workspace/frame.py`
- **Problem**: Нарушен порядок полей в dataclass (non-default после default)
- **Error**: `TypeError: non-default argument 'merit_scores' follows default argument`
- **Fix**: Переупорядочил поля, сделал merit_scores и identity optional с default_factory
- **Commit**: `60d3a38`

#### 🔴 CRITICAL: sys.exit in unified_gui.py
- **File**: `python/gui/unified_gui.py`
- **Problem**: `sys.exit(1)` при ImportError ломал импорт модуля
- **Impact**: Невозможно использовать модуль в тестах
- **Fix**: Добавлена проверка `if __name__ == "__main__"`
- **Commit**: `60d3a38`

#### 🔴 CRITICAL: sys.exit in test_e2e.py
- **File**: `python/tests/test_e2e.py`
- **Problem**: `sys.exit(1)` при ImportError прерывал выполнение тестов
- **Fix**: Заменено на `raise unittest.SkipTest`
- **Commit**: `60d3a38`

#### 🔴 CRITICAL: Unreachable code in runner.py
- **File**: `codex/benchmark/runner.py`
- **Problem**: Методы `_ensure_sample_wav`, `_write_sine_wave` и др. были после `return` внутри `_psutil()`
- **Impact**: Методы недоступны, AttributeError при вызове
- **Fix**: Перенесены на уровень класса BenchmarkRunner
- **Commit**: `e84a2ef`

#### 🔴 CRITICAL: IndexError in loop.py
- **File**: `codex/cognitive/loop.py`
- **Problem**: `candidates[0]` без проверки на пустой список
- **Impact**: IndexError когда все модели отфильтрованы
- **Fix**: Добавлена проверка `if not candidates` и возврат пустого DecisionContext
- **Commit**: `e84a2ef`

#### 🟡 MEDIUM: Missing GlobalFrame import in tests
- **Files**: 
  - `tests/unit/test_unified_cognitive_loop.py`
  - `tests/unit/test_workspace_layer.py`
- **Problem**: Использование `GlobalFrame` без импорта
- **Error**: `NameError: name 'GlobalFrame' is not defined`
- **Fix**: Добавлен `from codex.cognitive.workspace import GlobalFrame`
- **Commit**: `4aec73e`

#### 🟡 MEDIUM: Truncated file in loop.py
- **File**: `codex/cognitive/loop.py`
- **Problem**: Файл обрывался на строке 281, функция `_record_memory` была неполной
- **Fix**: Дописана функция `_record_memory`
- **Commit**: `1bc6288`

#### 🟡 MEDIUM: Field name mismatch
- **Files**: 
  - `codex/cognitive/workspace/frame.py` (causal_context)
  - `codex/cognitive/workspace/schema.py` (memory_refs)
- **Problem**: Разные имена полей в разных классах
- **Fix**: Унифицировано на `memory_refs`
- **Commit**: `e84a2ef`

#### 🟡 MEDIUM: Windows psutil compatibility
- **File**: `codex/causal_memory/layer.py`
- **Problem**: `psutil.sensors_temperatures()` не работает на Windows
- **Fix**: Добавлена проверка `hasattr(psutil, "sensors_temperatures")`
- **Commit**: `1bc6288`

#### 🟡 MEDIUM: importlib.find_spec conflict
- **Files**: 
  - `codex/causal_memory/layer.py`
  - `codex/benchmark/runner.py`
- **Problem**: `importlib.util.find_spec()` конфликтует с pytest monkeypatch
- **Fix**: Заменено на `try/except ImportError`
- **Commit**: `e84a2ef`

## Active Bugs (To Fix)

### 🟡 MEDIUM: ModuleNotFoundError in old python/modules
- **Files**: `python/modules/agent/loop.py`, `python/modules/llm/*.py`
- **Problem**: Абсолютные импорты `from llm.temporal` вместо `from ..llm.temporal`
- **Status**: Частично исправлено, требуется полный рефакторинг
- **Impact**: Старые модули не импортируются
- **Priority**: Medium (используются только в тестах)

### 🟢 LOW: Print statements in CLI
- **File**: `codex/cli.py`
- **Problem**: Использование `print()` вместо `logging`
- **Status**: Не критично, можно оставить для CLI

## How to Report a Bug

1. Проверьте, нет ли уже такого бага в этом файле
2. Используйте шаблон: [BUG_REPORT_TEMPLATE.md](./BUG_REPORT_TEMPLATE.md)
3. Создайте issue на GitHub или добавьте в этот файл
4. Укажите severity и category
5. Добавьте шаги воспроизведения

## Bug Statistics

- **Total Found**: 11
- **Critical Fixed**: 5
- **High Fixed**: 0
- **Medium Fixed**: 5
- **Low Fixed**: 1
- **Active**: 1

## 2025-02-07 - Additional Fixes

### ✅ Fixed: Smoke/E2E Tests Import Errors
- **Files**: 
  - `python/modules/agent/loop.py`
  - `python/modules/llm/cot_adapter.py`
- **Problem**: Relative imports (`from ..llm.temporal`) broken when `python/modules` in sys.path
- **Fix**: Changed to absolute imports (`from python.modules.llm.temporal`)
- **Result**: All 19 smoke tests pass, all 8 e2e tests pass
- **Commit**: `bbd2a47`

## Last Updated
2025-02-07
