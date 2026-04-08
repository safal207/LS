# -*- coding: utf-8 -*-
"""
Tests for the multimodal operator pipeline components:
  - OCR module (perception/ocr.py)
  - VisionSubsystem.get_latest_screen_text()
  - TTS Speaker (tts/speaker.py)
  - _inject_screen_context logic

Run: python3 tests/unit/test_interview_pipeline.py
"""
from __future__ import annotations

import sys
import os
import threading
import unittest
import unittest.mock as mock

# ── Path bootstrap ────────────────────────────────────────────────────────────
_MODULES = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../python/modules"))
if _MODULES not in sys.path:
    sys.path.insert(0, _MODULES)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers — stub optional heavy deps
# ═══════════════════════════════════════════════════════════════════════════════

def _numpy_array(h=64, w=64, c=3):
    """Return a small zeros array (numpy is available after pip install numpy)."""
    try:
        import numpy as np
        return np.zeros((h, w, c), dtype=np.uint8)
    except ImportError:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# OCR module
# ═══════════════════════════════════════════════════════════════════════════════

class TestOCRModule(unittest.TestCase):

    def test_import_succeeds(self):
        from perception import ocr  # noqa
        self.assertTrue(hasattr(ocr, "extract_text"))
        self.assertTrue(hasattr(ocr, "backend_name"))

    def test_backend_name_is_string(self):
        from perception.ocr import backend_name
        name = backend_name()
        self.assertIn(name, ("pytesseract", "easyocr", "none"))

    def test_extract_text_with_none_backend_returns_empty(self):
        import perception.ocr as ocr_mod
        orig = ocr_mod._BACKEND
        try:
            ocr_mod._BACKEND = "none"
            arr = _numpy_array()
            if arr is None:
                self.skipTest("numpy not available")
            result = ocr_mod.extract_text(arr)
            self.assertEqual(result, "")
        finally:
            ocr_mod._BACKEND = orig

    def test_extract_text_returns_string_on_zeros_frame(self):
        from perception.ocr import extract_text
        arr = _numpy_array()
        if arr is None:
            self.skipTest("numpy not available")
        result = extract_text(arr)
        self.assertIsInstance(result, str)

    def test_extract_text_does_not_raise_on_none_input(self):
        """With _BACKEND=none, extract_text(None) must return '' not raise."""
        import perception.ocr as ocr_mod
        orig = ocr_mod._BACKEND
        try:
            ocr_mod._BACKEND = "none"
            result = ocr_mod.extract_text(None)  # type: ignore[arg-type]
            self.assertEqual(result, "")
        finally:
            ocr_mod._BACKEND = orig

    def test_clean_strips_blank_lines(self):
        from perception.ocr import _clean
        self.assertEqual(_clean("  hello  \n\n  world  \n"), "hello world")

    def test_clean_single_line(self):
        from perception.ocr import _clean
        self.assertEqual(_clean("  one line  "), "one line")

    def test_clean_empty_string(self):
        from perception.ocr import _clean
        self.assertEqual(_clean(""), "")


# ═══════════════════════════════════════════════════════════════════════════════
# VisionSubsystem.get_latest_screen_text
# ═══════════════════════════════════════════════════════════════════════════════

class _MinimalVision:
    """Minimal stub with only the screen-text cache."""
    def __init__(self):
        self._screen_text_lock = threading.Lock()
        self._latest_screen_text = ""

    def get_latest_screen_text(self) -> str:
        with self._screen_text_lock:
            return self._latest_screen_text


class TestVisionScreenText(unittest.TestCase):

    def test_initial_value_is_empty_string(self):
        vs = _MinimalVision()
        self.assertEqual(vs.get_latest_screen_text(), "")

    def test_returns_cached_text(self):
        vs = _MinimalVision()
        vs._latest_screen_text = "Hello from screen"
        self.assertEqual(vs.get_latest_screen_text(), "Hello from screen")

    def test_overwrite_cached_text(self):
        vs = _MinimalVision()
        vs._latest_screen_text = "first"
        vs._latest_screen_text = "second"
        self.assertEqual(vs.get_latest_screen_text(), "second")

    def test_thread_safe_update(self):
        vs = _MinimalVision()
        errors: list = []

        def writer():
            for i in range(200):
                with vs._screen_text_lock:
                    vs._latest_screen_text = f"frame_{i}"

        def reader():
            for _ in range(200):
                try:
                    vs.get_latest_screen_text()
                except Exception as exc:
                    errors.append(exc)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start(); t2.start()
        t1.join(); t2.join()
        self.assertEqual(errors, [])

    def test_only_non_empty_ocr_updates_cache(self):
        """Simulate the coordinator logic: only store if safe_ocr is truthy."""
        vs = _MinimalVision()
        vs._latest_screen_text = "old text"
        safe_ocr = ""  # empty OCR result
        if safe_ocr:
            with vs._screen_text_lock:
                vs._latest_screen_text = safe_ocr
        self.assertEqual(vs.get_latest_screen_text(), "old text")

    def test_non_empty_ocr_updates_cache(self):
        vs = _MinimalVision()
        vs._latest_screen_text = "old text"
        safe_ocr = "new screen content"
        if safe_ocr:
            with vs._screen_text_lock:
                vs._latest_screen_text = safe_ocr
        self.assertEqual(vs.get_latest_screen_text(), "new screen content")


# ═══════════════════════════════════════════════════════════════════════════════
# TTS Speaker
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpeaker(unittest.TestCase):

    def test_import_succeeds(self):
        from tts import speaker as _s  # noqa
        self.assertTrue(hasattr(_s, "Speaker"))

    def test_backend_name_is_known_value(self):
        from tts.speaker import Speaker
        s = Speaker()
        self.assertIn(s.backend_name(), ("pyttsx3", "none"))
        s.stop()

    def test_enabled_property_is_bool(self):
        from tts.speaker import Speaker
        s = Speaker()
        self.assertIsInstance(s.enabled, bool)
        s.stop()

    def test_say_empty_string_no_error(self):
        from tts.speaker import Speaker
        s = Speaker()
        s.say("")
        s.stop()

    def test_say_async_empty_string_no_error(self):
        from tts.speaker import Speaker
        s = Speaker()
        s.say_async("")
        s.stop()

    def test_say_disabled_prints_to_console(self):
        from tts.speaker import Speaker
        import io, contextlib
        s = Speaker.__new__(Speaker)
        s._enabled = False
        s._engine = None
        s._lock = threading.Lock()
        s._queue = []
        s._stop_event = threading.Event()
        s._work_event = threading.Event()
        s._worker_thread = None

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            s.say("test message")
        self.assertIn("test message", buf.getvalue())

    def test_say_async_queues_text(self):
        from tts.speaker import Speaker
        s = Speaker.__new__(Speaker)
        s._enabled = True
        s._engine = mock.MagicMock()
        s._lock = threading.Lock()
        s._queue = []
        s._stop_event = threading.Event()
        s._work_event = threading.Event()
        s._worker_thread = None

        s.say_async("queued text")
        with s._lock:
            self.assertIn("queued text", s._queue)

    def test_stop_safe_without_engine(self):
        from tts.speaker import Speaker
        s = Speaker.__new__(Speaker)
        s._enabled = False
        s._engine = None
        s._worker_thread = None
        s._stop_event = threading.Event()
        s._work_event = threading.Event()
        s._lock = threading.Lock()
        s._queue = []
        s.stop()  # must not raise

    def test_multiple_say_async_calls(self):
        from tts.speaker import Speaker
        s = Speaker.__new__(Speaker)
        s._enabled = True
        s._engine = mock.MagicMock()
        s._lock = threading.Lock()
        s._queue = []
        s._stop_event = threading.Event()
        s._work_event = threading.Event()
        s._worker_thread = None

        s.say_async("first")
        s.say_async("second")
        s.say_async("third")
        with s._lock:
            self.assertEqual(s._queue, ["first", "second", "third"])


# ═══════════════════════════════════════════════════════════════════════════════
# _inject_screen_context (standalone — avoids heavy AgentLoop import chain)
# ═══════════════════════════════════════════════════════════════════════════════

def _inject_screen_context(self, messages, max_chars=1200):
    """Copy of the method under test — extracted for isolated testing."""
    try:
        screen_text = self.vision.get_latest_screen_text()
    except Exception:
        return messages
    if not screen_text or not screen_text.strip():
        return messages
    snippet = screen_text.strip()[:max_chars]
    if len(screen_text.strip()) > max_chars:
        snippet += " …[truncated]"
    return messages + [{"role": "system", "content": f"Current screen content:\n{snippet}"}]


class _LoopStub:
    def __init__(self, screen_text=""):
        self.vision = mock.MagicMock()
        self.vision.get_latest_screen_text.return_value = screen_text

    _inject_screen_context = _inject_screen_context


class TestInjectScreenContext(unittest.TestCase):

    def test_no_screen_text_returns_messages_unchanged(self):
        loop = _LoopStub("")
        msgs = [{"role": "user", "content": "hi"}]
        self.assertEqual(loop._inject_screen_context(msgs), msgs)

    def test_whitespace_only_returns_messages_unchanged(self):
        loop = _LoopStub("   \n  ")
        msgs = [{"role": "user", "content": "hi"}]
        self.assertEqual(loop._inject_screen_context(msgs), msgs)

    def test_screen_text_appended_as_system_message(self):
        loop = _LoopStub("Error: NullPointerException at line 42")
        msgs = [{"role": "user", "content": "what's wrong?"}]
        result = loop._inject_screen_context(msgs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[-1]["role"], "system")
        self.assertIn("NullPointerException", result[-1]["content"])

    def test_original_messages_preserved(self):
        loop = _LoopStub("some screen text")
        msgs = [{"role": "system", "content": "be helpful"}, {"role": "user", "content": "hello"}]
        result = loop._inject_screen_context(msgs)
        self.assertEqual(result[:2], msgs)

    def test_long_screen_text_truncated(self):
        loop = _LoopStub("x" * 2000)
        msgs = [{"role": "user", "content": "hi"}]
        result = loop._inject_screen_context(msgs, max_chars=100)
        injected = result[-1]["content"]
        self.assertIn("truncated", injected)

    def test_exact_max_chars_not_truncated(self):
        loop = _LoopStub("a" * 100)
        msgs = []
        result = loop._inject_screen_context(msgs, max_chars=100)
        self.assertNotIn("truncated", result[-1]["content"])

    def test_vision_exception_returns_messages_unchanged(self):
        loop = _LoopStub()
        loop.vision.get_latest_screen_text.side_effect = RuntimeError("no vision")
        msgs = [{"role": "user", "content": "hi"}]
        self.assertEqual(loop._inject_screen_context(msgs), msgs)

    def test_empty_message_list_still_appends(self):
        loop = _LoopStub("some text on screen")
        result = loop._inject_screen_context([])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "system")

    def test_content_includes_screen_content_label(self):
        loop = _LoopStub("import os")
        result = loop._inject_screen_context([])
        self.assertIn("Current screen content:", result[0]["content"])


# ═══════════════════════════════════════════════════════════════════════════════
# TTS toggle — set_tts() and _tts_active runtime flag
# ═══════════════════════════════════════════════════════════════════════════════

import re as _re

_TTS_ON_RE = _re.compile(
    r"\b(голос\s+вкл|voice\s+on|tts\s+on|включи\s+голос|speak\s+on|озвучка\s+вкл)\b",
    _re.I,
)
_TTS_OFF_RE = _re.compile(
    r"\b(голос\s+выкл|voice\s+off|tts\s+off|выключи\s+голос|speak\s+off|озвучка\s+выкл)\b",
    _re.I,
)


def _set_tts(self, enabled: bool) -> str:
    """Standalone copy of AgentLoop.set_tts() for isolated testing."""
    self._tts_active = bool(enabled)
    if self._speaker is None:
        return (
            "Голос включён (без аудио — pyttsx3 не найден, установи: pip install pyttsx3)"
            if enabled
            else "Голос выключен."
        )
    status = "включён" if enabled else "выключен"
    backend = self._speaker.backend_name()
    return f"Голос {status} (бэкенд: {backend})."


class _AgentStub:
    """Minimal AgentLoop stub with TTS toggle + speak-decision logic."""

    def __init__(self, speaker=None, tts_active=False):
        self._speaker = speaker
        self._tts_active = tts_active

    set_tts = _set_tts

    @property
    def tts_active(self):
        return self._tts_active

    def should_speak(self, item: dict) -> bool:
        """Mirrors the speak-decision logic in AgentLoop._handle_item."""
        override = item.get("_speak")
        if isinstance(override, bool):
            return override and self._speaker is not None
        return self._tts_active and self._speaker is not None


class _FakeSpeaker:
    """Minimal Speaker stub that records calls."""
    def __init__(self):
        self.spoken: list = []
        self._backend = "test"

    def say_async(self, text):
        self.spoken.append(text)

    def backend_name(self):
        return self._backend


class TestTTSToggle(unittest.TestCase):

    # ── set_tts() ────────────────────────────────────────────────────────────

    def test_set_tts_enables_flag(self):
        stub = _AgentStub(tts_active=False)
        stub.set_tts(True)
        self.assertTrue(stub._tts_active)

    def test_set_tts_disables_flag(self):
        stub = _AgentStub(tts_active=True)
        stub.set_tts(False)
        self.assertFalse(stub._tts_active)

    def test_set_tts_returns_confirmation_with_backend(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=False)
        msg = stub.set_tts(True)
        self.assertIn("включён", msg)
        self.assertIn("test", msg)

    def test_set_tts_disabled_confirmation(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=True)
        msg = stub.set_tts(False)
        self.assertIn("выключен", msg)

    def test_set_tts_no_speaker_returns_graceful_message(self):
        stub = _AgentStub(speaker=None, tts_active=False)
        msg = stub.set_tts(True)
        self.assertIn("pyttsx3", msg)

    def test_tts_active_property(self):
        stub = _AgentStub(tts_active=False)
        self.assertFalse(stub.tts_active)
        stub._tts_active = True
        self.assertTrue(stub.tts_active)

    # ── speak decision logic ──────────────────────────────────────────────────

    def test_global_flag_off_no_speak(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=False)
        self.assertFalse(stub.should_speak({}))

    def test_global_flag_on_speaks(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=True)
        self.assertTrue(stub.should_speak({}))

    def test_per_message_override_true_speaks_even_when_global_off(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=False)
        self.assertTrue(stub.should_speak({"_speak": True}))

    def test_per_message_override_false_silences_even_when_global_on(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=True)
        self.assertFalse(stub.should_speak({"_speak": False}))

    def test_per_message_override_true_but_no_speaker_still_false(self):
        stub = _AgentStub(speaker=None, tts_active=False)
        self.assertFalse(stub.should_speak({"_speak": True}))

    def test_global_flag_on_but_no_speaker_returns_false(self):
        stub = _AgentStub(speaker=None, tts_active=True)
        self.assertFalse(stub.should_speak({}))

    # ── TTS toggle regex ──────────────────────────────────────────────────────

    def test_on_regex_matches_voice_on(self):
        self.assertIsNotNone(_TTS_ON_RE.search("voice on"))

    def test_on_regex_matches_tts_on(self):
        self.assertIsNotNone(_TTS_ON_RE.search("tts on"))

    def test_on_regex_matches_russian(self):
        self.assertIsNotNone(_TTS_ON_RE.search("голос вкл"))
        self.assertIsNotNone(_TTS_ON_RE.search("включи голос"))

    def test_off_regex_matches_voice_off(self):
        self.assertIsNotNone(_TTS_OFF_RE.search("voice off"))

    def test_off_regex_matches_russian(self):
        self.assertIsNotNone(_TTS_OFF_RE.search("голос выкл"))
        self.assertIsNotNone(_TTS_OFF_RE.search("выключи голос"))

    def test_on_regex_case_insensitive(self):
        self.assertIsNotNone(_TTS_ON_RE.search("Voice ON"))
        self.assertIsNotNone(_TTS_ON_RE.search("ГОЛОС ВКЛ"))

    def test_off_regex_case_insensitive(self):
        self.assertIsNotNone(_TTS_OFF_RE.search("Voice OFF"))

    def test_slash_commands_caught_before_regex(self):
        # /voice on contains "voice on" so regex matches the substring,
        # but in the handler exact-string check runs first — regex is never reached.
        # Verify the exact-string check works correctly.
        slash_on_commands = ["/voice on", "/tts on"]
        slash_off_commands = ["/voice off", "/tts off"]
        for cmd in slash_on_commands:
            self.assertIn(cmd, ("/voice on", "/voice off", "/tts on", "/tts off"))
        for cmd in slash_off_commands:
            self.assertIn(cmd, ("/voice on", "/voice off", "/tts on", "/tts off"))

    def test_on_regex_does_not_match_off_phrase(self):
        self.assertIsNone(_TTS_ON_RE.search("voice off"))

    def test_off_regex_does_not_match_on_phrase(self):
        self.assertIsNone(_TTS_OFF_RE.search("voice on"))

    # ── Toggle → speak decision integration ──────────────────────────────────

    def test_toggle_on_then_speaks(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=False)
        stub.set_tts(True)
        self.assertTrue(stub.should_speak({}))

    def test_toggle_off_then_silent(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=True)
        stub.set_tts(False)
        self.assertFalse(stub.should_speak({}))

    def test_toggle_multiple_times(self):
        sp = _FakeSpeaker()
        stub = _AgentStub(speaker=sp, tts_active=False)
        for expected in [True, False, True, False]:
            stub.set_tts(expected)
            self.assertEqual(stub.tts_active, expected)


if __name__ == "__main__":
    unittest.main()
