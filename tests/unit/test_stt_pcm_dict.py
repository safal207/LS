from __future__ import annotations

import queue
import sys
import types

import numpy as np


def test_stt_accepts_pcm16_dict_without_wav_path(monkeypatch) -> None:
    captured = {}

    class _FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            return None

        def transcribe(self, audio_input, **kwargs):
            captured["audio_input"] = audio_input
            captured["kwargs"] = kwargs
            return [types.SimpleNamespace(text="hello")], types.SimpleNamespace()

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_FakeWhisperModel))
    monkeypatch.setitem(sys.modules, "config", types.SimpleNamespace(WHISPER_MODEL_SIZE="tiny"))
    monkeypatch.setitem(sys.modules, "shared.utils", types.SimpleNamespace(is_question=lambda _: False))
    import python.modules.stt.stt_module as stt_module

    stt = stt_module.SpeechToText(queue.Queue(), queue.Queue())
    assert stt.load_model() is True

    pcm = (np.ones(3200, dtype=np.int16) * 1000)
    result = stt.transcribe_audio({"samples": pcm, "sample_rate": 16000, "timestamp": 123.4})

    assert result == "hello"
    assert isinstance(captured["audio_input"], np.ndarray)
    assert captured["audio_input"].dtype == np.float32
    assert captured["audio_input"].shape[0] == pcm.shape[0]
